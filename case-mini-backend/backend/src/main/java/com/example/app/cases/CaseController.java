package com.example.app.cases;

import com.example.app.cases.dto.CreateCaseRequest;
import com.example.app.cases.dto.CaseResponse;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

import java.util.List;
import java.util.Optional;

/**
 * REST controller for /api/cases.
 * - GET /api/cases → list all (for screenshot: URL + 200 + JSON)
 * - GET /api/cases/{id} → get one
 * - POST /api/cases?assigneeId=... → create (assigneeId optional)
 */
@RestController
@RequestMapping("/api/cases")
public class CaseController {

    private final CaseService caseService;

    public CaseController(CaseService caseService) {
        this.caseService = caseService;
    }

    @GetMapping
    public List<CaseResponse> list() {
        return caseService.listAll();
    }

    @GetMapping("/{id}")
    public ResponseEntity<CaseResponse> getById(@PathVariable Long id) {
        Optional<CaseResponse> opt = caseService.getCaseById(id);
        return opt.map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<?> create(
            @Valid @RequestBody CreateCaseRequest request,
            @RequestParam(required = false) Long assigneeId,
            @RequestParam(required = false) String idempotencyKey) {
        try {
            CaseResponse created = caseService.createCaseWithMicroservices(request, assigneeId, idempotencyKey);
            var location = ServletUriComponentsBuilder.fromCurrentRequest()
                .path("/{id}").buildAndExpand(created.getId()).toUri();
            return ResponseEntity.created(location).body(created);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                .body(new ErrorBody("bad_request", e.getMessage()));
        }
    }

    public record ErrorBody(String error, String message) {}
}
