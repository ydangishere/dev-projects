package com.example.app.cases;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface IdempotencyRepository extends JpaRepository<IdempotencyRecord, String> {
    // JpaRepository provides:
    // - save() - lưu idempotency record
    // - findById() - tìm theo idempotency key
    // - existsById() - check key đã tồn tại chưa
}