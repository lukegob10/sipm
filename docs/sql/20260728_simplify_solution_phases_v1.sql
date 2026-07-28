-- SIPM canonical seven-phase workflow migration v1.
--
-- Purpose:
--   Replace the legacy 17-step phase catalog and per-solution phase subsets
--   with one fixed seven-phase workflow. This script is idempotent.

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
  phase_id, phase_group, phase_name, sequence, created_at, updated_at
) VALUES (
  s.phase_id, s.phase_group, s.phase_name, s.sequence, SYSDATE, SYSDATE
);

UPDATE "TB_TA_PM_SOLUTIONS"
SET current_phase = CASE current_phase
  WHEN 'backlog' THEN 'backlog'
  WHEN 'requirements' THEN 'requirements'
  WHEN 'controls_scoping' THEN 'requirements'
  WHEN 'resourcing_timeline' THEN 'requirements'
  WHEN 'poc' THEN 'requirements'
  WHEN 'delivery_success' THEN 'requirements'
  WHEN 'design' THEN 'requirements'
  WHEN 'build_docs' THEN 'development'
  WHEN 'sandbox_deploy' THEN 'development'
  WHEN 'development' THEN 'development'
  WHEN 'socialization_signoff' THEN 'testing'
  WHEN 'dev_deploy' THEN 'testing'
  WHEN 'uat' THEN 'testing'
  WHEN 'uat_deploy' THEN 'testing'
  WHEN 'testing' THEN 'testing'
  WHEN 'deployment_prep' THEN 'deployment'
  WHEN 'prod_deploy' THEN 'deployment'
  WHEN 'deployment' THEN 'deployment'
  WHEN 'go_live' THEN 'go_live'
  WHEN 'closure_signoff' THEN 'retired'
  WHEN 'handoff_offboarding' THEN 'retired'
  WHEN 'retired' THEN 'retired'
  ELSE 'backlog'
END,
updated_at = SYSDATE
WHERE current_phase IS NOT NULL;

MERGE INTO "TB_TA_PM_SOLUTION_PHASES" sp
USING (
  SELECT
    solutions.solution_id,
    phases.phase_id
  FROM "TB_TA_PM_SOLUTIONS" solutions
  CROSS JOIN "TB_TA_PM_PHASES" phases
  WHERE phases.phase_id IN (
    'backlog', 'requirements', 'development', 'testing',
    'deployment', 'go_live', 'retired'
  )
) s
ON (sp.solution_id = s.solution_id AND sp.phase_id = s.phase_id)
WHEN MATCHED THEN UPDATE SET
  sp.is_enabled = 1,
  sp.sequence_override = NULL,
  sp.updated_at = SYSDATE
WHEN NOT MATCHED THEN INSERT (
  solution_phase_id, solution_id, phase_id, is_enabled,
  sequence_override, created_at, updated_at
) VALUES (
  LOWER(RAWTOHEX(SYS_GUID())), s.solution_id, s.phase_id, 1,
  NULL, SYSDATE, SYSDATE
);

DELETE FROM "TB_TA_PM_SOLUTION_PHASES"
WHERE phase_id NOT IN (
  'backlog', 'requirements', 'development', 'testing',
  'deployment', 'go_live', 'retired'
);

DELETE FROM "TB_TA_PM_PHASES"
WHERE phase_id NOT IN (
  'backlog', 'requirements', 'development', 'testing',
  'deployment', 'go_live', 'retired'
);

COMMIT;

SELECT phase_id, phase_group, phase_name, sequence
FROM "TB_TA_PM_PHASES"
ORDER BY sequence;
