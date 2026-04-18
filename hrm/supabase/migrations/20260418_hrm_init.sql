create extension if not exists "pgcrypto";

create table if not exists public.departments (
	id uuid primary key default gen_random_uuid(),
	name text not null unique,
	created_at timestamptz not null default now()
);

create table if not exists public.employees (
	id uuid primary key references auth.users(id) on delete cascade,
	full_name text not null,
	email text not null unique,
	department_id uuid references public.departments(id) on delete set null,
	role text not null default 'employee' check (role in ('admin', 'employee')),
	status text not null default 'active' check (status in ('active', 'inactive')),
	created_at timestamptz not null default now()
);

create table if not exists public.leave_requests (
	id uuid primary key default gen_random_uuid(),
	employee_id uuid not null references public.employees(id) on delete cascade,
	start_date date not null,
	end_date date not null,
	total_days integer not null check (total_days > 0),
	reason text not null,
	status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
	created_at timestamptz not null default now()
);

alter table public.departments enable row level security;
alter table public.employees enable row level security;
alter table public.leave_requests enable row level security;

create or replace function public.is_admin()
returns boolean
language sql
stable
security invoker
as $$
	select exists (
		select 1
		from public.employees
		where id = auth.uid()
			and role = 'admin'
	);
$$;

create policy "employees_select_admin_or_self"
on public.employees
for select
to authenticated
using (public.is_admin() or id = auth.uid());

create policy "employees_update_admin_or_self"
on public.employees
for update
to authenticated
using (public.is_admin() or id = auth.uid())
with check (public.is_admin() or id = auth.uid());

create policy "departments_select_authenticated"
on public.departments
for select
to authenticated
using (true);

create policy "leave_requests_select_admin_or_owner"
on public.leave_requests
for select
to authenticated
using (public.is_admin() or employee_id = auth.uid());

create policy "leave_requests_insert_owner"
on public.leave_requests
for insert
to authenticated
with check (employee_id = auth.uid());

create policy "leave_requests_update_admin_or_owner"
on public.leave_requests
for update
to authenticated
using (public.is_admin() or employee_id = auth.uid())
with check (public.is_admin() or employee_id = auth.uid());
