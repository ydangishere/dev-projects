package com.example.app.cases;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CaseRepository extends JpaRepository<CaseEntity, Long> {
    // JpaRepository cung cấp sẵn:
    // - save() - lưu case mới hoặc update
    // - findById() - tìm case theo ID
    // - findAll() - lấy tất cả cases
    // - deleteById() - xóa case theo ID
}