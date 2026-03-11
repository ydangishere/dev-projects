package com.example.app.notes;

import com.example.app.cases.CaseCreatedEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * NOTES MICROSERVICE - Business Logic  
 * 
 * 🎯 CHỨC NĂNG:
 * - Tạo default note khi receive CaseCreated event
 * - IDEMPOTENT: Không tạo duplicate note
 * - Manage notes lifecycle
 * 
 * 📨 EVENT CONSUMER:
 * - Listen to CaseCreated events từ Kafka
 * - Tự động tạo "Case created" system note
 */
@Service
public class NoteService {
    
    private final NoteRepository repository;
    private final ObjectMapper objectMapper;
    
    public NoteService(NoteRepository repository) {
        this.repository = repository;
        this.objectMapper = new ObjectMapper();
    }
    
    /**
     * EVENT HANDLER - Process CaseCreated Event
     * 
     * 🎯 MICROSERVICES EVENT FLOW:
     * Case Service → publish CaseCreated → Notes Service consume → create default note
     * 
     * ⚡ IDEMPOTENT: Có thể receive event nhiều lần nhưng chỉ tạo 1 default note
     */
    @Transactional
    public void handleCaseCreatedEvent(String eventPayload) {
        try {
            System.out.println("📥 Notes Service received CaseCreated event");
            
            // Parse event payload
            CaseCreatedEvent event = objectMapper.readValue(eventPayload, CaseCreatedEvent.class);
            
            // IDEMPOTENCY CHECK: Tránh duplicate default note
            if (repository.hasDefaultNote(event.getCaseId())) {
                System.out.println("⚠️  Default note already exists for case " + event.getCaseId() + ", skipping");
                return;
            }
            
            // Create default system note
            String defaultContent = String.format(
                "📝 Case '%s' has been created and assigned for tracking. Status: %s",
                event.getTitle(),
                event.getStatus()
            );
            
            Note defaultNote = new Note(event.getCaseId(), defaultContent);
            
            Note savedNote = repository.save(defaultNote);
            
            System.out.println("✅ Created default note #" + savedNote.getId() + " for case " + event.getCaseId());
            
        } catch (Exception e) {
            System.err.println("❌ Error processing CaseCreated event: " + e.getMessage());
            throw new RuntimeException("Failed to process CaseCreated event", e);
        }
    }
    
    /**
     * Get notes for a case (for API endpoints)
     */
    public List<Note> getNotesByCaseId(Long caseId) {
        if (caseId == null || caseId <= 0) {
            throw new IllegalArgumentException("Valid case ID required");
        }
        return repository.findByCaseId(caseId);
    }
    
    /**
     * Create manual note (not system-generated)
     */
    public Note createNote(Long caseId, String content, String createdBy) {
        if (content == null || content.isBlank()) {
            throw new IllegalArgumentException("Note content required");
        }
        
        // createdBy được giữ ở API để tương thích, nhưng schema hiện tại chỉ lưu content/core fields
        Note note = new Note(caseId, content);
        return repository.save(note);
    }
}