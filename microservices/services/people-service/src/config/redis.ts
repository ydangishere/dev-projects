import { createClient } from 'redis';
import { createLogger } from '@microservices/shared';

const logger = createLogger('redis');

/**
 * Redis client cho caching
 * Use case: Cache people list, cache individual person
 */
export const redisClient = createClient({
  socket: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT || '6379'),
  },
});

redisClient.on('error', (err) => logger.error('Redis Client Error', { error: err }));

export async function connectRedis(): Promise<void> {
  if (!redisClient.isOpen) {
    await redisClient.connect();
  }
}

/**
 * Cache key patterns
 */
export const CacheKeys = {
  person: (id: number) => `person:${id}`,
  peopleList: (page: number, limit: number) => `people:list:${page}:${limit}`,
};

/**
 * Cache TTL (Time To Live)
 */
export const CacheTTL = {
  person: 3600, // 1 hour
  list: 300, // 5 minutes
};
