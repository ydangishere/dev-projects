package com.example.app.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HomeController {
    
    @GetMapping("/")
    public String home() {
        return "Hello Spring Boot! Application is running successfully! 🚀";
    }
    
    @GetMapping("/health")
    public String health() {
        return "OK - Application is healthy";
    }
}