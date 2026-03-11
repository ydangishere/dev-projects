# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json tsconfig.json ./
COPY shared ./shared
COPY services/people-service ./services/people-service

RUN npm ci
RUN npm run build --workspace=shared
RUN npm run build --workspace=services/people-service

# Production stage
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
COPY shared/package.json ./shared/
COPY services/people-service/package.json ./services/people-service/

RUN npm ci --production

COPY --from=builder /app/shared/dist ./shared/dist
COPY --from=builder /app/services/people-service/dist ./services/people-service/dist

ENV NODE_ENV=production
ENV PORT=3002

EXPOSE 3002

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3002/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "services/people-service/dist/index.js"]
