import { Request, Response, NextFunction } from 'express';
import { extractToken, verifyToken, UnauthorizedError } from '@microservices/shared';

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

    (req as any).user = decoded;
    next();
  } catch (error) {
    next(error);
  }
}
