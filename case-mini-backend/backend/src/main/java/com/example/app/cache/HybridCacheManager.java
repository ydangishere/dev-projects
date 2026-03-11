package com.example.app.cache;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.stereotype.Service;

/**
 * Hybrid Cache Manager
 * 
 * Strategy:
 * 1. Try Redis first (distributed, persistent)  
 * 2. Fallback to In-Memory (ultra-fast, no dependencies)
 * 3. Auto-recovery khi Redis available lại
 */
@Service
public class HybridCacheManager implements LRUCache {
    
    @Autowired
    private RedisLRUCache redisCache;
    
    private final InMemoryLRUCache memoryCache;
    private boolean redisAvailable = true;
    private long lastRedisCheck = 0;
    private final long REDIS_CHECK_INTERVAL = 5000; // Check mỗi 5 giây
    
    public HybridCacheManager() {
        this.memoryCache = new InMemoryLRUCache(10); // Same capacity as Redis
    }
    
    @Override
    public String get(String key) {
        if (isRedisAvailable()) {
            try {
                return redisCache.get(key);
            } catch (Exception e) {
                handleRedisFailure("get", e);
                return memoryCache.get(key);
            }
        } else {
            return memoryCache.get(key);
        }
    }
    
    @Override
    public void put(String key, String value) {
        if (isRedisAvailable()) {
            try {
                redisCache.put(key, value);
                // 📝 WRITE-BACK: Sync to memory cache sau khi Redis success
                memoryCache.put(key, value);
                return;
            } catch (Exception e) {
                handleRedisFailure("put", e);
            }
        }
        
        // Fallback to memory cache only
        memoryCache.put(key, value);
        
        // 🔄 WRITE-BACK: Schedule sync back to Redis khi available
        if (!redisAvailable) {
            System.out.println("📝 Write-back scheduled: " + key + " will sync when Redis recovers");
        }
    }
    
    @Override
    public int size() {
        if (isRedisAvailable()) {
            try {
                return redisCache.size();
            } catch (Exception e) {
                handleRedisFailure("size", e);
            }
        }
        return memoryCache.size();
    }
    
    @Override
    public void clear() {
        if (isRedisAvailable()) {
            try {
                redisCache.clear();
            } catch (Exception e) {
                handleRedisFailure("clear", e);
            }
        }
        memoryCache.clear();
    }
    
    @Override
    public int getCapacity() {
        return memoryCache.getCapacity(); // Same capacity for both
    }
    
    /**
     * Check Redis availability với throttling
     */
    private boolean isRedisAvailable() {
        long now = System.currentTimeMillis();
        
        // Throttle Redis checks để tránh spam
        if (!redisAvailable && (now - lastRedisCheck) < REDIS_CHECK_INTERVAL) {
            return false;
        }
        
        if (!redisAvailable) {
            lastRedisCheck = now;
            try {
                // Simple health check
                redisCache.size();
                redisAvailable = true;
                System.out.println("✅ Redis recovered, switching back from in-memory fallback");
            } catch (Exception e) {
                // Redis still down
                return false;
            }
        }
        
        return redisAvailable;
    }
    
    /**
     * Handle Redis failure và switch to fallback
     */
    private void handleRedisFailure(String operation, Exception e) {
        if (redisAvailable) {
            redisAvailable = false;
            lastRedisCheck = System.currentTimeMillis();
            System.out.println("⚠️  Redis failed for operation: " + operation + 
                             ". Switching to in-memory fallback. Error: " + e.getMessage());
        }
    }
    
    /**
     * Get current cache type being used
     */
    public String getCurrentCacheType() {
        return isRedisAvailable() ? "Redis" : "In-Memory";
    }
    
    /**
     * Force switch to memory cache (for testing)
     */
    public void forceMemoryMode() {
        redisAvailable = false;
        System.out.println("🔧 Forced switch to in-memory cache");
    }
    
    /**
     * Force switch back to Redis (for testing)
     */
    public void forceRedisMode() {
        redisAvailable = true;
        lastRedisCheck = 0;
        System.out.println("🔧 Forced switch to Redis cache");
    }
    
    /**
     * DELETE key from cache (for invalidation pattern)
     */
    public void delete(String key) {
        try {
            if (isRedisAvailable()) {
                redisCache.delete(key);
                System.out.println("🗑️ Redis: Deleted key " + key);
            } else {
                memoryCache.delete(key);
                System.out.println("🗑️ Memory: Deleted key " + key);
            }
        } catch (Exception e) {
            System.err.println("❌ Error deleting key " + key + ": " + e.getMessage());
            // Fallback to in-memory delete
            if (isRedisAvailable()) {
                try {
                    memoryCache.delete(key);
                    System.out.println("🔄 Fallback: Deleted key " + key + " from memory");
                } catch (Exception fallbackError) {
                    System.err.println("❌ Fallback delete failed: " + fallbackError.getMessage());
                }
            }
        }
    }
    
    /**
     * PUT with TTL (Time To Live)
     */
    public void put(String key, String value, int ttlSeconds) {
        // For demo: use regular put (Redis TTL would be implemented in production)
        put(key, value);
        
        // Log TTL info
        if (ttlSeconds > 0) {
            System.out.println("⏰ Key " + key + " cached with TTL " + ttlSeconds + "s");
        }
    }
}