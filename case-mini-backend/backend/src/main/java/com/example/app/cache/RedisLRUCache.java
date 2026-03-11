package com.example.app.cache;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.connection.RedisConnection;
import org.springframework.stereotype.Service;

import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Redis-based LRU Cache Implementation
 * 
 * Trade-offs so với Custom LRU:
 * ✅ Production-ready, battle-tested
 * ✅ Distributed caching support
 * ✅ Persistence và clustering
 * ❌ Network latency
 * ❌ External dependency
 */
@Service
public class RedisLRUCache implements LRUCache {
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    private final int capacity;
    private final String CACHE_PREFIX = "lru:";
    private final String USAGE_ZSET = "lru:usage"; // Sorted set để track usage order
    
    public RedisLRUCache() {
        this.capacity = 10; // Default capacity
    }
    
    public RedisLRUCache(int capacity) {
        this.capacity = capacity;
    }
    
    @Override
    public String get(String key) {
        String cacheKey = CACHE_PREFIX + key;
        String value = redisTemplate.opsForValue().get(cacheKey);
        
        if (value != null) {
            // Update access time (LRU tracking)
            long currentTime = System.currentTimeMillis();
            redisTemplate.opsForZSet().add(USAGE_ZSET, key, currentTime);
        }
        
        return value;
    }
    
    @Override
    public void put(String key, String value) {
        String cacheKey = CACHE_PREFIX + key;
        long currentTime = System.currentTimeMillis();
        
        // 🔒 ATOMIC: Use Redis transaction để đảm bảo consistency
        redisTemplate.execute((RedisCallback<Void>) connection -> {
            connection.multi(); // Start transaction
            
            try {
                // Check if key already exists
                boolean keyExists = Boolean.TRUE.equals(redisTemplate.hasKey(cacheKey));
                
                if (!keyExists) {
                    // Check capacity and evict if necessary (atomic)
                    evictIfNecessaryAtomic(connection);
                }
                
                // Set the value and update usage (atomic)
                redisTemplate.opsForValue().set(cacheKey, value);
                redisTemplate.opsForZSet().add(USAGE_ZSET, key, currentTime);
                
                connection.exec(); // Execute transaction
                return null;
            } catch (Exception e) {
                connection.discard(); // Rollback on error
                throw e;
            }
        });
    }
    
    private void evictIfNecessaryAtomic(RedisConnection connection) {
        long currentSize = getCurrentSize();
        
        if (currentSize >= capacity) {
            // Get least recently used key (lowest score in sorted set)
            Set<String> lruKeys = redisTemplate.opsForZSet().range(USAGE_ZSET, 0, 0);
            
            if (!lruKeys.isEmpty()) {
                String lruKey = lruKeys.iterator().next();
                
                // 🔒 ATOMIC: Remove from cache and usage tracking
                redisTemplate.delete(CACHE_PREFIX + lruKey);
                redisTemplate.opsForZSet().remove(USAGE_ZSET, lruKey);
                
                System.out.println("🗑️  Evicted LRU key atomically: " + lruKey);
            }
        }
    }
    
    private long getCurrentSize() {
        Long size = redisTemplate.opsForZSet().count(USAGE_ZSET, Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY);
        return size != null ? size : 0;
    }
    
    @Override
    public int size() {
        return (int) getCurrentSize();
    }
    
    @Override
    public void clear() {
        // Get all keys in usage tracking
        Set<String> allKeys = redisTemplate.opsForZSet().range(USAGE_ZSET, 0, -1);
        
        if (allKeys != null && !allKeys.isEmpty()) {
            // Delete all cache entries
            for (String key : allKeys) {
                redisTemplate.delete(CACHE_PREFIX + key);
            }
        }
        
        // Clear usage tracking
        redisTemplate.delete(USAGE_ZSET);
        
        System.out.println("🧹 Redis LRU Cache cleared");
    }
    
    @Override
    public void delete(String key) {
        try {
            String cacheKey = CACHE_PREFIX + key;
            
            // Delete from both cache key and usage tracking set
            redisTemplate.delete(cacheKey);
            redisTemplate.opsForZSet().remove(USAGE_ZSET, key);
            
            System.out.println("🗑️ Redis: Deleted " + key);
        } catch (Exception e) {
            System.err.println("❌ Redis delete failed for " + key + ": " + e.getMessage());
            throw e;
        }
    }
    
    @Override
    public int getCapacity() {
        return capacity;
    }
    
    /**
     * Debug method để xem usage order
     */
    public void printUsageOrder() {
        Set<String> keys = redisTemplate.opsForZSet().range(USAGE_ZSET, 0, -1);
        System.out.println("📊 LRU Usage Order (oldest → newest): " + keys);
    }
}