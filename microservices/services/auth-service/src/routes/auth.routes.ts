import { Router } from 'express';
import { body } from 'express-validator';
import { register, login, getProfile } from '../controllers/auth.controller';
import { authenticate } from '../middleware/auth.middleware';

const router = Router();

/**
 * POST /api/auth/register
 * Body: { email, password, full_name }
 */
router.post(
  '/register',
  [
    body('email').isEmail().withMessage('Invalid email'),
    body('password').isLength({ min: 6 }).withMessage('Password must be at least 6 characters'),
    body('full_name').optional().isString(),
  ],
  register
);

/**
 * POST /api/auth/login
 * Body: { email, password }
 */
router.post(
  '/login',
  [
    body('email').isEmail().withMessage('Invalid email'),
    body('password').notEmpty().withMessage('Password is required'),
  ],
  login
);

/**
 * GET /api/auth/profile
 * Header: Authorization: Bearer <token>
 */
router.get('/profile', authenticate, getProfile);

export default router;
