-- BYTE AI - SUPABASE SCHEMA SETUP (2026)
-- Run this in your Supabase SQL Editor to fix PGRST205 errors.

-- 1. Enable pgvector extension for Semantic Memory
create extension if not exists vector;

-- 2. Tables for Core Configuration and Persona
create table if not exists public.channels_config (
    channel_id text primary key,
    temperature float,
    top_p float,
    agent_paused boolean default false,
    is_active boolean default true,
    updated_at timestamptz default now()
);

create table if not exists public.persona_profiles (
    channel_id text primary key,
    base_identity jsonb default '{}'::jsonb,
    tonality_engine jsonb default '{}'::jsonb,
    behavioral_constraints jsonb default '{}'::jsonb,
    model_routing jsonb default '{}'::jsonb,
    updated_at timestamptz default now()
);

create table if not exists public.channel_identity (
    channel_id text primary key,
    persona_name text,
    tone text,
    emote_vocab text[],
    lore text,
    updated_at timestamptz default now()
);

create table if not exists public.agent_notes (
    channel_id text primary key,
    notes text,
    updated_at timestamptz default now()
);

-- 3. Tables for Observability and History
create table if not exists public.observability_rollups (
    id uuid primary key default gen_random_uuid(),
    captured_at timestamptz default now(),
    snapshot jsonb not null
);

create table if not exists public.observability_channel_history (
    id bigint generated always as identity primary key,
    channel_id text not null,
    captured_at timestamptz default now(),
    snapshot jsonb not null
);

create table if not exists public.channel_state (
    channel_id text primary key,
    vibe text,
    observability jsonb default '{}'::jsonb,
    last_reply text,
    updated_at timestamptz default now()
);

create table if not exists public.channel_history (
    id bigint generated always as identity primary key,
    channel_id text not null,
    author text not null,
    message text not null,
    ts timestamptz default now()
);

-- 4. Tables for Specialized Features (Clips, Webhooks, Memory)
create table if not exists public.post_stream_reports (
    id bigint generated always as identity primary key,
    channel_id text not null,
    report jsonb not null,
    generated_at timestamptz default now(),
    trigger text
);

create table if not exists public.revenue_conversions (
    id bigint generated always as identity primary key,
    channel_id text not null,
    conversion jsonb not null,
    timestamp timestamptz default now()
);

create table if not exists public.outbound_webhooks (
    id uuid primary key default gen_random_uuid(),
    channel_id text not null,
    url text not null,
    secret text,
    event_types text[] default '{}',
    is_active boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists public.outbound_webhook_deliveries (
    id uuid primary key default gen_random_uuid(),
    webhook_id uuid not null,
    channel_id text not null,
    event_type text not null,
    status_code int,
    success boolean,
    latency_ms int,
    timestamp timestamptz default now()
);

-- 5. Semantic Memory with pgvector
create table if not exists public.semantic_memory_entries (
    entry_id uuid primary key default gen_random_uuid(),
    channel_id text not null,
    memory_type text not null,
    content text not null,
    tags text[] default '{}',
    context jsonb default '{}'::jsonb,
    embedding vector(1536), -- Standard OpenAI/Kimi embedding size
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 6. RPC Functions for Semantic Search
create or replace function public.semantic_memory_search_pgvector(
    p_channel_id text,
    p_query_embedding vector(1536),
    p_limit int,
    p_search_limit int
) returns table (
    entry_id uuid,
    memory_type text,
    content text,
    tags text[],
    context jsonb,
    embedding vector(1536),
    created_at timestamptz,
    updated_at timestamptz,
    similarity float
) language plpgsql as $$
begin
    return query
    select
        s.entry_id,
        s.memory_type,
        s.content,
        s.tags,
        s.context,
        s.embedding,
        s.created_at,
        s.updated_at,
        1 - (s.embedding <=> p_query_embedding) as similarity
    from public.semantic_memory_entries s
    where s.channel_id = p_channel_id
    order by similarity desc
    limit p_limit;
end;
$$;

-- Enable Realtime for observability (optional but recommended)
alter publication supabase_realtime add table public.observability_channel_history;
