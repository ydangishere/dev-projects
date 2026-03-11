package com.example.app.cases;

import com.example.app.people.Person;
import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.time.LocalDateTime;

@Entity
@Table(
    name = "cases",
    indexes = {
        @Index(name = "idx_cases_assignee_id", columnList = "assigned_people_id"),
        @Index(name = "idx_cases_status", columnList = "status")
    }
)
public class CaseEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank(message = "Title is required")
    @Size(max = 255, message = "Title must be less than 255 characters")
    @Column(nullable = false)
    private String title;

    @NotBlank(message = "Status is required")
    @Column(nullable = false)
    private String status;
    
    /**
     * FK → people.id
     * 1 case có tối đa 1 assignee
     * 1 người có thể xử lý nhiều case
     */
    @Column(name = "assigned_people_id")
    private Long assignedPeopleId;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(
        name = "assigned_people_id",
        insertable = false,
        updatable = false,
        foreignKey = @ForeignKey(name = "fk_cases_assigned_people")
    )
    private Person assignedPerson;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    // Getters and Setters
    public Long getId() { return id; }
    
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public Long getAssignedPeopleId() { return assignedPeopleId; }
    public void setAssignedPeopleId(Long assignedPeopleId) { this.assignedPeopleId = assignedPeopleId; }
    public Person getAssignedPerson() { return assignedPerson; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}