-- Run in Supabase Dashboard → SQL Editor after creating project.
-- Creates a public-read bucket for the gzipped sales CSV.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'sales-data',
  'sales-data',
  true,
  52428800,
  array['application/gzip', 'application/x-gzip', 'text/csv', 'application/octet-stream']
)
on conflict (id) do nothing;

-- Allow anyone to download (dashboard uses anon key)
create policy "Public read sales data"
on storage.objects for select
using (bucket_id = 'sales-data');

-- Allow service role uploads (handled by service role key; optional explicit policy)
create policy "Service role upload sales data"
on storage.objects for insert
with check (bucket_id = 'sales-data');

create policy "Service role update sales data"
on storage.objects for update
using (bucket_id = 'sales-data');
