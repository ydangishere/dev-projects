-- 🏗️ DATABASE SCHEMA WITH FK RELATIONSHIPS
-- Generated from entity definitions

-- 1️⃣ PEOPLE TABLE (Master table)
CREATE TABLE people (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP
);

-- 2️⃣ CASES TABLE (References people)
CREATE TABLE cases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(255) NOT NULL,
    assigned_people_id BIGINT,              -- FK → people.id
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- FK Constraint
    FOREIGN KEY (assigned_people_id) REFERENCES people(id)
);

-- 3️⃣ NOTES TABLE (References cases)
CREATE TABLE notes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id BIGINT NOT NULL,                -- FK → cases.id
    content TEXT NOT NULL,
    created_at TIMESTAMP,
    
    -- FK Constraint  
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
);

-- 🔗 RELATIONSHIPS SUMMARY:
-- People (1) ────────── (0..N) Cases    [1 person can handle many cases]
-- Cases (1) ──────────── (0..N) Notes   [1 case can have many notes]

-- 🚫 FK CONSTRAINTS PREVENT:
-- ❌ Creating notes for non-existent cases
-- ❌ Assigning cases to non-existent people  
-- ❌ Orphaned data

-- ✅ FK CONSTRAINTS ENSURE:
-- ✅ Data integrity
-- ✅ Referential consistency
-- ✅ Cascade delete (notes deleted when case deleted)