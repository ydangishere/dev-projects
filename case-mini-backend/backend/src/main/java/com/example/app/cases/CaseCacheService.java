package com.example.app.cases;

import com.example.app.cases.dto.CaseResponse;
import com.example.app.cache.HybridCacheManager;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;

/**
 * CASE CACHE SERVICE - Read-through + Write-through + Anti-Stampede
 * 
 * 🎯 PATTERNS IMPLEMENTED:
 * 1. Read-through: Cache miss → query DB → cache result
 * 2. Write-through/Invalidation: Update case → invalidate cache
 * 3. Anti-stampede: Lock per key để tránh thundering herd
 * 
 * 🔑 KEY DESIGN: case:{id}:v{version}
 * 📊 TTL: 60-300s tùy business requirement
 */
@Service
public class CaseCacheService {
    
    private final HybridCacheManager cacheManager;
    private final CaseRepository caseRepository;
    private final ObjectMapper objectMapper;
    
    // Anti-stampede: Lock per key
    private final ConcurrentHashMap<String, ReentrantLock> keyLocks = new ConcurrentHashMap<>();
    
    // Cache configuration
    private static final int CACHE_TTL_SECONDS = 180; // 3 minutes
    private static final String CACHE_KEY_PREFIX = "case:";
    private static final String CACHE_VERSION = "v1";
    
    public CaseCacheService(HybridCacheManager cacheManager, 
                           CaseRepository caseRepository) {
        this.cacheManager = cacheManager;
        this.caseRepository = caseRepository;
        this.objectMapper = new ObjectMapper();
    }
    
    /**
     * READ-THROUGH CACHE PATTERN
     * 
     * 🔄 FLOW:
     * 1. Try cache hit với key case:{id}:v1
     * 2. Cache miss → acquire lock per key (anti-stampede)
     * 3. Double-check cache (có thể thread khác đã cache)
     * 4. Query DB → serialize → cache với TTL
     * 5. Return result
     */
    public Optional<CaseResponse> getCachedCase(Long caseId) {
        String cacheKey = buildCacheKey(caseId);
        
        try {
            // STEP 1: Try cache hit
            String cachedValue = cacheManager.get(cacheKey);
            if (cachedValue != null) {
                System.out.println("🎯 Cache HIT for case " + caseId);
                return Optional.of(deserializeCaseResponse(cachedValue));
            }
            
            // STEP 2: Cache miss → acquire lock (anti-stampede)
            ReentrantLock lock = keyLocks.computeIfAbsent(cacheKey, k -> new ReentrantLock());
            
            lock.lock();
            try {
                // STEP 3: Double-check cache (có thể thread khác đã cache)
                cachedValue = cacheManager.get(cacheKey);
                if (cachedValue != null) {
                    System.out.println("🎯 Cache HIT after lock for case " + caseId);
                    return Optional.of(deserializeCaseResponse(cachedValue));
                }
                
                // STEP 4: Query DB
                System.out.println("💽 Cache MISS → Query DB for case " + caseId);
                Optional<CaseEntity> caseEntity = caseRepository.findById(caseId);
                
                if (caseEntity.isEmpty()) {
                    // Cache negative result (short TTL)
                    cacheManager.put(cacheKey, "NULL", 30); // 30 seconds for NULL
                    return Optional.empty();
                }
                
                // STEP 5: Serialize and cache result
                CaseResponse caseResponse = CaseResponse.from(caseEntity.get());
                String serializedValue = serializeCaseResponse(caseResponse);
                
                cacheManager.put(cacheKey, serializedValue, CACHE_TTL_SECONDS);
                
                System.out.println("✅ Cached case " + caseId + " with TTL " + CACHE_TTL_SECONDS + "s");
                
                return Optional.of(caseResponse);
                
            } finally {
                lock.unlock();
            }
            
        } catch (Exception e) {
            System.err.println("❌ Cache error for case " + caseId + ": " + e.getMessage());
            
            // Fallback to DB (cache failure shouldn't break app)
            return caseRepository.findById(caseId).map(CaseResponse::from);
        }
    }
    
    /**
     * WRITE-THROUGH / INVALIDATION PATTERN
     * 
     * 🔄 Khi update case → invalidate cache để tránh stale data
     */
    public void invalidateCase(Long caseId) {
        String cacheKey = buildCacheKey(caseId);
        
        try {
            cacheManager.delete(cacheKey);
            System.out.println("🗑️  Invalidated cache for case " + caseId);
            
        } catch (Exception e) {
            System.err.println("⚠️  Failed to invalidate cache for case " + caseId + ": " + e.getMessage());
            // Non-critical error, continue execution
        }
    }
    
    /**
     * WARM-UP CACHE (preload popular cases)
     */
    public void warmUpCache(Long caseId) {
        System.out.println("🔥 Warming up cache for case " + caseId);
        getCachedCase(caseId); // This will cache the result
    }
    
    /**
     * CACHE STATISTICS
     */
    public CacheStats getCacheStats() {
        // Simplified stats - in production would track hits/misses
        int totalLocks = keyLocks.size();
        return new CacheStats(totalLocks, CACHE_TTL_SECONDS);
    }
    
    // Helper methods
    private String buildCacheKey(Long caseId) {
        return CACHE_KEY_PREFIX + caseId + ":" + CACHE_VERSION;
    }
    
    private String serializeCaseResponse(CaseResponse caseResponse) {
        try {
            return objectMapper.writeValueAsString(caseResponse);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize CaseResponse", e);
        }
    }
    
    private CaseResponse deserializeCaseResponse(String json) {
        if ("NULL".equals(json)) {
            return null; // Negative cache result
        }
        
        try {
            return objectMapper.readValue(json, CaseResponse.class);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to deserialize CaseResponse", e);
        }
    }
    
    /**
     * Stats DTO
     */
    public static class CacheStats {
        public final int activeLocks;
        public final int ttlSeconds;
        
        public CacheStats(int activeLocks, int ttlSeconds) {
            this.activeLocks = activeLocks;
            this.ttlSeconds = ttlSeconds;
        }
        
        @Override
        public String toString() {
            return String.format("CacheStats{activeLocks=%d, ttlSeconds=%d}", 
                               activeLocks, ttlSeconds);
        }
    }
}