# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy workspace files (root tsconfig needed for shared build)
COPY package*.json tsconfig.json ./
COPY shared ./shared
COPY services/auth-service ./services/auth-service

# Install dependencies
RUN npm ci

# Build
RUN npm run build --workspace=shared
RUN npm run build --workspace=services/auth-service

# Production stage
FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY shared/package.json ./shared/
COPY services/auth-service/package.json ./services/auth-service/

# Install production dependencies only
RUN npm ci --production

# Copy built files
COPY --from=builder /app/shared/dist ./shared/dist
COPY --from=builder /app/services/auth-service/dist ./services/auth-service/dist

# Set environment
ENV NODE_ENV=production
ENV PORT=3001

EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3001/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "services/auth-service/dist/index.js"]
