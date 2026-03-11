package com.example.app.events;

import jakarta.persistence.*;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * OUTBOX PATTERN - Event Storage Entity
 * 
 * 🎯 MỤC ĐÍCH:
 * - Lưu events trong cùng DB transaction với business data
 * - Đảm bảo event chỉ được publish khi DB commit thành công
 * - Tránh mất event khi service crash ngay sau commit
 * 
 * 🏗️ OUTBOX TABLE DESIGN:
 * - id: Unique identifier cho mỗi event
 * - event_type: Loại event (CaseCreated, CaseUpdated...)
 * - aggregate_id: ID của entity chính (case_id, people_id...)
 * - payload: JSON data của event
 * - created_at: Thời gian tạo event
 * - processed: Đã được publish chưa
 */
@Entity
@Table(name = "outbox_events")
public class OutboxEvent {
    
    @Id
    private String id;
    
    @Column(name = "event_type", nullable = false)
    private String eventType;
    
    @Column(name = "aggregate_id")
    private String aggregateId;
    
    @Column(columnDefinition = "TEXT")
    private String payload;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    private Boolean processed = false;

    // Constructors
    public OutboxEvent() {
        this.id = UUID.randomUUID().toString();
        this.createdAt = LocalDateTime.now();
    }
    
    public OutboxEvent(String eventType, String aggregateId, String payload) {
        this();
        this.eventType = eventType;
        this.aggregateId = aggregateId;
        this.payload = payload;
    }
    
    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    
    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }
    
    public String getAggregateId() { return aggregateId; }
    public void setAggregateId(String aggregateId) { this.aggregateId = aggregateId; }
    
    public String getPayload() { return payload; }
    public void setPayload(String payload) { this.payload = payload; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    
    public Boolean getProcessed() { return processed; }
    public void setProcessed(Boolean processed) { this.processed = processed; }
}