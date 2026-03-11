# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
COPY shared ./shared
COPY services/case-service ./services/case-service

RUN npm ci
RUN npm run build --workspace=shared
RUN npm run build --workspace=services/case-service

# Production stage
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
COPY shared/package.json ./shared/
COPY services/case-service/package.json ./services/case-service/

RUN npm ci --production

COPY --from=builder /app/shared/dist ./shared/dist
COPY --from=builder /app/services/case-service/dist ./services/case-service/dist

ENV NODE_ENV=production
ENV PORT=3003

EXPOSE 3003

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3003/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

CMD ["node", "services/case-service/dist/index.js"]
