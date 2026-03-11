package com.example.app.cases.dto;

import jakarta.validation.constraints.*;

/**
 * DTO for creating a new case
 * - Chỉ chứa fields cần thiết để tạo case
 * - Không có id, timestamps (auto-generated)
 */
public class CreateCaseRequest {
    
    @NotBlank(message = "Title is required")
    @Size(max = 255, message = "Title must be less than 255 characters")
    private String title;
    
    @NotBlank(message = "Status is required")
    private String status;

    // Constructors
    public CreateCaseRequest() {}
    
    public CreateCaseRequest(String title, String description, String status) {
        this.title = title;
        this.status = status;
    }

    // Getters and Setters
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}