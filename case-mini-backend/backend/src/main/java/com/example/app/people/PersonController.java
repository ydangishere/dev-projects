package com.example.app.people;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

/**
 * PEOPLE MICROSERVICE - REST API
 * 
 * 🎯 ENDPOINTS:
 * - GET /api/people/active → List assignable people
 * - GET /api/people/{id}/validate → Validate assignee  
 * - POST /api/people → Create new person
 */
@RestController
@RequestMapping("/api/people")
public class PersonController {
    
    private final PersonService personService;
    
    public PersonController(PersonService personService) {
        this.personService = personService;
    }
    
    /**
     * Get active members for assignment dropdown
     */
    @GetMapping("/active")
    public ResponseEntity<List<Person>> getActiveMembers() {
        List<Person> activeMembers = personService.getActiveMembers();
        return ResponseEntity.ok(activeMembers);
    }
    
    /**
     * Validate assignee (cho case service gọi)
     */
    @GetMapping("/{id}/validate")
    public ResponseEntity<Boolean> validateAssignee(@PathVariable Long id) {
        boolean isValid = personService.isValidAssignee(id);
        return ResponseEntity.ok(isValid);
    }
    
    /**
     * Get person by ID
     */
    @GetMapping("/{id}")
    public ResponseEntity<Person> getPersonById(@PathVariable Long id) {
        Optional<Person> person = personService.getPersonById(id);
        return person.map(ResponseEntity::ok)
                    .orElse(ResponseEntity.notFound().build());
    }
    
    /**
     * Search people
     */
    @GetMapping
    public ResponseEntity<List<Person>> searchPeople(@RequestParam String search) {
        try {
            List<Person> results = personService.searchPeople(search);
            return ResponseEntity.ok(results);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
    
    /**
     * Create new person
     */
    @PostMapping
    public ResponseEntity<Person> createPerson(@RequestBody Person person) {
        try {
            Person created = personService.createPerson(person);
            return ResponseEntity.ok(created);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
}