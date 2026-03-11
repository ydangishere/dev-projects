package com.example.app.notes;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * NOTES SERVICE - Repository
 * 
 * 🎯 MICROSERVICE OPERATIONS:
 * - findByCaseId(): Lấy all notes của 1 case
 * - checkDefaultNoteExists(): Tránh duplicate default note
 */
@Repository
public interface NoteRepository extends JpaRepository<Note, Long> {
    
    /**
     * Lấy tất cả notes của 1 case (sorted by creation time)
     */
    @Query("SELECT n FROM Note n WHERE n.caseId = :caseId ORDER BY n.createdAt ASC")
    List<Note> findByCaseId(@Param("caseId") Long caseId);
    
    /**
     * Check default note đã tồn tại chưa (để tránh duplicate)
     */
    @Query("SELECT COUNT(n) > 0 FROM Note n WHERE n.caseId = :caseId")
    boolean hasDefaultNote(@Param("caseId") Long caseId);
    
    /**
     * Count notes của case (để monitoring)
     */
    @Query("SELECT COUNT(n) FROM Note n WHERE n.caseId = :caseId")
    long countByCaseId(@Param("caseId") Long caseId);
    
}