import express from 'express';
import dotenv from 'dotenv';
import { createLogger } from '@microservices/shared';
import { dbConnect } from './config/database';
import { redisClient, connectRedis } from './config/redis';
import { kafkaProducer, connectKafka } from './config/kafka';
import peopleRoutes from './routes/people.routes';
import { errorHandler } from './middleware/error.middleware';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3002;
const logger = createLogger('people-service');

// Middleware
app.use(express.json());
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// Health check
app.get('/health', async (req, res) => {
  const redisStatus = redisClient.isOpen ? 'connected' : 'disconnected';
  res.json({
    status: 'ok',
    service: 'people-service',
    redis: redisStatus,
  });
});

// Routes
app.use('/api/people', peopleRoutes);

// Error handler
app.use(errorHandler);

// Start server
async function start() {
  try {
    await dbConnect();
    logger.info('Database connected');

    await connectRedis();
    logger.info('Redis connected');

    await connectKafka();
    logger.info('Kafka connected');

    app.listen(PORT, () => {
      logger.info(`People Service running on port ${PORT}`);
    });
  } catch (error) {
    logger.error('Failed to start server', { error });
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully');
  await redisClient.quit();
  await kafkaProducer.disconnect();
  process.exit(0);
});

start();
