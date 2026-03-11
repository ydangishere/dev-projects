import express from 'express';
import dotenv from 'dotenv';
import { createLogger } from '@microservices/shared';
import { dbConnect } from './config/database';
import authRoutes from './routes/auth.routes';
import { errorHandler } from './middleware/error.middleware';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;
const logger = createLogger('auth-service');

// Middleware
app.use(express.json());
// CORS - allow Admin UI (file:// or localhost) to call API
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'auth-service' });
});

// Routes
app.use('/api/auth', authRoutes);

// Error handler (phải để cuối cùng)
app.use(errorHandler);

// Start server
async function start() {
  try {
    await dbConnect();
    logger.info('Database connected');

    app.listen(PORT, () => {
      logger.info(`Auth Service running on port ${PORT}`);
    });
  } catch (error) {
    logger.error('Failed to start server', { error });
    process.exit(1);
  }
}

start();
