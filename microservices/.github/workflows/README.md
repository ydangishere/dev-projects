# CI/CD Pipeline

## Pipeline Flow

### 1. CI Pipeline (Continuous Integration)
Trigger: PR hoặc push lên `main`/`develop`

**Stages:**
1. **Lint and Unit Tests**
   - Install dependencies
   - Build shared package
   - Run unit tests
   - Upload coverage

2. **Integration Tests**
   - Spin up PostgreSQL, Redis (GitHub Actions services)
   - Run integration tests
   - Verify services integration

3. **Build Docker** (chỉ khi merge vào main)
   - Build Docker images cho 3 services
   - Push lên Docker Hub với tags: `latest` và `git-sha`

### 2. Deploy Pipeline (Continuous Delivery)
Trigger: Sau khi CI Pipeline pass

**Stages:**
1. **Deploy to Staging**
   - Deploy services lên staging environment
   - Run smoke tests
   - Notify team

2. **Deploy to Production** (manual approval required)
   - Blue-green deployment
   - Health checks
   - Monitor metrics
   - Keep rollback point

## Metrics Tracked

### Build Metrics
- **Build time**: CI pipeline duration
- **Test pass rate**: % tests thành công
- **Coverage**: Code coverage %

### Deployment Metrics
- **Deploy frequency**: Số lần deploy/ngày
- **Lead time**: Thời gian từ commit → production
- **Change failure rate**: % deploy bị rollback
- **MTTR**: Mean Time To Recovery

## Setup Required

### GitHub Secrets
```
DOCKER_USERNAME=your-docker-username
DOCKER_PASSWORD=your-docker-password
```

### Production Environment Variables
```
DB_HOST=production-db-host
JWT_SECRET=strong-production-secret
KAFKA_BROKERS=prod-kafka-1:9092,prod-kafka-2:9092
```

## Rollback Strategy

Nếu deployment fail:
1. Health check fail → Auto rollback
2. Error rate spike → Manual rollback
3. Rollback command:
   ```bash
   # Revert to previous Docker image tag
   docker-compose pull --tag=<previous-sha>
   docker-compose up -d
   ```

## Monitoring After Deploy

- Check logs: `npm run docker:logs`
- Monitor metrics: Grafana dashboard
- Alert thresholds:
  - Error rate > 5%
  - Latency P95 > 500ms
  - Kafka consumer lag > 1000
