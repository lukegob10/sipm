-- First-deploy SIPM reference data bootstrap.
--
-- Purpose:
--   Populate canonical reference rows required by the application after
--   docs/sql/schema_oracle_ta.sql has created the schema.
--
-- Operator note:
--   This script is idempotent. It can be rerun after deploys to restore the
--   expected phase catalog without deleting existing transactional data.

SET DEFINE OFF;

MERGE INTO "TB_TA_PM_PHASES" p
USING (
  SELECT 'backlog' phase_id, 'Intake / Backlog' phase_group, 'Intake / Backlog' phase_name, 1 sequence FROM dual UNION ALL
  SELECT 'requirements', 'Requirements / Specification', 'Requirements / Specification', 2 FROM dual UNION ALL
  SELECT 'development', 'Development', 'Development', 3 FROM dual UNION ALL
  SELECT 'testing', 'Testing', 'Testing', 4 FROM dual UNION ALL
  SELECT 'deployment', 'Deployment', 'Deployment', 5 FROM dual UNION ALL
  SELECT 'go_live', 'Go Live', 'Go Live', 6 FROM dual UNION ALL
  SELECT 'retired', 'Retired', 'Retired', 7 FROM dual
) s
ON (p.phase_id = s.phase_id)
WHEN MATCHED THEN UPDATE SET
  p.phase_group = s.phase_group,
  p.phase_name = s.phase_name,
  p.sequence = s.sequence,
  p.updated_at = SYSDATE
WHEN NOT MATCHED THEN INSERT (
  phase_id,
  phase_group,
  phase_name,
  sequence,
  created_at,
  updated_at
) VALUES (
  s.phase_id,
  s.phase_group,
  s.phase_name,
  s.sequence,
  SYSDATE,
  SYSDATE
);

COMMIT;

SELECT phase_id, phase_group, phase_name, sequence
FROM "TB_TA_PM_PHASES"
ORDER BY sequence;
