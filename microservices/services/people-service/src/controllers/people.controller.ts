import { Request, Response, NextFunction } from 'express';
import { validationResult } from 'express-validator';
import {
  successResponse,
  errorResponse,
  NotFoundError,
  createLogger,
  PersonCreatedEvent,
  PersonUpdatedEvent,
} from '@microservices/shared';
import { pool } from '../config/database';
import { redisClient, CacheKeys, CacheTTL } from '../config/redis';
import { publishEvent, Topics } from '../config/kafka';

const logger = createLogger('people-controller');

/**
 * Create new person
 * POST /api/people
 */
export async function createPerson(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const { first_name, last_name, email, phone, address } = req.body;
    const userId = (req as any).user.userId;

    const result = await pool.query(
      'INSERT INTO people (first_name, last_name, email, phone, address, created_by) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *',
      [first_name, last_name, email, phone, address, userId]
    );

    const person = result.rows[0];

    // Invalidate cache list
    const keys = await redisClient.keys('people:list:*');
    if (keys.length > 0) {
      await redisClient.del(keys);
    }

    // Publish Kafka event
    const event: PersonCreatedEvent = {
      id: person.id,
      firstName: person.first_name,
      lastName: person.last_name,
      email: person.email,
    };
    await publishEvent(Topics.PEOPLE_CREATED, {
      eventType: 'PersonCreated',
      timestamp: new Date().toISOString(),
      data: event,
      metadata: { userId },
    });

    logger.info('Person created', { personId: person.id, userId });

    res.status(201).json(successResponse(person));
  } catch (error) {
    next(error);
  }
}

/**
 * Get person by ID (with Redis cache)
 * GET /api/people/:id
 */
export async function getPerson(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);
    const cacheKey = CacheKeys.person(id);

    // Try cache first
    const cached = await redisClient.get(cacheKey);
    if (cached) {
      logger.info('Cache hit', { personId: id });
      return res.json(successResponse(JSON.parse(cached)));
    }

    // Cache miss - query DB
    const result = await pool.query('SELECT * FROM people WHERE id = $1', [id]);
    if (result.rows.length === 0) {
      throw new NotFoundError('Person not found');
    }

    const person = result.rows[0];

    // Set cache
    await redisClient.setEx(cacheKey, CacheTTL.person, JSON.stringify(person));
    logger.info('Cache miss - cached', { personId: id });

    res.json(successResponse(person));
  } catch (error) {
    next(error);
  }
}

/**
 * List people (with pagination and cache)
 * GET /api/people?page=1&limit=10
 */
export async function listPeople(req: Request, res: Response, next: NextFunction) {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const offset = (page - 1) * limit;

    const cacheKey = CacheKeys.peopleList(page, limit);

    // Try cache
    const cached = await redisClient.get(cacheKey);
    if (cached) {
      logger.info('Cache hit - list', { page, limit });
      return res.json(JSON.parse(cached));
    }

    // Query DB
    const [dataResult, countResult] = await Promise.all([
      pool.query('SELECT * FROM people ORDER BY id DESC LIMIT $1 OFFSET $2', [limit, offset]),
      pool.query('SELECT COUNT(*) FROM people'),
    ]);

    const total = parseInt(countResult.rows[0].count);
    const response = successResponse({
      data: dataResult.rows,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });

    // Cache result
    await redisClient.setEx(cacheKey, CacheTTL.list, JSON.stringify(response));
    logger.info('Cache miss - list cached', { page, limit });

    res.json(response);
  } catch (error) {
    next(error);
  }
}

/**
 * Update person
 * PUT /api/people/:id
 */
export async function updatePerson(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);
    const userId = (req as any).user.userId;
    const updates = req.body;

    // Build dynamic update query
    const fields = Object.keys(updates);
    const values = Object.values(updates);
    const setClause = fields.map((field, idx) => `${field} = $${idx + 1}`).join(', ');

    const result = await pool.query(
      `UPDATE people SET ${setClause}, updated_at = CURRENT_TIMESTAMP WHERE id = $${fields.length + 1} RETURNING *`,
      [...values, id]
    );

    if (result.rows.length === 0) {
      throw new NotFoundError('Person not found');
    }

    const person = result.rows[0];

    // Invalidate cache
    await redisClient.del(CacheKeys.person(id));
    const listKeys = await redisClient.keys('people:list:*');
    if (listKeys.length > 0) {
      await redisClient.del(listKeys);
    }

    // Publish event
    const event: PersonUpdatedEvent = {
      id: person.id,
      changes: updates,
    };
    await publishEvent(Topics.PEOPLE_UPDATED, {
      eventType: 'PersonUpdated',
      timestamp: new Date().toISOString(),
      data: event,
      metadata: { userId },
    });

    logger.info('Person updated', { personId: id, userId });

    res.json(successResponse(person));
  } catch (error) {
    next(error);
  }
}

/**
 * Delete person
 * DELETE /api/people/:id
 */
export async function deletePerson(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const id = parseInt(req.params.id);
    const userId = (req as any).user.userId;

    const result = await pool.query('DELETE FROM people WHERE id = $1 RETURNING id', [id]);
    if (result.rows.length === 0) {
      throw new NotFoundError('Person not found');
    }

    // Invalidate cache
    await redisClient.del(CacheKeys.person(id));
    const listKeys = await redisClient.keys('people:list:*');
    if (listKeys.length > 0) {
      await redisClient.del(listKeys);
    }

    // Publish event
    await publishEvent(Topics.PEOPLE_DELETED, {
      eventType: 'PersonDeleted',
      timestamp: new Date().toISOString(),
      data: { id },
      metadata: { userId },
    });

    logger.info('Person deleted', { personId: id, userId });

    res.json(successResponse({ id }, 'Person deleted'));
  } catch (error) {
    next(error);
  }
}
