# Case Mini Backend (Spring Boot)

Mini order/case management API: CRUD, validation, pagination.

## Tech

- **Java 17**, **Spring Boot 3.2**
- Spring Data JPA, Spring Web, Validation
- Redis (caching), SpringDoc OpenAPI (Swagger UI)
- Docker (optional)

## Run

```bash
cd backend
./mvnw spring-boot:run
```

API docs (when running): http://localhost:8080/swagger-ui.html

## Repo

Part of [java-backend-repos](https://github.com/ydangishere/java-backend-repos).

---

## Solution Architecture Review (implementation-backed)

**Business problem:** Expose a manageable case/order API with structured CRUD, validation and cacheable reads.

**Implemented flow (one line):** REST caller → Spring Boot controller/validation → Service layer → JPA repository/database → Optional Redis cache → JSON response.

**Architecture decisions**
- **Contract:** HTTP endpoints and DTO/validation patterns separate request input from internal persistence.
- **Persistence & cache:** JPA maintains case records; Redis-compatible caching trades fewer reads against invalidation and cache miss complexity.
- **Extensibility:** Controller/service/repository separation makes it possible to add approval workflows, integration events and role-based controls without rewriting the transport layer.
- **Production concerns:** Define database constraints, idempotency behavior, concurrency tests, auth, structured logs, timeouts and monitoring before scaling.
- **Evaluation:** Measure CRUD error rates, pagination stability, cache hit/miss behavior and concurrent-update correctness.

**RAG status:** No embedding, document-retrieval or LLM workflow.

**Status:** Backend reference/demo, not an independently verified production service.
