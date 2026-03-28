package com.example.demo;

import org.springframework.stereotype.Service;
import java.util.HashMap;
import java.util.List;
import java.util.concurrent.CompletableFuture;

@Service
public class SampleRisks {

    private static HashMap<String, String> cache = new HashMap<>();

    public void broadCatch() {
        try {
            doWork();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void infinite() {
        while (true) {
            if (System.currentTimeMillis() > 0) break;
        }
    }

    public void sleepWait() throws InterruptedException {
        Thread.sleep(1000);
    }

    public void asyncOrphan() {
        CompletableFuture.runAsync(() -> risky());
    }

    void risky() { }

    public void nplus(List<Long> ids, OrderRepository orderRepository) {
        for (Long id : ids) {
            orderRepository.findById(id);
        }
    }

    interface OrderRepository {
        Object findById(Long id);
    }

    public void rest() {
        org.springframework.web.client.RestTemplate restTemplate =
            new org.springframework.web.client.RestTemplate();
        restTemplate.getForObject("http://example.com", String.class);
    }
}
