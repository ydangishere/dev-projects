import * as jwt from 'jsonwebtoken';
import type { SignOptions } from 'jsonwebtoken';
import { JwtPayload } from './types';

const JWT_SECRET: string = process.env.JWT_SECRET || 'your-secret-key-change-in-production';
const JWT_EXPIRES_IN: string = process.env.JWT_EXPIRES_IN || '24h';

/**
 * Generate JWT token từ user payload
 * @param payload - User data để mã hóa vào token
 * @returns JWT token string
 */
export function generateToken(payload: JwtPayload): string {
  return jwt.sign(payload as object, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN } as SignOptions);
}

/**
 * Verify và decode JWT token
 * @param token - JWT token string
 * @returns Decoded payload hoặc null nếu invalid
 */
export function verifyToken(token: string): JwtPayload | null {
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as JwtPayload;
    return decoded;
  } catch (error) {
    return null;
  }
}

/**
 * Extract token từ Authorization header
 * @param authHeader - Authorization header (format: "Bearer <token>")
 * @returns Token string hoặc null
 */
export function extractToken(authHeader?: string): string | null {
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  return authHeader.substring(7);
}
