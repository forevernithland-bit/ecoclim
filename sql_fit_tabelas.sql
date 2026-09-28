-- =====================================================================
-- App Evolua (fitness) — tabelas no MESMO Supabase da Ecoclim.
-- Tudo com prefixo fit_ e bucket fit-fotos, pra não misturar com o ERP e
-- facilitar mover pra um projeto próprio no futuro (é só copiar estas
-- tabelas + o bucket).
--
-- Segurança: usa Supabase Auth (login por e-mail) + RLS. Cada usuário só lê
-- e grava as próprias linhas e as próprias fotos (fotos do corpo = dado
-- sensível). Rode este arquivo inteiro no SQL Editor do Supabase, uma vez.
-- =====================================================================

create table if not exists fit_perfis (
  usuario_id uuid primary key references auth.users(id) on delete cascade,
  dados jsonb not null default '{}'::jsonb,
  atualizado_em timestamptz not null default now()
);

-- Mesmo formato para todos os registros do app: id do aparelho, data, jsonb.
do $$
declare t text;
begin
  foreach t in array array['fit_refeicoes','fit_checkins','fit_treinos','fit_chat','fit_metricas','fit_comparativos'] loop
    execute format('
      create table if not exists %I (
        id text primary key,
        usuario_id uuid not null references auth.users(id) on delete cascade,
        data date not null,
        dados jsonb not null default ''{}''::jsonb,
        atualizado_em timestamptz not null default now()
      )', t);
    execute format('create index if not exists %I on %I (usuario_id, data)', t || '_usuario_data', t);
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "dono" on %I', t);
    execute format('create policy "dono" on %I for all to authenticated using (usuario_id = auth.uid()) with check (usuario_id = auth.uid())', t);
  end loop;
end $$;

alter table fit_perfis enable row level security;
drop policy if exists "dono" on fit_perfis;
create policy "dono" on fit_perfis for all to authenticated
  using (usuario_id = auth.uid()) with check (usuario_id = auth.uid());

-- Bucket PRIVADO para as fotos (corpo e pratos). Caminho: <uid>/<tipo>/<arquivo>.jpg
insert into storage.buckets (id, name, public)
values ('fit-fotos', 'fit-fotos', false)
on conflict (id) do update set public = false;

drop policy if exists "fit fotos do dono - ler" on storage.objects;
drop policy if exists "fit fotos do dono - gravar" on storage.objects;
drop policy if exists "fit fotos do dono - atualizar" on storage.objects;
drop policy if exists "fit fotos do dono - apagar" on storage.objects;

create policy "fit fotos do dono - ler" on storage.objects for select to authenticated
  using (bucket_id = 'fit-fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "fit fotos do dono - gravar" on storage.objects for insert to authenticated
  with check (bucket_id = 'fit-fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "fit fotos do dono - atualizar" on storage.objects for update to authenticated
  using (bucket_id = 'fit-fotos' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "fit fotos do dono - apagar" on storage.objects for delete to authenticated
  using (bucket_id = 'fit-fotos' and (storage.foldername(name))[1] = auth.uid()::text);
