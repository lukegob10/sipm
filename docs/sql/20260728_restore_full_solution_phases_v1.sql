-- SIPM canonical 17-phase workflow restoration v1.
--
-- Purpose:
--   Restore the full solution lifecycle after the temporary seven-phase
--   catalog, normalize current phases, and enable every phase for every
--   solution. This script is idempotent.

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
  phase_id, phase_group, phase_name, sequence, created_at, updated_at
) VALUES (
  s.phase_id, s.phase_group, s.phase_name, s.sequence, SYSDATE, SYSDATE
);

UPDATE "TB_TA_PM_SOLUTIONS"
SET current_phase = CASE current_phase
  WHEN 'backlog' THEN 'backlog'
  WHEN 'requirements' THEN 'requirements'
  WHEN 'controls_scoping' THEN 'controls_scoping'
  WHEN 'resourcing_timeline' THEN 'resourcing_timeline'
  WHEN 'poc' THEN 'poc'
  WHEN 'delivery_success' THEN 'delivery_success'
  WHEN 'design' THEN 'design'
  WHEN 'build_docs' THEN 'build_docs'
  WHEN 'sandbox_deploy' THEN 'sandbox_deploy'
  WHEN 'socialization_signoff' THEN 'socialization_signoff'
  WHEN 'deployment_prep' THEN 'deployment_prep'
  WHEN 'dev_deploy' THEN 'dev_deploy'
  WHEN 'uat' THEN 'uat_deploy'
  WHEN 'uat_deploy' THEN 'uat_deploy'
  WHEN 'prod_deploy' THEN 'prod_deploy'
  WHEN 'go_live' THEN 'go_live'
  WHEN 'closure_signoff' THEN 'closure_signoff'
  WHEN 'handoff_offboarding' THEN 'handoff_offboarding'
  WHEN 'development' THEN 'build_docs'
  WHEN 'testing' THEN 'uat_deploy'
  WHEN 'deployment' THEN 'prod_deploy'
  WHEN 'retired' THEN 'handoff_offboarding'
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
    'backlog', 'requirements', 'controls_scoping', 'resourcing_timeline',
    'poc', 'delivery_success', 'design', 'build_docs', 'sandbox_deploy',
    'socialization_signoff', 'deployment_prep', 'dev_deploy', 'uat_deploy',
    'prod_deploy', 'go_live', 'closure_signoff', 'handoff_offboarding'
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
  'backlog', 'requirements', 'controls_scoping', 'resourcing_timeline',
  'poc', 'delivery_success', 'design', 'build_docs', 'sandbox_deploy',
  'socialization_signoff', 'deployment_prep', 'dev_deploy', 'uat_deploy',
  'prod_deploy', 'go_live', 'closure_signoff', 'handoff_offboarding'
);

DELETE FROM "TB_TA_PM_PHASES"
WHERE phase_id NOT IN (
  'backlog', 'requirements', 'controls_scoping', 'resourcing_timeline',
  'poc', 'delivery_success', 'design', 'build_docs', 'sandbox_deploy',
  'socialization_signoff', 'deployment_prep', 'dev_deploy', 'uat_deploy',
  'prod_deploy', 'go_live', 'closure_signoff', 'handoff_offboarding'
);

COMMIT;

SELECT phase_id, phase_group, phase_name, sequence
FROM "TB_TA_PM_PHASES"
ORDER BY sequence;
