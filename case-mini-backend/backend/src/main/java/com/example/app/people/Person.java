package com.example.app.people;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.LocalDateTime;

/**
 * PEOPLE MICROSERVICE - Entity
 * 
 * 🎯 MỤC ĐÍCH:
 * - Quản lý thông tin người trong hệ thống
 * - Validate assignee khi tạo case
 * - Separated database từ Case service (microservices pattern)
 * a
 * 🏗️ TRONG MICROSERVICES:
 * - Mỗi service có DB riêng → không thể join trực tiếp với cases table
 * - Communication qua API calls hoặc events
 * - Data consistency qua eventual consistency
 */
@Entity
@Table(
    name = "people",
    indexes = {
        @Index(name = "idx_people_name", columnList = "name")
    }
)
public class Person {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @NotBlank(message = "Name is required")
    @Size(max = 255)
    @Column(nullable = false)
    private String name;
    
    @NotBlank(message = "Email is required")
    @Column(nullable = false, unique = true)
    private String email;
    
    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }

    // Constructors
    public Person() {}
    
    public Person(String name, String email) {
        this.name = name;
        this.email = email;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}