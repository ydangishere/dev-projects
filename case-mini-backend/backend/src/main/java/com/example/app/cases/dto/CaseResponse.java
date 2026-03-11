package com.example.app.cases.dto;

import com.example.app.cases.CaseEntity;
import java.time.LocalDateTime;

/**
 * DTO for case response
 * - Chứa tất cả thông tin để trả về client
 * - Có thể format/transform data nếu cần
 */
public class CaseResponse {
    
    private Long id;
    private String title;
    private String status;
    private Long assignedPeopleId;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    // Constructors
    public CaseResponse() {}
    
    public CaseResponse(Long id, String title, String status, Long assignedPeopleId,
                       LocalDateTime createdAt, LocalDateTime updatedAt) {
        this.id = id;
        this.title = title;
        this.status = status;
        this.assignedPeopleId = assignedPeopleId;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    /**
     * Factory method để convert từ Entity sang DTO
     */
    public static CaseResponse from(CaseEntity entity) {
        return new CaseResponse(
            entity.getId(),
            entity.getTitle(),
            entity.getStatus(),
            entity.getAssignedPeopleId(),
            entity.getCreatedAt(),
            entity.getUpdatedAt()
        );
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public Long getAssignedPeopleId() { return assignedPeopleId; }
    public void setAssignedPeopleId(Long assignedPeopleId) { this.assignedPeopleId = assignedPeopleId; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}