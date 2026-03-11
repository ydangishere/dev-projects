import { Request, Response, NextFunction } from 'express';
import { AppError, errorResponse, createLogger } from '@microservices/shared';

const logger = createLogger('error-handler');

export function errorHandler(err: Error, req: Request, res: Response, next: NextFunction) {
  logger.error('Error occurred', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method,
  });

  if (err instanceof AppError) {
    return res.status(err.statusCode).json(errorResponse(err.message));
  }

  res.status(500).json(errorResponse('Internal server error'));
}
