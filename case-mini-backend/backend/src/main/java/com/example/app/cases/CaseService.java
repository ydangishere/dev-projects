package com.example.app.cases;

import com.example.app.cases.dto.CreateCaseRequest;
import com.example.app.cases.dto.CaseResponse;
import com.example.app.events.OutboxEvent;
import com.example.app.events.OutboxEventRepository;
import com.example.app.people.PersonService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * CASE SERVICE - Updated với OUTBOX PATTERN
 * 
 * 🎯 MICROSERVICES DESIGN:
 * - Tạo case + emit event trong 1 transaction
 * - Validate assignee qua People Service API call  
 * - Event sẽ trigger Notes Service tạo default note
 */
@Service
public class CaseService {
    private final CaseRepository repository;
    private final IdempotencyRepository idempotencyRepository;
    private final OutboxEventRepository outboxRepository;
    private final PersonService personService;
    private final ObjectMapper objectMapper;
    private final CaseCacheService cacheService;

    public CaseService(CaseRepository repository, 
                      IdempotencyRepository idempotencyRepository,
                      OutboxEventRepository outboxRepository,
                      PersonService personService,
                      CaseCacheService cacheService) {
        this.repository = repository;
        this.idempotencyRepository = idempotencyRepository;
        this.outboxRepository = outboxRepository;
        this.personService = personService;
        this.objectMapper = new ObjectMapper();
        this.cacheService = cacheService;
    }

    /**
     * CREATE CASE với MICROSERVICES PATTERN
     * 
     * 🔄 FLOW:
     * 1. Validate assignee qua People Service (microservice call)
     * 2. Create case trong local transaction
     * 3. Emit CaseCreated event vào outbox (cùng transaction)  
     * 4. Event publisher sẽ publish event lên Kafka
     * 5. Notes Service consume event → create default note
     */
    @Transactional
    public CaseResponse createCaseWithMicroservices(CreateCaseRequest request, 
                                                   Long assigneeId, 
                                                   String idempotencyKey) {
        // STEP 1: Validate assignee qua People Service (microservice boundary)
        if (assigneeId != null && !personService.isValidAssignee(assigneeId)) {
            throw new IllegalArgumentException("Invalid assignee: person not found or inactive");
        }
        
        // STEP 2: Check idempotency (tránh duplicate)
        if (idempotencyKey != null && !idempotencyKey.isBlank()) {
            Optional<IdempotencyRecord> existing = idempotencyRepository.findById(idempotencyKey);
            if (existing.isPresent()) {
                Long existingCaseId = existing.get().getCaseId();
                CaseEntity existingCase = repository.findById(existingCaseId)
                    .orElseThrow(() -> new RuntimeException("Case not found for idempotency key"));
                return CaseResponse.from(existingCase);
            }
        }

        // STEP 3: Create case entity
        CaseEntity entity = new CaseEntity();
        entity.setTitle(request.getTitle());
        entity.setStatus(request.getStatus() != null ? request.getStatus() : "OPEN");
        entity.setAssignedPeopleId(assigneeId);
        
        CaseEntity savedCase = repository.save(entity);
        
        // STEP 4: Save idempotency record
        if (idempotencyKey != null && !idempotencyKey.isBlank()) {
            IdempotencyRecord record = new IdempotencyRecord(idempotencyKey, savedCase.getId());
            idempotencyRepository.save(record);
        }
        
        // STEP 5: EMIT EVENT vào outbox (cùng transaction!)
        try {
            CaseCreatedEvent eventPayload = new CaseCreatedEvent(
                savedCase.getId(),
                savedCase.getTitle(),
                assigneeId,
                savedCase.getStatus()
            );
            
            String payloadJson = objectMapper.writeValueAsString(eventPayload);
            
            OutboxEvent outboxEvent = new OutboxEvent(
                "CaseCreated",
                savedCase.getId().toString(), 
                payloadJson
            );
            
            outboxRepository.save(outboxEvent);
            
            System.out.println("📤 Event saved to outbox: CaseCreated for case " + savedCase.getId());
            
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize event payload", e);
        }
        
        return CaseResponse.from(savedCase);
    }
    
    // Backward compatibility methods
    public CaseResponse createCase(CreateCaseRequest request, String idempotencyKey) {
        return createCaseWithMicroservices(request, null, idempotencyKey);
    }
    
    public CaseResponse createCase(CreateCaseRequest request) {
        return createCase(request, null);
    }
    
    /**
     * LIST ALL CASES (for GET /api/cases)
     */
    public List<CaseResponse> listAll() {
        return repository.findAll().stream()
            .map(CaseResponse::from)
            .collect(Collectors.toList());
    }

    /**
     * GET CASE WITH READ-THROUGH CACHE
     * 
     * 🎯 PATTERN: Cache hit → return cached
     *           Cache miss → query DB → cache result → return
     */
    public Optional<CaseResponse> getCaseById(Long id) {
        if (id == null || id <= 0) {
            return Optional.empty();
        }
        
        try {
            // Use cache service (implements read-through pattern)
            return cacheService.getCachedCase(id);
            
        } catch (Exception e) {
            System.err.println("❌ Cache error, fallback to DB for case " + id + ": " + e.getMessage());
            
            // Fallback to direct DB query
            return repository.findById(id).map(CaseResponse::from);
        }
    }
    
    /**
     * GET CASE BY ID OR THROW (no cache, direct DB)
     * Use for internal operations that need fresh data
     */
    public CaseResponse getCaseByIdOrThrow(Long id) {
        CaseEntity entity = repository.findById(id)
            .orElseThrow(() -> new RuntimeException("case not found"));
        return CaseResponse.from(entity);
    }
    
    /**
     * UPDATE CASE - WITH CACHE INVALIDATION
     * 
     * 🔄 PATTERN: Update DB → invalidate cache → fresh data on next read
     */
    @Transactional
    public CaseResponse updateCaseStatus(Long id, String newStatus) {
        CaseEntity entity = repository.findById(id)
            .orElseThrow(() -> new RuntimeException("case not found"));
        
        String oldStatus = entity.getStatus();
        entity.setStatus(newStatus);
        
        CaseEntity updatedEntity = repository.save(entity);
        
        // CACHE INVALIDATION (write-through pattern)
        cacheService.invalidateCase(id);
        
        System.out.println("📝 Updated case " + id + " status: " + oldStatus + " → " + newStatus);
        
        return CaseResponse.from(updatedEntity);
    }
}