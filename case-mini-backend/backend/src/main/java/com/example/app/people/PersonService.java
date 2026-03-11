package com.example.app.people;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

/**
 * PEOPLE MICROSERVICE - Business Logic
 * 
 * 🎯 CHỨC NĂNG TRONG MICROSERVICES:
 * - Validate assignee cho case creation
 * - Provide assignee information  
 * - Independent từ Case service
 * 
 * 🔗 COMMUNICATION:
 * - Case service sẽ gọi API này để validate assignee
 * - Hoặc pre-validate assigneeId trước khi tạo case
 */
@Service
public class PersonService {
    
    private final PersonRepository repository;
    
    public PersonService(PersonRepository repository) {
        this.repository = repository;
    }
    
    /**
     * VALIDATE ASSIGNEE - Called by Case Service
     * 🎯 Đây là microservice boundary call
     */
    public boolean isValidAssignee(Long personId) {
        if (personId == null || personId <= 0) {
            return false;
        }
        return repository.isValidAssignee(personId);
    }
    
    /**
     * Get person info for case details
     */
    public Optional<Person> getPersonById(Long id) {
        return repository.findById(id);
    }
    
    /**
     * Get active members for assignment UI
     */
    public List<Person> getActiveMembers() {
        return repository.findActiveMembers();
    }
    
    /**
     * Create new person
     */
    public Person createPerson(Person person) {
        // Business validation
        if (person.getName() == null || person.getName().isBlank()) {
            throw new IllegalArgumentException("Name is required");
        }
        
        if (person.getEmail() == null || person.getEmail().isBlank()) {
            throw new IllegalArgumentException("Email is required");
        }
        
        // Check email uniqueness
        if (repository.findByEmail(person.getEmail()).isPresent()) {
            throw new IllegalArgumentException("Email already exists");
        }
        
        return repository.save(person);
    }
    
    /**
     * Search people
     */
    public List<Person> searchPeople(String search) {
        if (search == null || search.isBlank()) {
            throw new IllegalArgumentException("Search term required");
        }
        return repository.searchPeople(search);
    }
}