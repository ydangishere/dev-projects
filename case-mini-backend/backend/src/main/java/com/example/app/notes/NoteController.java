package com.example.app.notes;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * NOTES MICROSERVICE - REST API
 * 
 * 🎯 ENDPOINTS:
 * - GET /api/notes/case/{caseId} → Get notes for a case
 * - POST /api/notes → Create manual note
 */
@RestController
@RequestMapping("/api/notes")
public class NoteController {
    
    private final NoteService noteService;
    
    public NoteController(NoteService noteService) {
        this.noteService = noteService;
    }
    
    /**
     * Get all notes for a case
     */
    @GetMapping("/case/{caseId}")
    public ResponseEntity<List<Note>> getNotesByCaseId(@PathVariable Long caseId) {
        try {
            List<Note> notes = noteService.getNotesByCaseId(caseId);
            return ResponseEntity.ok(notes);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
    
    /**
     * Create manual note
     */
    @PostMapping
    public ResponseEntity<Note> createNote(@RequestParam Long caseId, 
                                         @RequestParam String content,
                                         @RequestParam(defaultValue = "USER") String createdBy) {
        try {
            Note note = noteService.createNote(caseId, content, createdBy);
            return ResponseEntity.ok(note);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }
    }
}