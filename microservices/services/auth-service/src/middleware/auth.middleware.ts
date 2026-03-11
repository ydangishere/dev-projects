import { Request, Response, NextFunction } from 'express';
import { extractToken, verifyToken, UnauthorizedError } from '@microservices/shared';

/**
 * Middleware xác thực JWT token
 * Attach user info vào req.user
 */
export function authenticate(req: Request, res: Response, next: NextFunction) {
  try {
    const token = extractToken(req.headers.authorization);
    if (!token) {
      throw new UnauthorizedError('No token provided');
    }

    const decoded = verifyToken(token);
    if (!decoded) {
      throw new UnauthorizedError('Invalid or expired token');
    }

    // Attach user info vào request
    (req as any).user = decoded;
    next();
  } catch (error) {
    next(error);
  }
}

/**
 * Middleware check role
 * Dùng sau authenticate middleware
 */
export function authorize(...allowedRoles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    const user = (req as any).user;
    if (!user || !allowedRoles.includes(user.role)) {
      return next(new UnauthorizedError('Insufficient permissions'));
    }
    next();
  };
}
