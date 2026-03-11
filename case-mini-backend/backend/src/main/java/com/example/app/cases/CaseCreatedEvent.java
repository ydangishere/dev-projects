package com.example.app.cases;

/**
 * CASE CREATED EVENT - Event Payload
 * 
 * 🎯 MỤC ĐÍCH:
 * - Structured data để publish lên Kafka/Event Bus
 * - Contains all info cần thiết cho downstream services
 * - Immutable event data (không thay đổi sau khi tạo)
 * 
 * 📤 CONSUMERS:
 * - Notes Service: Tạo default note cho case
 * - Audit Service: Log case creation activity  
 * - Notification Service: Send alerts to assignee
 */
public class CaseCreatedEvent {
    
    private final Long caseId;
    private final String title;
    private final Long assigneeId;
    private final String status;
    private final long timestamp;
    
    public CaseCreatedEvent(Long caseId, String title, Long assigneeId, String status) {
        this.caseId = caseId;
        this.title = title;
        this.assigneeId = assigneeId;
        this.status = status;
        this.timestamp = System.currentTimeMillis();
    }
    
    // Getters (no setters - immutable event)
    public Long getCaseId() { return caseId; }
    public String getTitle() { return title; }
    public Long getAssigneeId() { return assigneeId; }
    public String getStatus() { return status; }
    public long getTimestamp() { return timestamp; }
    
    @Override
    public String toString() {
        return String.format("CaseCreatedEvent{caseId=%d, title='%s', assigneeId=%s, status='%s'}", 
                           caseId, title, assigneeId, status);
    }
}