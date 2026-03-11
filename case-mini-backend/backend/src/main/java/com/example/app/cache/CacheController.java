package com.example.app.cache;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * Advanced Cache Controller với Performance Testing
 */
@RestController
@RequestMapping("/api/cache")
public class CacheController {
    
    @Autowired
    private HybridCacheManager hybridCache;
    
    @Autowired  
    private RedisLRUCache redisCache;
    
    private final InMemoryLRUCache memoryCache = new InMemoryLRUCache(10);
    
    /**
     * GET /api/cache/{key} - Lấy value từ hybrid cache
     */
    @GetMapping("/{key}")
    public Map<String, Object> get(@PathVariable String key) {
        long startTime = System.nanoTime();
        String value = hybridCache.get(key);
        long endTime = System.nanoTime();
        
        Map<String, Object> response = new HashMap<>();
        response.put("key", key);
        response.put("value", value);
        response.put("found", value != null);
        response.put("cacheSize", hybridCache.size());
        response.put("cacheType", hybridCache.getCurrentCacheType());
        response.put("latencyNs", endTime - startTime);
        response.put("latencyMs", (endTime - startTime) / 1_000_000.0);
        
        return response;
    }
    
    /**
     * PUT /api/cache/{key} - Thêm value vào hybrid cache
     */
    @PutMapping("/{key}")
    public Map<String, Object> put(@PathVariable String key, @RequestBody Map<String, String> body) {
        String value = body.get("value");
        
        long startTime = System.nanoTime();
        hybridCache.put(key, value);
        long endTime = System.nanoTime();
        
        Map<String, Object> response = new HashMap<>();
        response.put("key", key);
        response.put("value", value);
        response.put("action", "stored");
        response.put("cacheSize", hybridCache.size());
        response.put("cacheType", hybridCache.getCurrentCacheType());
        response.put("latencyNs", endTime - startTime);
        response.put("latencyMs", (endTime - startTime) / 1_000_000.0);
        
        return response;
    }
    
    /**
     * GET /api/cache/benchmark - Performance comparison
     */
    @GetMapping("/benchmark")
    public Map<String, Object> benchmark() {
        int iterations = 1000;
        
        // Benchmark In-Memory Cache
        long memoryTotal = 0;
        for (int i = 0; i < iterations; i++) {
            long start = System.nanoTime();
            memoryCache.put("test" + i, "value" + i);
            memoryCache.get("test" + i);
            memoryTotal += System.nanoTime() - start;
        }
        
        // Benchmark Redis Cache (if available)
        long redisTotal = 0;
        boolean redisSuccess = true;
        try {
            for (int i = 0; i < iterations; i++) {
                long start = System.nanoTime();
                redisCache.put("test" + i, "value" + i);
                redisCache.get("test" + i);
                redisTotal += System.nanoTime() - start;
            }
        } catch (Exception e) {
            redisSuccess = false;
        }
        
        Map<String, Object> results = new HashMap<>();
        results.put("iterations", iterations);
        results.put("inMemory", Map.of(
            "totalNs", memoryTotal,
            "avgNsPerOp", memoryTotal / iterations,
            "avgMsPerOp", (double) memoryTotal / iterations / 1_000_000
        ));
        
        if (redisSuccess) {
            results.put("redis", Map.of(
                "totalNs", redisTotal,
                "avgNsPerOp", redisTotal / iterations,
                "avgMsPerOp", (double) redisTotal / iterations / 1_000_000,
                "slowdownFactor", (double) redisTotal / memoryTotal
            ));
        } else {
            results.put("redis", Map.of("error", "Redis not available"));
        }
        
        return results;
    }
    
    /**
     * POST /api/cache/switch/memory - Force switch to memory cache
     */
    @PostMapping("/switch/memory")
    public Map<String, String> switchToMemory() {
        hybridCache.forceMemoryMode();
        Map<String, String> response = new HashMap<>();
        response.put("action", "switched");
        response.put("cacheType", "In-Memory");
        response.put("message", "Forced switch to ultra-fast in-memory cache");
        return response;
    }
    
    /**
     * POST /api/cache/switch/redis - Force switch to Redis cache  
     */
    @PostMapping("/switch/redis")
    public Map<String, String> switchToRedis() {
        hybridCache.forceRedisMode();
        Map<String, String> response = new HashMap<>();
        response.put("action", "switched");
        response.put("cacheType", "Redis");
        response.put("message", "Forced switch to distributed Redis cache");
        return response;
    }
}