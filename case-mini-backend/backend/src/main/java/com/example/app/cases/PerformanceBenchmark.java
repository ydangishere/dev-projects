package com.example.app.cases;

import com.example.app.cases.dto.CaseResponse;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * PERFORMANCE BENCHMARK - Đo P95 improvement với cache
 * 
 * 🎯 TEST SCENARIOS:
 * 1. WITHOUT cache: Direct DB queries
 * 2. WITH cache: Read-through cache pattern
 * 3. Concurrent load: Anti-stampede test
 */
@Service
public class PerformanceBenchmark {
    
    private final CaseService caseService;
    private final CaseCacheService cacheService;
    private final CaseRepository caseRepository;
    
    public PerformanceBenchmark(CaseService caseService, 
                               CaseCacheService cacheService, 
                               CaseRepository caseRepository) {
        this.caseService = caseService;
        this.cacheService = cacheService;
        this.caseRepository = caseRepository;
    }
    
    /**
     * BENCHMARK: WITHOUT CACHE vs WITH CACHE
     * Đo P50, P95, P99 latency improvements
     */
    public BenchmarkResult runPerformanceBenchmark(Long caseId, int iterations) {
        System.out.println("🏁 Starting Performance Benchmark...");
        
        // Phase 1: WITHOUT CACHE (Direct DB)
        System.out.println("📊 Phase 1: Direct DB queries (no cache)");
        List<Long> noCacheLatencies = benchmarkDirectDB(caseId, iterations);
        
        // Small pause between phases
        try { Thread.sleep(1000); } catch (InterruptedException e) {}
        
        // Phase 2: WITH CACHE (Read-through)
        System.out.println("📊 Phase 2: Read-through cache queries");
        List<Long> withCacheLatencies = benchmarkWithCache(caseId, iterations);
        
        // Calculate percentiles
        PerformanceMetrics noCacheMetrics = calculateMetrics(noCacheLatencies, "No Cache");
        PerformanceMetrics withCacheMetrics = calculateMetrics(withCacheLatencies, "With Cache");
        
        return new BenchmarkResult(noCacheMetrics, withCacheMetrics);
    }
    
    /**
     * BENCHMARK: Direct DB queries
     */
    private List<Long> benchmarkDirectDB(Long caseId, int iterations) {
        List<Long> latencies = new ArrayList<>();
        
        for (int i = 0; i < iterations; i++) {
            long startTime = System.nanoTime();
            
            // Direct DB query (bypass cache)
            Optional<CaseResponse> result = caseRepository.findById(caseId)
                                                        .map(CaseResponse::from);
            
            long latencyNanos = System.nanoTime() - startTime;
            latencies.add(latencyNanos / 1_000_000); // Convert to milliseconds
            
            // Small delay between requests
            try { Thread.sleep(10); } catch (InterruptedException e) {}
        }
        
        return latencies;
    }
    
    /**
     * BENCHMARK: With cache (read-through)
     */
    private List<Long> benchmarkWithCache(Long caseId, int iterations) {
        List<Long> latencies = new ArrayList<>();
        
        // First request will be cache miss
        // Subsequent requests will be cache hits
        
        for (int i = 0; i < iterations; i++) {
            long startTime = System.nanoTime();
            
            // Use cache service (read-through pattern)
            Optional<CaseResponse> result = cacheService.getCachedCase(caseId);
            
            long latencyNanos = System.nanoTime() - startTime;
            latencies.add(latencyNanos / 1_000_000); // Convert to milliseconds
            
            // Small delay between requests
            try { Thread.sleep(10); } catch (InterruptedException e) {}
        }
        
        return latencies;
    }
    
    /**
     * CONCURRENT LOAD BENCHMARK - Anti-Stampede Test
     */
    public ConcurrentBenchmarkResult runConcurrentBenchmark(Long caseId, int concurrency) {
        System.out.println("⚡ Starting Concurrent Benchmark...");
        
        // Invalidate cache first để đảm bảo cache miss
        cacheService.invalidateCase(caseId);
        
        ExecutorService executor = Executors.newFixedThreadPool(concurrency);
        List<CompletableFuture<Long>> futures = new ArrayList<>();
        
        long benchmarkStartTime = System.currentTimeMillis();
        
        // Launch concurrent requests
        for (int i = 0; i < concurrency; i++) {
            CompletableFuture<Long> future = CompletableFuture.supplyAsync(() -> {
                long startTime = System.nanoTime();
                
                // All threads request same key simultaneously 
                Optional<CaseResponse> result = cacheService.getCachedCase(caseId);
                
                long latencyNanos = System.nanoTime() - startTime;
                return latencyNanos / 1_000_000; // Convert to ms
                
            }, executor);
            
            futures.add(future);
        }
        
        // Wait for all to complete
        List<Long> latencies = new ArrayList<>();
        try {
            for (CompletableFuture<Long> future : futures) {
                latencies.add(future.get(10, TimeUnit.SECONDS));
            }
        } catch (Exception e) {
            System.err.println("❌ Concurrent benchmark failed: " + e.getMessage());
        }
        
        executor.shutdown();
        
        long totalBenchmarkTime = System.currentTimeMillis() - benchmarkStartTime;
        PerformanceMetrics metrics = calculateMetrics(latencies, "Concurrent");
        
        return new ConcurrentBenchmarkResult(concurrency, metrics, totalBenchmarkTime);
    }
    
    /**
     * Calculate percentiles (P50, P95, P99)
     */
    private PerformanceMetrics calculateMetrics(List<Long> latencies, String phase) {
        if (latencies.isEmpty()) {
            return new PerformanceMetrics(phase, 0, 0, 0, 0, 0, 0);
        }
        
        Collections.sort(latencies);
        
        int size = latencies.size();
        long p50 = latencies.get((int) (size * 0.50));
        long p95 = latencies.get((int) (size * 0.95));
        long p99 = latencies.get((int) (size * 0.99));
        long min = latencies.get(0);
        long max = latencies.get(size - 1);
        
        long avg = (long) latencies.stream().mapToLong(Long::longValue).average().orElse(0.0);
        
        System.out.printf("📈 %s Metrics: P50=%dms, P95=%dms, P99=%dms, Avg=%dms%n", 
                         phase, p50, p95, p99, avg);
        
        return new PerformanceMetrics(phase, min, max, avg, p50, p95, p99);
    }
    
    /**
     * Performance Metrics DTO
     */
    public static class PerformanceMetrics {
        public final String phase;
        public final long minMs;
        public final long maxMs;
        public final long avgMs;
        public final long p50Ms;
        public final long p95Ms;
        public final long p99Ms;
        
        public PerformanceMetrics(String phase, long minMs, long maxMs, long avgMs, 
                                long p50Ms, long p95Ms, long p99Ms) {
            this.phase = phase;
            this.minMs = minMs;
            this.maxMs = maxMs;
            this.avgMs = avgMs;
            this.p50Ms = p50Ms;
            this.p95Ms = p95Ms;
            this.p99Ms = p99Ms;
        }
    }
    
    /**
     * Benchmark Result with improvement calculations
     */
    public static class BenchmarkResult {
        public final PerformanceMetrics noCacheMetrics;
        public final PerformanceMetrics withCacheMetrics;
        public final double p95ImprovementPercent;
        public final double avgImprovementPercent;
        
        public BenchmarkResult(PerformanceMetrics noCacheMetrics, PerformanceMetrics withCacheMetrics) {
            this.noCacheMetrics = noCacheMetrics;
            this.withCacheMetrics = withCacheMetrics;
            
            // Calculate improvement percentages
            if (noCacheMetrics.p95Ms > 0) {
                this.p95ImprovementPercent = ((double) (noCacheMetrics.p95Ms - withCacheMetrics.p95Ms) / noCacheMetrics.p95Ms) * 100;
            } else {
                this.p95ImprovementPercent = 0.0;
            }
            
            if (noCacheMetrics.avgMs > 0) {
                this.avgImprovementPercent = ((double) (noCacheMetrics.avgMs - withCacheMetrics.avgMs) / noCacheMetrics.avgMs) * 100;
            } else {
                this.avgImprovementPercent = 0.0;
            }
        }
        
        public void printSummary() {
            System.out.println("\n🎯 PERFORMANCE BENCHMARK RESULTS:");
            System.out.printf("WITHOUT Cache - P95: %dms, Avg: %dms%n", 
                            noCacheMetrics.p95Ms, noCacheMetrics.avgMs);
            System.out.printf("WITH Cache    - P95: %dms, Avg: %dms%n", 
                            withCacheMetrics.p95Ms, withCacheMetrics.avgMs);
            System.out.printf("📊 P95 Improvement: %.1f%% faster%n", p95ImprovementPercent);
            System.out.printf("📊 Avg Improvement: %.1f%% faster%n", avgImprovementPercent);
        }
    }
    
    /**
     * Concurrent benchmark result
     */
    public static class ConcurrentBenchmarkResult {
        public final int concurrency;
        public final PerformanceMetrics metrics;
        public final long totalBenchmarkTimeMs;
        
        public ConcurrentBenchmarkResult(int concurrency, PerformanceMetrics metrics, long totalTimeMs) {
            this.concurrency = concurrency;
            this.metrics = metrics;
            this.totalBenchmarkTimeMs = totalTimeMs;
        }
        
        public void printSummary() {
            System.out.printf("\n⚡ CONCURRENT BENCHMARK (%d threads):%n", concurrency);
            System.out.printf("P95: %dms, Avg: %dms, Total: %dms%n", 
                            metrics.p95Ms, metrics.avgMs, totalBenchmarkTimeMs);
        }
    }
}