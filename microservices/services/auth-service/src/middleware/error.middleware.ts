import { Request, Response, NextFunction } from 'express';
import { AppError, errorResponse, createLogger } from '@microservices/shared';

const logger = createLogger('error-handler');

/**
 * Global error handler middleware
 */
export function errorHandler(err: Error, req: Request, res: Response, next: NextFunction) {
  logger.error('Error occurred', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method,
  });

  // AppError (known errors)
  if (err instanceof AppError) {
    return res.status(err.statusCode).json(errorResponse(err.message));
  }

  // Unknown errors
  res.status(500).json(errorResponse('Internal server error'));
}
