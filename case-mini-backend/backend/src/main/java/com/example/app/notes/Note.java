package com.example.app.notes;

import com.example.app.cases.CaseEntity;
import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDateTime;

/**
 * NOTES MICROSERVICE - Entity
 * 
 * 🎯 MỤC ĐÍCH:
 * - Quản lý notes/comments cho cases
 * - Tự động tạo default note khi case created  
 * - Separated database từ Case service
 * 
 * 📝 TRONG MICROSERVICES:
 * - Notes service chỉ biết caseId (external reference)
 * - Không join với cases table → eventual consistency
 * - Tạo note dựa vào CaseCreated event
 */
@Entity
@Table(
    name = "notes",
    indexes = {
        @Index(name = "idx_notes_case_created_at", columnList = "case_id, created_at")
    }
)
public class Note {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    /**
     * FK → cases.id
     * 1 note bắt buộc phải thuộc 1 case
     * 1 case có thể có nhiều note
     */
    @Column(name = "case_id", nullable = false)
    private Long caseId;
    
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(
        name = "case_id",
        insertable = false,
        updatable = false,
        foreignKey = @ForeignKey(name = "fk_notes_case")
    )
    private CaseEntity caseEntity;
    
    @NotBlank(message = "Content is required")
    @Column(nullable = false, columnDefinition = "TEXT")
    private String content;
    
    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        if (createdAt == null) {
            createdAt = LocalDateTime.now();
        }
    }

    // Constructors
    public Note() {}
    
    public Note(Long caseId, String content) {
        this.caseId = caseId;
        this.content = content;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public Long getCaseId() { return caseId; }
    public void setCaseId(Long caseId) { this.caseId = caseId; }
    public CaseEntity getCaseEntity() { return caseEntity; }
    
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}