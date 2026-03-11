import { Router } from 'express';
import { body, param } from 'express-validator';
import {
  createPerson,
  getPerson,
  listPeople,
  updatePerson,
  deletePerson,
} from '../controllers/people.controller';
import { authenticate } from '../middleware/auth.middleware';

const router = Router();

// Tất cả routes đều cần authentication
router.use(authenticate);

/**
 * POST /api/people
 * Body: { first_name, last_name, email, phone, address }
 */
router.post(
  '/',
  [
    body('first_name').notEmpty().withMessage('First name is required'),
    body('last_name').notEmpty().withMessage('Last name is required'),
    body('email').optional().isEmail().withMessage('Invalid email'),
    body('phone').optional().isString(),
    body('address').optional().isString(),
  ],
  createPerson
);

/**
 * GET /api/people?page=1&limit=10
 */
router.get('/', listPeople);

/**
 * GET /api/people/:id
 */
router.get('/:id', [param('id').isInt().withMessage('Invalid ID')], getPerson);

/**
 * PUT /api/people/:id
 */
router.put(
  '/:id',
  [
    param('id').isInt().withMessage('Invalid ID'),
    body('first_name').optional().notEmpty(),
    body('last_name').optional().notEmpty(),
    body('email').optional().isEmail(),
  ],
  updatePerson
);

/**
 * DELETE /api/people/:id
 */
router.delete('/:id', [param('id').isInt().withMessage('Invalid ID')], deletePerson);

export default router;
