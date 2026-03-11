# Infrastructure Setup

## Components

### PostgreSQL (Port 5432)
- **Mục đích**: Database chính cho các services
- **Databases**: `auth_db`, `people_db`, `case_db` (mỗi service có DB riêng)
- **Credentials**: user=`admin`, password=`admin123`

### Redis (Port 6379)
- **Mục đích**: Cache dữ liệu đọc thường xuyên, giảm DB load
- **Use case**: Cache user profile, cache people list

### Kafka (Port 9092)
- **Mục đích**: Event streaming giữa services (async communication)
- **Topics**: `people.created`, `people.updated`, `case.created`
- **Zookeeper**: Port 2181

### Elasticsearch (Port 9200)
- **Mục đích**: Full-text search, filter phức tạp
- **Use case**: Search cases theo title/description
- **Kibana UI**: http://localhost:5601

## Commands

### Start tất cả services
```bash
cd d:\microservices
npm run docker:up
```

### Stop tất cả services
```bash
npm run docker:down
```

### Xem logs
```bash
npm run docker:logs
```

### Check health
```bash
# PostgreSQL
docker exec ms-postgres pg_isready -U admin

# Redis
docker exec ms-redis redis-cli ping

# Kafka
docker exec ms-kafka kafka-topics --list --bootstrap-server localhost:9092

# Elasticsearch
curl http://localhost:9200/_cluster/health
```

## Metrics để monitor

- **Kafka**: consumer lag, retry count, processing time
- **Redis**: cache hit rate, eviction rate
- **Elasticsearch**: search latency, index lag
- **PostgreSQL**: connection pool, query time
