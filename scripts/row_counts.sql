-- Row count of every table in schema public, one "table|count" line each, sorted by name.
-- Used by scripts/compose_smoke.sh and scripts/restore_backup.sh (MKC-11.4), and by the
-- restore drill against production (runbook "Backups and restore drill").
SELECT table_name || '|' || (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;
