import redis
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


def get_cache(key: str):
    """Get value from Redis cache"""
    if not redis_client:
        logger.warning("Redis client not available, skipping cache")
        return None
    try:
        value = redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
        return None


def set_cache(key: str, value: any, ttl: int = 60):
    """Set value in Redis cache with TTL"""
    if not redis_client:
        logger.warning("Redis client not available, skipping cache")
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value))
        logger.debug(f"Cached key: {key} with TTL: {ttl}s")
    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")
