package com.example.app.cases;

import jakarta.persistence.*;
import java.time.LocalDateTime;

/**
 * Entity để lưu idempotency keys và prevent duplicate requests
 */
@Entity
@Table(name = "idempotency_records")
public class IdempotencyRecord {
    
    @Id
    private String idempotencyKey;
    
    @Column(name = "case_id")
    private Long caseId;
    
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    
    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }

    // Constructors
    public IdempotencyRecord() {}
    
    public IdempotencyRecord(String idempotencyKey, Long caseId) {
        this.idempotencyKey = idempotencyKey;
        this.caseId = caseId;
    }

    // Getters and Setters
    public String getIdempotencyKey() { return idempotencyKey; }
    public void setIdempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; }
    
    public Long getCaseId() { return caseId; }
    public void setCaseId(Long caseId) { this.caseId = caseId; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}