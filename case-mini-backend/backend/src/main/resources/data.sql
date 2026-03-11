-- CLIENT DATA (keep existing)
insert into clients (name, age) values ('ABC', null);
insert into clients (name, age) values ('XYZ', 20);

-- 🔑 PEOPLE TABLE (PK: id)
insert into people (name, email, created_at) values
('John Smith', 'john.smith@company.com', now()),
('Sarah Johnson', 'sarah.johnson@company.com', now()),
('Mike Chen', 'mike.chen@company.com', now()),
('Lisa Brown', 'lisa.brown@company.com', now());

-- 🔑 CASES TABLE (PK: id, FK: assigned_people_id → people.id)
insert into cases (title, status, assigned_people_id, created_at, updated_at) values 
('Bug Report: Login Issue', 'OPEN', 1, now(), now()),          -- assigned to John Smith (id=1)
('Feature Request: Dark Mode', 'IN_PROGRESS', 2, now(), now()), -- assigned to Sarah Johnson (id=2)
('Support: Password Reset', 'CLOSED', 2, now(), now()),         -- assigned to Sarah Johnson (id=2)
('Database Migration', 'OPEN', null, now(), now());             -- unassigned case

-- 🔑 NOTES TABLE (PK: id, FK: case_id → cases.id)
insert into notes (case_id, content, created_at) values
(1, 'Initial bug report received from user. Investigating login flow.', now()),
(1, 'Reproduced the issue on staging environment. Password validation seems to be failing.', now()),
(2, 'Dark mode feature request approved. Starting UI design phase.', now()),
(2, 'Created wireframes for dark theme components.', now()),
(3, 'Password reset completed successfully. User confirmed access restored.', now()),
(4, 'Migration plan drafted. Need DBA review before execution.', now());