import { Request, Response, NextFunction } from 'express';
import { validationResult } from 'express-validator';
import { successResponse, errorResponse, NotFoundError, createLogger } from '@microservices/shared';
import { pool } from '../config/database';
import {
  indexCase,
  updateCaseInIndex,
  deleteCaseFromIndex,
  searchCases as esSearchCases,
} from '../config/elasticsearch';

const logger = createLogger('case-controller');

/**
 * Generate unique case number
 */
function generateCaseNumber(): string {
  const timestamp = Date.now();
  const random = Math.floor(Math.random() * 1000);
  return `CASE-${timestamp}-${random}`;
}

/**
 * Create new case
 * POST /api/cases
 */
export async function createCase(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const { title, description, status, priority, assigned_to, person_id } = req.body;
    const userId = (req as any).user.userId;
    const caseNumber = generateCaseNumber();

    const result = await pool.query(
      `INSERT INTO cases (case_number, title, description, status, priority, assigned_to, person_id, created_by)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *`,
      [caseNumber, title, description, status || 'open', priority || 'medium', assigned_to, person_id, userId]
    );

    const caseData = result.rows[0];

    // Index vào Elasticsearch
    await indexCase(caseData);

    logger.info('Case created', { caseId: caseData.id, caseNumber });

    res.status(201).json(successResponse(caseData));
  } catch (error) {
    next(error);
  }
}

/**
 * Get case by ID
 * GET /api/cases/:id
 */
export async function getCase(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);

    const result = await pool.query('SELECT * FROM cases WHERE id = $1', [id]);
    if (result.rows.length === 0) {
      throw new NotFoundError('Case not found');
    }

    res.json(successResponse(result.rows[0]));
  } catch (error) {
    next(error);
  }
}

/**
 * List cases with pagination
 * GET /api/cases?page=1&limit=10
 */
export async function listCases(req: Request, res: Response, next: NextFunction) {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const offset = (page - 1) * limit;

    const [dataResult, countResult] = await Promise.all([
      pool.query('SELECT * FROM cases ORDER BY id DESC LIMIT $1 OFFSET $2', [limit, offset]),
      pool.query('SELECT COUNT(*) FROM cases'),
    ]);

    const total = parseInt(countResult.rows[0].count);

    res.json(
      successResponse({
        data: dataResult.rows,
        pagination: {
          page,
          limit,
          total,
          totalPages: Math.ceil(total / limit),
        },
      })
    );
  } catch (error) {
    next(error);
  }
}

/**
 * Search cases using Elasticsearch
 * GET /api/cases/search?q=keyword&status=open&priority=high
 */
export async function searchCases(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const query = (req.query.q as string) || '';
    const filters = {
      status: req.query.status as string,
      priority: req.query.priority as string,
      assigned_to: req.query.assigned_to ? parseInt(req.query.assigned_to as string) : undefined,
    };

    const results = await esSearchCases(query, filters);

    logger.info('Search performed', { query, resultCount: results.length });

    res.json(successResponse(results));
  } catch (error) {
    next(error);
  }
}

/**
 * Update case
 * PUT /api/cases/:id
 */
export async function updateCase(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);
    const updates = req.body;

    const fields = Object.keys(updates);
    const values = Object.values(updates);
    const setClause = fields.map((field, idx) => `${field} = $${idx + 1}`).join(', ');

    const result = await pool.query(
      `UPDATE cases SET ${setClause}, updated_at = CURRENT_TIMESTAMP WHERE id = $${fields.length + 1} RETURNING *`,
      [...values, id]
    );

    if (result.rows.length === 0) {
      throw new NotFoundError('Case not found');
    }

    const caseData = result.rows[0];

    // Update Elasticsearch
    await updateCaseInIndex(id, updates);

    logger.info('Case updated', { caseId: id });

    res.json(successResponse(caseData));
  } catch (error) {
    next(error);
  }
}

/**
 * Delete case
 * DELETE /api/cases/:id
 */
export async function deleteCase(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);

    const result = await pool.query('DELETE FROM cases WHERE id = $1 RETURNING id', [id]);
    if (result.rows.length === 0) {
      throw new NotFoundError('Case not found');
    }

    // Delete from Elasticsearch
    await deleteCaseFromIndex(id);

    logger.info('Case deleted', { caseId: id });

    res.json(successResponse({ id }, 'Case deleted'));
  } catch (error) {
    next(error);
  }
}
