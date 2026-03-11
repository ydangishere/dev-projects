package com.example.app.events;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * EVENT SYSTEM - MONITORING API
 * 
 * 🎯 ENDPOINTS:
 * - GET /api/events/outbox/stats → Outbox statistics
 * - POST /api/events/publish → Manual publish trigger
 */
@RestController
@RequestMapping("/api/events")
public class EventController {
    
    private final EventPublisher eventPublisher;
    
    public EventController(EventPublisher eventPublisher) {
        this.eventPublisher = eventPublisher;
    }
    
    /**
     * Get outbox statistics
     */
    @GetMapping("/outbox/stats")
    public ResponseEntity<EventPublisher.OutboxStats> getOutboxStats() {
        EventPublisher.OutboxStats stats = eventPublisher.getOutboxStats();
        return ResponseEntity.ok(stats);
    }
    
    /**
     * Manually trigger event publishing (for testing)
     */
    @PostMapping("/publish")
    public ResponseEntity<String> publishEvents() {
        eventPublisher.publishNow();
        return ResponseEntity.ok("Event publishing triggered");
    }
}