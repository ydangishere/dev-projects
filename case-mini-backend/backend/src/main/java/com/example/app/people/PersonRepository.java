package com.example.app.people;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * PEOPLE SERVICE - Repository
 * 
 * 🎯 MICROSERVICE OPERATIONS:
 * - validateAssignee(): Check person tồn tại
 * - findByEmail(): Unique lookup  
 * - findActiveMembers(): List người có thể assign
 */
@Repository
public interface PersonRepository extends JpaRepository<Person, Long> {
    
    /**
     * Validate assignee cho case creation
     * Chỉ cần tồn tại trong people table
     */
    @Query("SELECT CASE WHEN COUNT(p) > 0 THEN true ELSE false END " +
           "FROM Person p WHERE p.id = :id")
    boolean isValidAssignee(@Param("id") Long id);
    
    /**
     * Find by email (unique constraint)
     */
    Optional<Person> findByEmail(String email);
    
    /**
     * Find active members for assignment dropdown
     */
    @Query("SELECT p FROM Person p ORDER BY p.name")
    List<Person> findActiveMembers();
    
    /**
     * Search people by name or email
     */
    @Query("SELECT p FROM Person p WHERE " +
           "LOWER(p.name) LIKE LOWER(CONCAT('%', :search, '%')) OR " +
           "LOWER(p.email) LIKE LOWER(CONCAT('%', :search, '%'))")
    List<Person> searchPeople(@Param("search") String search);
}