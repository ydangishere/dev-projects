-- Run in Supabase SQL Editor to create the orders table.
-- Purpose: store incoming Shopify order webhook data (Shopify → external DB).

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  shopify_order_id bigint not null,
  order_number text,
  email text,
  total_price numeric,
  financial_status text,
  shop_domain text,
  raw_json jsonb,
  created_at timestamptz default now()
);

-- Optional: allow anonymous insert from your app (if using anon key)
alter table public.orders enable row level security;

create policy "Allow insert from app"
  on public.orders for insert
  with check (true);

create policy "Allow read for authenticated or anon"
  on public.orders for select
  using (true);
