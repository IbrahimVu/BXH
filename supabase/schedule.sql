-- Chỉ chạy trên dự án Supabase của BXH. Lưu token trong Vault trước khi chạy.
begin;

create extension if not exists pg_cron;
create extension if not exists pg_net;

do $$
begin
  if (
    select count(*)
    from vault.decrypted_secrets
    where name = 'bxh_github_actions_token'
      and length(btrim(decrypted_secret)) > 0
  ) <> 1 then
    raise exception 'Cần có đúng một token bxh_github_actions_token trong Supabase Vault';
  end if;

  if current_setting('cron.timezone') not in ('GMT', 'UTC', 'Etc/UTC', 'Etc/GMT') then
    raise exception 'Điều chỉnh giờ cron theo múi giờ hiện tại (%) trước khi áp dụng', current_setting('cron.timezone');
  end if;
end;
$$;

-- Tạo lịch 12:00 và 23:59 giờ Hà Nội (05:00 và 16:59 UTC).
do $schedule$
declare
  dispatch_sql constant text := $job$
  select net.http_post(
    url := 'https://api.github.com/repos/IbrahimVu/BXH/actions/workflows/pages.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'bxh_github_actions_token'
      ),
      'Accept', 'application/vnd.github+json',
      'Content-Type', 'application/json',
      'X-GitHub-Api-Version', '2026-03-10',
      'User-Agent', 'BXH-Supabase-Cron'
    ),
    body := jsonb_build_object('ref', 'master'),
    timeout_milliseconds := 10000
  ) as request_id;
  $job$;
begin
  perform cron.schedule('bxh-github-pages-crawl', '59 16 * * *', dispatch_sql);
  perform cron.schedule('bxh-github-pages-crawl-noon', '0 5 * * *', dispatch_sql);
end;
$schedule$;

commit;
