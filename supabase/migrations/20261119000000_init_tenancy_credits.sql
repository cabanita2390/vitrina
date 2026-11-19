-- =============================================================================
-- Vitrina · Migración inicial: multi-tenant, kit de marca, créditos y costos.
--
-- Principios:
--   * Toda tabla de negocio lleva organization_id y RLS habilitada.
--   * Las funciones auxiliares de RLS viven en el esquema `private` (no expuesto
--     por PostgREST) y son SECURITY DEFINER con search_path vacío.
--   * credit_ledger es inmutable a nivel de base de datos (REVOKE + triggers).
--   * usage_costs es interno: sin políticas para usuarios (solo service_role).
-- =============================================================================

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to authenticated, service_role;

-- -----------------------------------------------------------------------------
-- Tipos
-- -----------------------------------------------------------------------------
create type public.organization_kind as enum ('business', 'institution');
create type public.membership_role as enum ('owner', 'admin', 'member');
create type public.sponsorship_status as enum ('active', 'paused', 'ended');
create type public.credit_reason as enum (
  'signup_bonus', 'manual_topup', 'sponsorship_grant',
  'job_charge', 'job_refund', 'adjustment'
);

-- -----------------------------------------------------------------------------
-- Utilidades
-- -----------------------------------------------------------------------------
create function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- organizations
-- -----------------------------------------------------------------------------
create table public.organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (char_length(name) between 1 and 120),
  kind        public.organization_kind not null default 'business',
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table public.organizations is 'Tenant. Negocio (autoservicio) o institución patrocinadora.';

create trigger organizations_updated_at
  before update on public.organizations
  for each row execute function private.set_updated_at();

-- -----------------------------------------------------------------------------
-- memberships
-- -----------------------------------------------------------------------------
create table public.memberships (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  user_id          uuid not null references auth.users (id) on delete cascade,
  role             public.membership_role not null default 'member',
  created_at       timestamptz not null default now(),
  unique (organization_id, user_id)
);
create index memberships_user_id_idx on public.memberships (user_id);

-- Funciones de RLS. SECURITY DEFINER evita recursión de RLS sobre memberships.
create function private.is_org_member(org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.memberships m
    where m.organization_id = org_id
      and m.user_id = (select auth.uid())
  );
$$;

create function private.has_org_role(org_id uuid, roles public.membership_role[])
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.memberships m
    where m.organization_id = org_id
      and m.user_id = (select auth.uid())
      and m.role = any (roles)
  );
$$;

revoke all on function private.is_org_member(uuid) from public;
revoke all on function private.has_org_role(uuid, public.membership_role[]) from public;
grant execute on function private.is_org_member(uuid) to authenticated, service_role;
grant execute on function private.has_org_role(uuid, public.membership_role[]) to authenticated, service_role;

-- -----------------------------------------------------------------------------
-- sponsorships (institución -> negocio). Panel institucional en v2.
-- organization_id = negocio patrocinado; institution_id = patrocinador.
-- -----------------------------------------------------------------------------
create table public.sponsorships (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  institution_id   uuid not null references public.organizations (id) on delete cascade,
  status           public.sponsorship_status not null default 'active',
  starts_at        timestamptz not null default now(),
  ends_at          timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (organization_id, institution_id),
  check (organization_id <> institution_id),
  check (ends_at is null or ends_at > starts_at)
);
create index sponsorships_institution_id_idx on public.sponsorships (institution_id);

create trigger sponsorships_updated_at
  before update on public.sponsorships
  for each row execute function private.set_updated_at();

-- -----------------------------------------------------------------------------
-- brand_kits
-- -----------------------------------------------------------------------------
create table public.brand_kits (
  id                    uuid primary key default gen_random_uuid(),
  organization_id       uuid not null references public.organizations (id) on delete cascade,
  name                  text not null check (char_length(name) between 1 and 120),
  business_description  text,
  target_audience       text,
  tone                  text,
  city                  text,
  colors                jsonb not null default '[]'::jsonb,
  fonts                 jsonb not null default '{}'::jsonb,
  logo_asset_id         uuid,  -- FK a assets cuando exista la tabla
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);
create index brand_kits_organization_id_idx on public.brand_kits (organization_id);

create trigger brand_kits_updated_at
  before update on public.brand_kits
  for each row execute function private.set_updated_at();

-- -----------------------------------------------------------------------------
-- credit_rates (configuración de plataforma, sin organization_id)
-- Créditos que cuesta cada unidad de un proveedor/operación.
-- -----------------------------------------------------------------------------
create table public.credit_rates (
  id                uuid primary key default gen_random_uuid(),
  provider          text not null,          -- anthropic, kokoro, remotion, fal, ...
  operation         text not null,          -- llm_call, tts, render_template, video_ai
  unit              text not null,          -- request, second, character, 1k_tokens
  credits_per_unit  numeric(12, 4) not null check (credits_per_unit >= 0),
  effective_from    timestamptz not null default now(),
  active            boolean not null default true,
  created_at        timestamptz not null default now(),
  unique (provider, operation, unit, effective_from)
);

-- -----------------------------------------------------------------------------
-- credit_ledger: libro inmutable. Saldo = sum(delta).
-- idempotency_key garantiza que un trabajo nunca se cobre dos veces.
-- -----------------------------------------------------------------------------
create table public.credit_ledger (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete restrict,
  delta            integer not null check (delta <> 0),
  reason           public.credit_reason not null,
  idempotency_key  text not null check (char_length(idempotency_key) between 1 and 200),
  job_id           text,
  created_by       uuid references auth.users (id) on delete set null,
  metadata         jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now(),
  unique (organization_id, idempotency_key)
);
create index credit_ledger_org_created_idx on public.credit_ledger (organization_id, created_at desc);

create function private.forbid_ledger_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'credit_ledger es inmutable: % no permitido. Registra un ajuste compensatorio.', tg_op
    using errcode = 'insufficient_privilege';
end;
$$;

create trigger credit_ledger_no_update_delete
  before update or delete on public.credit_ledger
  for each row execute function private.forbid_ledger_mutation();

create trigger credit_ledger_no_truncate
  before truncate on public.credit_ledger
  for each statement execute function private.forbid_ledger_mutation();

-- Saldo calculado (security_invoker: respeta la RLS de quien consulta).
create view public.credit_balances
with (security_invoker = true) as
  select organization_id, coalesce(sum(delta), 0)::bigint as balance
  from public.credit_ledger
  group by organization_id;

-- -----------------------------------------------------------------------------
-- usage_costs: costo real por trabajo (interno; fuente de verdad del presupuesto).
-- -----------------------------------------------------------------------------
create table public.usage_costs (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete restrict,
  job_id           text,
  provider         text not null,
  model            text,
  operation        text not null,
  input_tokens     integer check (input_tokens >= 0),
  output_tokens    integer check (output_tokens >= 0),
  characters       integer check (characters >= 0),
  seconds          numeric(12, 3) check (seconds >= 0),
  usd_cost         numeric(12, 6) not null check (usd_cost >= 0),
  metadata         jsonb not null default '{}'::jsonb,
  created_at       timestamptz not null default now()
);
create index usage_costs_created_at_idx on public.usage_costs (created_at);
create index usage_costs_org_created_idx on public.usage_costs (organization_id, created_at desc);

-- -----------------------------------------------------------------------------
-- Permisos base: anon no toca tablas de negocio; los usuarios autenticados
-- dependen de la RLS. Nadie (ni service_role) puede modificar el ledger.
-- -----------------------------------------------------------------------------
revoke all on all tables in schema public from anon;
revoke update, delete, truncate on public.credit_ledger from public, anon, authenticated, service_role;
revoke insert on public.credit_ledger from authenticated;
revoke insert, update, delete, truncate on public.usage_costs from anon, authenticated;
revoke insert, update, delete, truncate on public.credit_rates from anon, authenticated;
revoke insert, update, delete, truncate on public.memberships from anon, authenticated;
revoke insert, update, delete, truncate on public.sponsorships from anon, authenticated;
revoke insert, delete, truncate on public.organizations from anon, authenticated;
revoke truncate on public.brand_kits from anon, authenticated;

-- -----------------------------------------------------------------------------
-- RLS
-- -----------------------------------------------------------------------------
alter table public.organizations enable row level security;
alter table public.memberships   enable row level security;
alter table public.sponsorships  enable row level security;
alter table public.brand_kits    enable row level security;
alter table public.credit_rates  enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.usage_costs   enable row level security;

-- organizations: los miembros leen; owner/admin editan. Altas y bajas por el sistema.
create policy organizations_select on public.organizations
  for select to authenticated
  using ((select private.is_org_member(id)));

create policy organizations_update on public.organizations
  for update to authenticated
  using ((select private.has_org_role(id, array['owner', 'admin']::public.membership_role[])))
  with check ((select private.has_org_role(id, array['owner', 'admin']::public.membership_role[])));

-- memberships: los miembros ven a su equipo. Escrituras vía API (service_role) en v1.
create policy memberships_select on public.memberships
  for select to authenticated
  using ((select private.is_org_member(organization_id)));

-- sponsorships: visibles para el negocio y para la institución.
create policy sponsorships_select on public.sponsorships
  for select to authenticated
  using (
    (select private.is_org_member(organization_id))
    or (select private.is_org_member(institution_id))
  );

-- brand_kits: CRUD para miembros de la organización; borrar solo owner/admin.
create policy brand_kits_select on public.brand_kits
  for select to authenticated
  using ((select private.is_org_member(organization_id)));
create policy brand_kits_insert on public.brand_kits
  for insert to authenticated
  with check ((select private.is_org_member(organization_id)));
create policy brand_kits_update on public.brand_kits
  for update to authenticated
  using ((select private.is_org_member(organization_id)))
  with check ((select private.is_org_member(organization_id)));
create policy brand_kits_delete on public.brand_kits
  for delete to authenticated
  using ((select private.has_org_role(organization_id, array['owner', 'admin']::public.membership_role[])));

-- credit_rates: tarifas visibles para usuarios autenticados.
create policy credit_rates_select on public.credit_rates
  for select to authenticated
  using (true);

-- credit_ledger: los miembros ven sus movimientos. Inserciones solo service_role.
create policy credit_ledger_select on public.credit_ledger
  for select to authenticated
  using ((select private.is_org_member(organization_id)));

-- usage_costs: sin políticas para authenticated => solo service_role (panel admin).

-- -----------------------------------------------------------------------------
-- Registro autoservicio: crea organización + membresía owner.
-- Nombre del negocio desde raw_user_meta_data.business_name (o el correo).
-- -----------------------------------------------------------------------------
create function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  new_org_id uuid;
  org_name   text;
begin
  org_name := nullif(btrim(coalesce(new.raw_user_meta_data ->> 'business_name', '')), '');
  if org_name is null then
    org_name := coalesce(nullif(split_part(coalesce(new.email, ''), '@', 1), ''), 'Mi negocio');
  end if;
  org_name := left(org_name, 120);

  insert into public.organizations (name, kind)
  values (org_name, 'business')
  returning id into new_org_id;

  insert into public.memberships (organization_id, user_id, role)
  values (new_org_id, new.id, 'owner');

  return new;
end;
$$;

revoke all on function private.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();
