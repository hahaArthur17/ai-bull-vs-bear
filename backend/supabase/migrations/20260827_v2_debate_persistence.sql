-- Add canonical, user-owned persistence for the V2 multi-turn Debate.
-- Queue transport remains a separate Phase 5 migration; debate_jobs is only
-- the application ledger and contains no credentials or protected prompt text.

create table if not exists public.debate_sessions (
  id uuid primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  stock_id bigint not null references public.stocks(id) on delete restrict,
  ticker text not null,
  mode text not null check (mode in ('live', 'demo', 'replay')),
  status text not null default 'created' check (status in (
    'created',
    'queued_round_1',
    'running_round_1',
    'awaiting_user',
    'queued_round_2',
    'running_round_2',
    'completed',
    'cancel_requested',
    'cancelled',
    'failed'
  )),
  opening_side text not null check (opening_side in ('bull', 'bear')),
  initial_question text,
  active_branch_id uuid not null,
  active_generation_id uuid not null,
  analysis_context jsonb not null,
  factor_snapshot jsonb not null,
  interim_judge_message_id uuid,
  final_judge_message_id uuid,
  guardrail_status text not null default 'pending' check (
    guardrail_status in ('pending', 'passed', 'rewritten', 'failed')
  ),
  safe_error_code text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  completed_at timestamptz,
  constraint debate_sessions_id_owner_unique unique (id, user_id),
  constraint debate_sessions_ticker_shape check (
    char_length(ticker) between 1 and 16 and ticker = upper(ticker)
  ),
  constraint debate_sessions_question_length check (
    initial_question is null or char_length(initial_question) <= 500
  ),
  constraint debate_sessions_context_object check (
    jsonb_typeof(analysis_context) = 'object'
  ),
  constraint debate_sessions_factor_snapshot_object check (
    jsonb_typeof(factor_snapshot) = 'object'
  ),
  constraint debate_sessions_updated_after_created check (updated_at >= created_at),
  constraint debate_sessions_terminal_timestamp check (
    (status in ('completed', 'cancelled', 'failed') and completed_at is not null)
    or
    (status not in ('completed', 'cancelled', 'failed') and completed_at is null)
  ),
  constraint debate_sessions_safe_error check (
    (status = 'failed' and safe_error_code is not null and char_length(safe_error_code) <= 80)
    or
    (status <> 'failed' and safe_error_code is null)
  )
);

create table if not exists public.debate_messages (
  id uuid primary key,
  session_id uuid not null references public.debate_sessions(id) on delete cascade,
  branch_id uuid not null,
  generation_id uuid not null,
  sequence_number integer not null check (sequence_number >= 1),
  round_number integer not null check (round_number between 0 and 2),
  exchange_number integer not null check (exchange_number between 0 and 3),
  role text not null check (role in ('bull', 'bear', 'judge', 'user', 'explainer', 'system')),
  message_kind text not null check (
    message_kind in ('argument', 'rebuttal', 'summary', 'question', 'explanation')
  ),
  content text not null default '',
  confidence text check (confidence is null or confidence in ('low', 'medium', 'high')),
  signal_strength text check (
    signal_strength is null or signal_strength in ('weak', 'medium', 'strong')
  ),
  terms text[] not null default '{}'::text[],
  metadata jsonb not null default '{}'::jsonb,
  is_complete boolean not null default true,
  cancelled_at timestamptz,
  created_at timestamptz not null,
  constraint debate_messages_session_branch_sequence_unique
    unique (session_id, branch_id, sequence_number),
  constraint debate_messages_id_session_unique unique (id, session_id),
  constraint debate_messages_content_length check (char_length(content) <= 6000),
  constraint debate_messages_terms_limit check (cardinality(terms) <= 12),
  constraint debate_messages_metadata_object check (jsonb_typeof(metadata) = 'object'),
  constraint debate_messages_role_kind check (
    (role in ('bull', 'bear') and message_kind in ('argument', 'rebuttal'))
    or (role = 'judge' and message_kind = 'summary')
    or (role = 'user' and message_kind = 'question')
    or (role = 'explainer' and message_kind = 'explanation')
    or (role = 'system' and message_kind = 'summary')
  ),
  constraint debate_messages_agent_round check (
    role not in ('bull', 'bear', 'judge') or round_number in (1, 2)
  ),
  constraint debate_messages_completion check (
    (is_complete and content <> '' and cancelled_at is null)
    or (not is_complete and cancelled_at is not null)
  )
);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'debate_sessions_interim_judge_fk'
      and conrelid = 'public.debate_sessions'::regclass
  ) then
    alter table public.debate_sessions
      add constraint debate_sessions_interim_judge_fk
      foreign key (interim_judge_message_id)
      references public.debate_messages(id)
      on delete set null
      deferrable initially deferred;
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'debate_sessions_final_judge_fk'
      and conrelid = 'public.debate_sessions'::regclass
  ) then
    alter table public.debate_sessions
      add constraint debate_sessions_final_judge_fk
      foreign key (final_judge_message_id)
      references public.debate_messages(id)
      on delete set null
      deferrable initially deferred;
  end if;
end
$$;

create table if not exists public.debate_message_evidence (
  message_id uuid not null references public.debate_messages(id) on delete cascade,
  evidence_id text not null,
  citation_order integer not null check (citation_order >= 1),
  support_span text,
  metadata jsonb not null default '{}'::jsonb,
  primary key (message_id, evidence_id),
  constraint debate_message_evidence_order_unique unique (message_id, citation_order),
  constraint debate_message_evidence_id_length check (
    char_length(evidence_id) between 1 and 240
  ),
  constraint debate_message_evidence_span_length check (
    support_span is null or char_length(support_span) <= 500
  ),
  constraint debate_message_evidence_metadata_object check (
    jsonb_typeof(metadata) = 'object'
  )
);

create table if not exists public.debate_interventions (
  id uuid primary key,
  session_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  selected_message_id uuid not null,
  selected_text text not null,
  question text not null,
  mode text not null check (mode in ('explain', 'challenge')),
  created_at timestamptz not null,
  constraint debate_interventions_session_owner_fk
    foreign key (session_id, user_id)
    references public.debate_sessions(id, user_id)
    on delete cascade,
  constraint debate_interventions_selected_message_fk
    foreign key (selected_message_id, session_id)
    references public.debate_messages(id, session_id)
    on delete cascade,
  constraint debate_interventions_selected_text_length check (
    char_length(selected_text) between 1 and 500
  ),
  constraint debate_interventions_question_length check (
    char_length(question) between 1 and 500
  )
);

create table if not exists public.debate_jobs (
  id uuid primary key,
  session_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  job_type text not null check (job_type in ('round_1', 'round_2', 'explanation', 'replay')),
  status text not null default 'queued' check (
    status in ('queued', 'running', 'completed', 'failed', 'cancelled')
  ),
  idempotency_key text not null unique,
  queue_message_id bigint check (queue_message_id is null or queue_message_id > 0),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  available_at timestamptz not null,
  started_at timestamptz,
  finished_at timestamptz,
  safe_error_code text,
  provider_request_count integer not null default 0 check (provider_request_count >= 0),
  prompt_tokens integer not null default 0 check (prompt_tokens >= 0),
  completion_tokens integer not null default 0 check (completion_tokens >= 0),
  total_tokens integer not null default 0 check (total_tokens >= 0),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  constraint debate_jobs_session_owner_fk
    foreign key (session_id, user_id)
    references public.debate_sessions(id, user_id)
    on delete cascade,
  constraint debate_jobs_idempotency_key_length check (
    char_length(idempotency_key) between 8 and 200
  ),
  constraint debate_jobs_attempt_limit check (attempt_count <= max_attempts),
  constraint debate_jobs_updated_after_created check (updated_at >= created_at),
  constraint debate_jobs_token_sum check (
    total_tokens = prompt_tokens + completion_tokens
  ),
  constraint debate_jobs_running_state check (
    status <> 'running'
    or (started_at is not null and finished_at is null and attempt_count >= 1)
  ),
  constraint debate_jobs_terminal_timestamp check (
    (status in ('completed', 'failed', 'cancelled') and finished_at is not null)
    or
    (status not in ('completed', 'failed', 'cancelled') and finished_at is null)
  ),
  constraint debate_jobs_completed_started check (
    status <> 'completed' or started_at is not null
  ),
  constraint debate_jobs_safe_error check (
    (status = 'failed' and safe_error_code is not null and char_length(safe_error_code) <= 80)
    or
    (status <> 'failed' and safe_error_code is null)
  )
);

create index if not exists debate_sessions_user_created_idx
  on public.debate_sessions (user_id, created_at desc);

create index if not exists debate_sessions_status_updated_idx
  on public.debate_sessions (status, updated_at);

create index if not exists debate_messages_generation_idx
  on public.debate_messages (session_id, generation_id, sequence_number);

create index if not exists debate_interventions_session_created_idx
  on public.debate_interventions (session_id, created_at);

create index if not exists debate_jobs_worker_claim_idx
  on public.debate_jobs (status, available_at, created_at);

create index if not exists debate_jobs_session_created_idx
  on public.debate_jobs (session_id, created_at);

alter table public.debate_sessions enable row level security;
alter table public.debate_messages enable row level security;
alter table public.debate_message_evidence enable row level security;
alter table public.debate_interventions enable row level security;
alter table public.debate_jobs enable row level security;

revoke all on table
  public.debate_sessions,
  public.debate_messages,
  public.debate_message_evidence,
  public.debate_interventions,
  public.debate_jobs
from anon, authenticated;

grant select on table
  public.debate_sessions,
  public.debate_messages,
  public.debate_message_evidence,
  public.debate_interventions,
  public.debate_jobs
to authenticated;

grant all privileges on table
  public.debate_sessions,
  public.debate_messages,
  public.debate_message_evidence,
  public.debate_interventions,
  public.debate_jobs
to service_role;

drop policy if exists "Users can read their own Debate sessions"
  on public.debate_sessions;
create policy "Users can read their own Debate sessions"
  on public.debate_sessions for select
  using (auth.uid() = user_id);

drop policy if exists "Users can read messages from their Debate sessions"
  on public.debate_messages;
create policy "Users can read messages from their Debate sessions"
  on public.debate_messages for select
  using (
    exists (
      select 1 from public.debate_sessions
      where debate_sessions.id = debate_messages.session_id
        and debate_sessions.user_id = auth.uid()
    )
  );

drop policy if exists "Users can read citations from their Debate sessions"
  on public.debate_message_evidence;
create policy "Users can read citations from their Debate sessions"
  on public.debate_message_evidence for select
  using (
    exists (
      select 1
      from public.debate_messages
      join public.debate_sessions
        on debate_sessions.id = debate_messages.session_id
      where debate_messages.id = debate_message_evidence.message_id
        and debate_sessions.user_id = auth.uid()
    )
  );

drop policy if exists "Users can read interventions from their Debate sessions"
  on public.debate_interventions;
create policy "Users can read interventions from their Debate sessions"
  on public.debate_interventions for select
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.debate_sessions
      where debate_sessions.id = debate_interventions.session_id
        and debate_sessions.user_id = auth.uid()
    )
  );

drop policy if exists "Users can read jobs from their Debate sessions"
  on public.debate_jobs;
create policy "Users can read jobs from their Debate sessions"
  on public.debate_jobs for select
  using (
    auth.uid() = user_id
    and exists (
      select 1 from public.debate_sessions
      where debate_sessions.id = debate_jobs.session_id
        and debate_sessions.user_id = auth.uid()
    )
  );
