import express from 'express';
import dotenv from 'dotenv';
import { createLogger } from '@microservices/shared';
import { dbConnect } from './config/database';
import { esClient, connectElasticsearch, initializeIndex } from './config/elasticsearch';
import { connectKafka, startConsumer } from './config/kafka';
import caseRoutes from './routes/case.routes';
import { errorHandler } from './middleware/error.middleware';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3003;
const logger = createLogger('case-service');

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
  try {
    const esHealth = await esClient.cluster.health();
    res.json({
      status: 'ok',
      service: 'case-service',
      elasticsearch: esHealth.status,
    });
  } catch (error) {
    res.json({ status: 'ok', service: 'case-service', elasticsearch: 'error' });
  }
});

// Routes
app.use('/api/cases', caseRoutes);

// Error handler
app.use(errorHandler);

// Start server
async function start() {
  try {
    await dbConnect();
    logger.info('Database connected');

    await connectElasticsearch();
    await initializeIndex();
    logger.info('Elasticsearch connected and index initialized');

    await connectKafka();
    logger.info('Kafka connected');

    // Start Kafka consumer trong background
    startConsumer().catch((error) => {
      logger.error('Kafka consumer error', { error });
    });

    app.listen(PORT, () => {
      logger.info(`Case Service running on port ${PORT}`);
    });
  } catch (error) {
    logger.error('Failed to start server', { error });
    process.exit(1);
  }
}

start();
