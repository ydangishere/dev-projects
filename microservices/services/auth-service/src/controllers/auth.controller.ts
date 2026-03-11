import { Request, Response, NextFunction } from 'express';
import { validationResult } from 'express-validator';
import {
  hashPassword,
  comparePassword,
  generateToken,
  successResponse,
  errorResponse,
  ConflictError,
  UnauthorizedError,
  ValidationError,
  createLogger,
} from '@microservices/shared';
import { pool } from '../config/database';

const logger = createLogger('auth-controller');

/**
 * Register new user
 * POST /api/auth/register
 */
export async function register(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const { email, password, full_name } = req.body;

    // Check if user exists
    const existingUser = await pool.query('SELECT id FROM users WHERE email = $1', [email]);
    if (existingUser.rows.length > 0) {
      throw new ConflictError('Email already registered');
    }

    // Hash password
    const passwordHash = await hashPassword(password);

    // Insert user
    const result = await pool.query(
      'INSERT INTO users (email, password_hash, full_name, role) VALUES ($1, $2, $3, $4) RETURNING id, email, full_name, role',
      [email, passwordHash, full_name, 'user']
    );

    const user = result.rows[0];
    logger.info('User registered', { userId: user.id, email });

    res.status(201).json(successResponse(user, 'User registered successfully'));
  } catch (error) {
    next(error);
  }
}

/**
 * Login user
 * POST /api/auth/login
 */
export async function login(req: Request, res: Response, next: NextFunction) {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json(errorResponse('Validation failed', JSON.stringify(errors.array())));
    }

    const { email, password } = req.body;

    // Get user
    const result = await pool.query(
      'SELECT id, email, password_hash, full_name, role FROM users WHERE email = $1',
      [email]
    );

    if (result.rows.length === 0) {
      throw new UnauthorizedError('Invalid credentials');
    }

    const user = result.rows[0];

    // Verify password
    const isValid = await comparePassword(password, user.password_hash);
    if (!isValid) {
      throw new UnauthorizedError('Invalid credentials');
    }

    // Generate JWT
    const token = generateToken({
      userId: user.id,
      email: user.email,
      role: user.role,
    });

    logger.info('User logged in', { userId: user.id, email });

    res.json(
      successResponse({
        token,
        user: {
          id: user.id,
          email: user.email,
          full_name: user.full_name,
          role: user.role,
        },
      })
    );
  } catch (error) {
    next(error);
  }
}

/**
 * Get user profile
 * GET /api/auth/profile
 */
export async function getProfile(req: Request, res: Response, next: NextFunction) {
  try {
    const userId = (req as any).user.userId;

    const result = await pool.query(
      'SELECT id, email, full_name, role, created_at FROM users WHERE id = $1',
      [userId]
    );

    if (result.rows.length === 0) {
      throw new UnauthorizedError('User not found');
    }

    res.json(successResponse(result.rows[0]));
  } catch (error) {
    next(error);
  }
}
