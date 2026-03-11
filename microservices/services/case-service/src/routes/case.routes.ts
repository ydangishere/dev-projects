import { Router } from 'express';
import { body, param, query } from 'express-validator';
import {
  createCase,
  getCase,
  listCases,
  updateCase,
  deleteCase,
  searchCases as searchCasesController,
} from '../controllers/case.controller';
import { authenticate } from '../middleware/auth.middleware';

const router = Router();

router.use(authenticate);

/**
 * POST /api/cases
 */
router.post(
  '/',
  [
    body('title').notEmpty().withMessage('Title is required'),
    body('description').optional().isString(),
    body('status').optional().isIn(['open', 'in_progress', 'closed']),
    body('priority').optional().isIn(['low', 'medium', 'high']),
    body('assigned_to').optional().isInt(),
    body('person_id').optional().isInt(),
  ],
  createCase
);

/**
 * GET /api/cases?page=1&limit=10
 */
router.get('/', listCases);

/**
 * GET /api/cases/search?q=keyword&status=open&priority=high
 */
router.get('/search', [query('q').optional().isString()], searchCasesController);

/**
 * GET /api/cases/:id
 */
router.get('/:id', [param('id').isInt().withMessage('Invalid ID')], getCase);

/**
 * PUT /api/cases/:id
 */
router.put('/:id', [param('id').isInt().withMessage('Invalid ID')], updateCase);

/**
 * DELETE /api/cases/:id
 */
router.delete('/:id', [param('id').isInt().withMessage('Invalid ID')], deleteCase);

export default router;
