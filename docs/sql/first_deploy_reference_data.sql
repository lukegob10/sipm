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
  SELECT 'backlog' phase_id, 'Backlog' phase_group, 'Backlog' phase_name, 1 sequence FROM dual UNION ALL
  SELECT 'requirements', 'Planning', 'Requirements', 2 FROM dual UNION ALL
  SELECT 'controls_scoping', 'Planning', 'Controls & Scoping', 3 FROM dual UNION ALL
  SELECT 'resourcing_timeline', 'Planning', 'Resourcing & Timeline', 4 FROM dual UNION ALL
  SELECT 'poc', 'Planning', 'Proof of Concept', 5 FROM dual UNION ALL
  SELECT 'delivery_success', 'Planning', 'Delivery and Success Criteria', 6 FROM dual UNION ALL
  SELECT 'design', 'Development', 'Design', 7 FROM dual UNION ALL
  SELECT 'build_docs', 'Development', 'Build & Documentation', 8 FROM dual UNION ALL
  SELECT 'sandbox_deploy', 'Development', 'Sandbox Deployment', 9 FROM dual UNION ALL
  SELECT 'socialization_signoff', 'Development', 'Socialization & Signoff', 10 FROM dual UNION ALL
  SELECT 'deployment_prep', 'Deployment & Testing', 'Deployment Preparation', 11 FROM dual UNION ALL
  SELECT 'dev_deploy', 'Deployment & Testing', 'DEV Deployment', 12 FROM dual UNION ALL
  SELECT 'uat_deploy', 'Deployment & Testing', 'UAT Deployment', 13 FROM dual UNION ALL
  SELECT 'prod_deploy', 'Deployment & Testing', 'PROD Deployment', 14 FROM dual UNION ALL
  SELECT 'go_live', 'Closure', 'Go Live', 15 FROM dual UNION ALL
  SELECT 'closure_signoff', 'Closure', 'Closure and Signoff', 16 FROM dual UNION ALL
  SELECT 'handoff_offboarding', 'Closure', 'Handoff and offboarding', 17 FROM dual
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
