package com.example.app.cache;

import redis.embedded.RedisServer;
import org.springframework.stereotype.Service;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.io.IOException;

/**
 * Embedded Redis Server for development
 * Trong production, sử dụng external Redis cluster
 */
@Service
public class EmbeddedRedisService {
    
    private RedisServer redisServer;
    private final int REDIS_PORT = 6379;
    
    @PostConstruct
    public void startRedis() throws IOException {
        try {
            redisServer = new RedisServer(REDIS_PORT);
            redisServer.start();
            System.out.println("🚀 Embedded Redis started on port " + REDIS_PORT);
        } catch (Exception e) {
            System.out.println("⚠️  Redis port " + REDIS_PORT + " already in use, using external Redis");
        }
    }
    
    @PreDestroy
    public void stopRedis() {
        if (redisServer != null && redisServer.isActive()) {
            redisServer.stop();
            System.out.println("🛑 Embedded Redis stopped");
        }
    }
}