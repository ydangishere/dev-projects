package com.example.app.events;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * OUTBOX REPOSITORY - Query Operations
 * 
 * 🎯 CHỨC NĂNG:
 * - findUnprocessedEvents(): Lấy events chưa publish
 * - markAsProcessed(): Đánh dấu event đã publish thành công
 */
@Repository
public interface OutboxEventRepository extends JpaRepository<OutboxEvent, String> {
    
    /**
     * Lấy tất cả events chưa được publish
     * Order by created_at để đảm bảo publish theo thứ tự
     */
    @Query("SELECT o FROM OutboxEvent o WHERE o.processed = false ORDER BY o.createdAt ASC")
    List<OutboxEvent> findUnprocessedEvents();
    
    /**
     * Lấy events theo event type
     */
    List<OutboxEvent> findByEventTypeAndProcessed(String eventType, Boolean processed);
    
    /**
     * Count events chưa publish (để monitoring)
     */
    @Query("SELECT COUNT(o) FROM OutboxEvent o WHERE o.processed = false")
    long countUnprocessedEvents();
}