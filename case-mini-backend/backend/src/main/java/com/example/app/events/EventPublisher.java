package com.example.app.events;

import com.example.app.notes.NoteService;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * EVENT PUBLISHER - OUTBOX POLLING + KAFKA SIMULATION
 * 
 * 🎯 MỤC ĐÍCH:
 * - Poll outbox events định kỳ 
 * - Publish events lên "message bus" (simulate Kafka)
 * - Mark events as processed sau khi publish thành công
 * 
 * 🔄 OUTBOX PATTERN FLOW:
 * 1. Business logic save data + event trong 1 transaction
 * 2. Publisher poll events chưa processed  
 * 3. Publish event lên Kafka/Message Bus
 * 4. Mark event processed để không publish lại
 * 
 * ⚡ LỢI ÍCH:
 * - Guaranteed delivery: Event không mất khi service crash
 * - At-least-once delivery: Event có thể được gửi lại nếu fail  
 * - Decoupled: Business logic không cần biết về messaging infrastructure
 */
@Service
public class EventPublisher {
    
    private final OutboxEventRepository outboxRepository;
    private final NoteService noteService;  // Simulate event consumer
    
    public EventPublisher(OutboxEventRepository outboxRepository, NoteService noteService) {
        this.outboxRepository = outboxRepository;
        this.noteService = noteService;
    }
    
    /**
     * SCHEDULED OUTBOX POLLING
     * 
     * 🕐 Chạy mỗi 5 giây để poll events chưa processed
     * 🏭 Production: Có thể dùng multiple instances với distributed locking
     */
    @Scheduled(fixedDelay = 5000) // 5 seconds
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> unpublishedEvents = outboxRepository.findUnprocessedEvents();
        
        if (unpublishedEvents.isEmpty()) {
            return; // No events to process
        }
        
        System.out.println("📡 Publishing " + unpublishedEvents.size() + " pending events...");
        
        for (OutboxEvent event : unpublishedEvents) {
            try {
                // SIMULATE KAFKA PUBLISH
                publishEventToMessageBus(event);
                
                // Mark as processed (trong same transaction)
                event.setProcessed(true);
                outboxRepository.save(event);
                
                System.out.println("✅ Published event: " + event.getEventType() + 
                                 " for aggregate: " + event.getAggregateId());
                
            } catch (Exception e) {
                System.err.println("❌ Failed to publish event " + event.getId() + ": " + e.getMessage());
                // Event sẽ được retry trong lần poll tiếp theo
            }
        }
        
        System.out.println("📊 Outbox status: " + outboxRepository.countUnprocessedEvents() + " events pending");
    }
    
    /**
     * SIMULATE MESSAGE BUS PUBLISH
     * 
     * 🚀 Trong production: 
     * - kafkaTemplate.send("case-events", event.getPayload())
     * - rabbitTemplate.convertAndSend("case.exchange", "case.created", event)
     * 
     * 🧪 Demo: Direct call to consumer services
     */
    private void publishEventToMessageBus(OutboxEvent event) {
        System.out.println("📤 Publishing to message bus: " + event.getEventType());
        
        // SIMULATE KAFKA TOPIC ROUTING
        switch (event.getEventType()) {
            case "CaseCreated":
                // Route to Notes Service (simulate Kafka consumer)
                noteService.handleCaseCreatedEvent(event.getPayload());
                break;
                
            case "CaseUpdated":
                // Future: Route to other consumers
                System.out.println("📮 CaseUpdated event published (no consumers yet)");
                break;
                
            default:
                System.out.println("⚠️  Unknown event type: " + event.getEventType());
        }
        
        // SIMULATE NETWORK DELAY  
        try {
            Thread.sleep(100); // 100ms publish latency
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
    
    /**
     * Manual trigger để test (via REST endpoint)
     */
    public void publishNow() {
        System.out.println("🔄 Manual event publishing triggered...");
        publishPendingEvents();
    }
    
    /**
     * Get outbox stats (để monitoring)
     */
    public OutboxStats getOutboxStats() {
        long pending = outboxRepository.countUnprocessedEvents();
        long total = outboxRepository.count();
        
        return new OutboxStats(total, pending, total - pending);
    }
    
    /**
     * Stats DTO
     */
    public static class OutboxStats {
        public final long totalEvents;
        public final long pendingEvents; 
        public final long publishedEvents;
        
        public OutboxStats(long total, long pending, long published) {
            this.totalEvents = total;
            this.pendingEvents = pending;
            this.publishedEvents = published;
        }
        
        @Override
        public String toString() {
            return String.format("OutboxStats{total=%d, pending=%d, published=%d}", 
                               totalEvents, pendingEvents, publishedEvents);
        }
    }
}