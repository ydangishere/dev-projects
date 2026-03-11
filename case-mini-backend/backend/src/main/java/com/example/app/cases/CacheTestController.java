package com.example.app.cases;

import com.example.app.cases.dto.CaseResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

/**
 * CACHE TEST CONTROLLER - Test Cache Patterns
 * 
 * 🧪 ENDPOINTS:
 * - GET /api/cache/test/case/{id} → Test read-through cache
 * - POST /api/cache/test/warm-up/{id} → Warm up cache  
 * - DELETE /api/cache/test/invalidate/{id} → Test invalidation
 * - GET /api/cache/test/stampede/{id} → Test anti-stampede
 * - GET /api/cache/test/stats → Cache statistics
 */
@RestController
@RequestMapping("/api/cache/test")
public class CacheTestController {
    
    private final CaseCacheService cacheService;
    private final CaseService caseService;
    private final PerformanceBenchmark benchmark;
    
    public CacheTestController(CaseCacheService cacheService, CaseService caseService, PerformanceBenchmark benchmark) {
        this.cacheService = cacheService;
        this.caseService = caseService;
        this.benchmark = benchmark;
    }
    
    /**
     * TEST READ-THROUGH CACHE PATTERN
     * First call: Cache miss → DB query → cache result  
     * Second call: Cache hit → return from cache
     */
    @GetMapping("/case/{id}")
    public ResponseEntity<TestResult> testReadThrough(@PathVariable Long id) {
        long startTime = System.currentTimeMillis();
        
        // First call (should be cache miss)
        long firstCallStart = System.currentTimeMillis();
        Optional<CaseResponse> firstResult = cacheService.getCachedCase(id);
        long firstCallTime = System.currentTimeMillis() - firstCallStart;
        
        // Small delay
        try { Thread.sleep(10); } catch (InterruptedException e) {}
        
        // Second call (should be cache hit)  
        long secondCallStart = System.currentTimeMillis();
        Optional<CaseResponse> secondResult = cacheService.getCachedCase(id);
        long secondCallTime = System.currentTimeMillis() - secondCallStart;
        
        long totalTime = System.currentTimeMillis() - startTime;
        
        TestResult result = new TestResult(
            "read-through-cache",
            firstResult.isPresent() && secondResult.isPresent(),
            totalTime,
            String.format("First call (miss): %dms, Second call (hit): %dms. Cache hit should be faster!", 
                        firstCallTime, secondCallTime)
        );
        
        return ResponseEntity.ok(result);
    }
    
    /**
     * TEST CACHE WARM-UP
     */
    @PostMapping("/warm-up/{id}")
    public ResponseEntity<TestResult> testWarmUp(@PathVariable Long id) {
        long startTime = System.currentTimeMillis();
        
        try {
            cacheService.warmUpCache(id);
            long duration = System.currentTimeMillis() - startTime;
            
            TestResult result = new TestResult(
                "cache-warm-up",
                true,
                duration,
                "Cache warmed up for case " + id
            );
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            TestResult result = new TestResult(
                "cache-warm-up",
                false,
                System.currentTimeMillis() - startTime,
                "Warm-up failed: " + e.getMessage()
            );
            
            return ResponseEntity.ok(result);
        }
    }
    
    /**
     * TEST CACHE INVALIDATION PATTERN
     * Cache case → invalidate → verify cache miss on next read
     */
    @DeleteMapping("/invalidate/{id}")
    public ResponseEntity<TestResult> testInvalidation(@PathVariable Long id) {
        long startTime = System.currentTimeMillis();
        
        try {
            // Step 1: Warm up cache
            cacheService.getCachedCase(id);
            
            // Step 2: Invalidate
            cacheService.invalidateCase(id);
            
            // Step 3: Next call should be cache miss  
            long missStart = System.currentTimeMillis();
            Optional<CaseResponse> result = cacheService.getCachedCase(id);
            long missTime = System.currentTimeMillis() - missStart;
            
            long totalTime = System.currentTimeMillis() - startTime;
            
            TestResult testResult = new TestResult(
                "cache-invalidation",
                result.isPresent(),
                totalTime,
                String.format("Cache invalidated for case %d. Next read took %dms (should show cache miss in logs)", 
                            id, missTime)
            );
            
            return ResponseEntity.ok(testResult);
            
        } catch (Exception e) {
            TestResult result = new TestResult(
                "cache-invalidation",
                false,
                System.currentTimeMillis() - startTime,
                "Invalidation test failed: " + e.getMessage()
            );
            
            return ResponseEntity.ok(result);
        }
    }
    
    /**
     * TEST ANTI-STAMPEDE PATTERN
     * Simulate multiple concurrent requests for same key
     */
    @GetMapping("/stampede/{id}")
    public ResponseEntity<TestResult> testAntiStampede(@PathVariable Long id) {
        long startTime = System.currentTimeMillis();
        
        try {
            // Invalidate first to ensure cache miss
            cacheService.invalidateCase(id);
            
            // Simulate 5 concurrent requests
            List<CompletableFuture<Optional<CaseResponse>>> futures = new ArrayList<>();
            
            for (int i = 0; i < 5; i++) {
                CompletableFuture<Optional<CaseResponse>> future = CompletableFuture.supplyAsync(() -> {
                    return cacheService.getCachedCase(id);
                });
                futures.add(future);
            }
            
            // Wait for all requests to complete
            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0]))
                           .get(10, TimeUnit.SECONDS);
            
            long totalTime = System.currentTimeMillis() - startTime;
            
            TestResult result = new TestResult(
                "anti-stampede",
                true,
                totalTime,
                "5 concurrent requests completed. Check logs - only 1 DB query should occur (anti-stampede protection)"
            );
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            TestResult result = new TestResult(
                "anti-stampede",
                false,
                System.currentTimeMillis() - startTime,
                "Anti-stampede test failed: " + e.getMessage()
            );
            
            return ResponseEntity.ok(result);
        }
    }
    
    /**
     * TEST WRITE-THROUGH PATTERN (Update + Invalidation)
     */
    @PutMapping("/write-through/{id}")
    public ResponseEntity<TestResult> testWriteThrough(@PathVariable Long id, 
                                                      @RequestParam String newStatus) {
        long startTime = System.currentTimeMillis();
        
        try {
            // Step 1: Warm up cache
            cacheService.getCachedCase(id);
            
            // Step 2: Update case (should invalidate cache)
            CaseResponse updated = caseService.updateCaseStatus(id, newStatus);
            
            // Step 3: Read again (should be cache miss → fresh data)
            long freshReadStart = System.currentTimeMillis();
            Optional<CaseResponse> freshResult = cacheService.getCachedCase(id);
            long freshReadTime = System.currentTimeMillis() - freshReadStart;
            
            long totalTime = System.currentTimeMillis() - startTime;
            
            boolean success = freshResult.isPresent() && 
                            freshResult.get().getStatus().equals(newStatus);
            
            TestResult result = new TestResult(
                "write-through",
                success,
                totalTime,
                String.format("Case %d updated to status '%s'. Fresh read took %dms (should show cache miss in logs)", 
                            id, newStatus, freshReadTime)
            );
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            TestResult result = new TestResult(
                "write-through",
                false,
                System.currentTimeMillis() - startTime,
                "Write-through test failed: " + e.getMessage()
            );
            
            return ResponseEntity.ok(result);
        }
    }
    
    /**
     * GET CACHE STATISTICS
     */
    @GetMapping("/stats")
    public ResponseEntity<CaseCacheService.CacheStats> getCacheStats() {
        return ResponseEntity.ok(cacheService.getCacheStats());
    }
    
    /**
     * RUN P95 PERFORMANCE BENCHMARK
     * Test WITHOUT cache vs WITH cache để đo improvement
     */
    @GetMapping("/p95-benchmark/{id}")
    public ResponseEntity<PerformanceBenchmark.BenchmarkResult> runP95Benchmark(
            @PathVariable Long id,
            @RequestParam(defaultValue = "50") int iterations) {
        
        long startTime = System.currentTimeMillis();
        
        try {
            System.out.printf("🚀 Starting P95 benchmark for case %d with %d iterations%n", id, iterations);
            
            PerformanceBenchmark.BenchmarkResult result = benchmark.runPerformanceBenchmark(id, iterations);
            
            long totalTime = System.currentTimeMillis() - startTime;
            System.out.printf("✅ P95 benchmark completed in %dms%n", totalTime);
            
            result.printSummary();
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            System.err.printf("❌ P95 benchmark failed: %s%n", e.getMessage());
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * RUN CONCURRENT LOAD BENCHMARK (Anti-Stampede)
     */
    @GetMapping("/concurrent-benchmark/{id}")
    public ResponseEntity<PerformanceBenchmark.ConcurrentBenchmarkResult> runConcurrentBenchmark(
            @PathVariable Long id,
            @RequestParam(defaultValue = "10") int concurrency) {
        
        long startTime = System.currentTimeMillis();
        
        try {
            System.out.printf("⚡ Starting concurrent benchmark for case %d with %d threads%n", id, concurrency);
            
            PerformanceBenchmark.ConcurrentBenchmarkResult result = benchmark.runConcurrentBenchmark(id, concurrency);
            
            long totalTime = System.currentTimeMillis() - startTime;
            System.out.printf("✅ Concurrent benchmark completed in %dms%n", totalTime);
            
            result.printSummary();
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            System.err.printf("❌ Concurrent benchmark failed: %s%n", e.getMessage());
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * Test Result DTO
     */
    public static class TestResult {
        public final String testName;
        public final boolean success;
        public final long durationMs;
        public final String description;
        public final long timestamp;
        
        public TestResult(String testName, boolean success, long durationMs, String description) {
            this.testName = testName;
            this.success = success;
            this.durationMs = durationMs;
            this.description = description;
            this.timestamp = System.currentTimeMillis();
        }
    }
}