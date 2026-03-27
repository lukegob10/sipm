-- Oracle structural schema drift validator for SIPM.
-- Checks missing/unexpected tables and columns against docs/sql/schema_oracle_ta.sql.
-- Run as the application schema owner.

WITH
expected_tables AS (
  SELECT 'TB_TA_PM_EXTERNAL_REF' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_PHASES' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SPACES' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_USERS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_CHANGE_LOG' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_PLANNING_WINDOWS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_PROJECTS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SPACE_MEMBERSHIPS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_TEAMS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_RESOURCE_ALLOCATIONS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTIONS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_TEAM_MEMBERS' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTION_PHASES' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT' AS table_name FROM dual
  UNION ALL
  SELECT 'TB_TA_PM_SUBCOMPONENTS' AS table_name FROM dual
),
expected_columns AS (
  SELECT 'TB_TA_PM_EXTERNAL_REF' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('EXTERNAL_REF_ID', 'WORK_ITEM_TYPE', 'WORK_ITEM_ID', 'REF_TYPE', 'REF_URL', 'REF_KEY', 'LABEL', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_PHASES' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('PHASE_ID', 'PHASE_GROUP', 'PHASE_NAME', 'SEQUENCE', 'CREATED_AT', 'UPDATED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SPACES' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('SPACE_ID', 'NAME', 'SLUG', 'IS_ACTIVE', 'ARCHIVED_AT', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_USERS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('USER_ID', 'SOEID', 'EMAIL', 'DISPLAY_NAME', 'PASSWORD_HASH', 'ROLE', 'IS_ACTIVE', 'TEAM_TAG', 'CAPACITY_HOURS', 'CAPACITY_FTE_MONTH', 'FAILED_ATTEMPTS', 'LOCKED_UNTIL', 'LAST_LOGIN_AT', 'EXTERNAL_ID', 'TEMP_PASSWORD_HASH', 'TEMP_PASSWORD_EXPIRES_AT', 'FORCE_PASSWORD_RESET', 'PASSWORD_CHANGED_AT', 'CREATED_AT', 'UPDATED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_CHANGE_LOG' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('CHANGE_ID', 'ENTITY_TYPE', 'ENTITY_ID', 'ACTION', 'FIELD', 'OLD_VALUE', 'NEW_VALUE', 'USER_ID', 'SPACE_ID', 'REQUEST_ID', 'CREATED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_PLANNING_WINDOWS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('WINDOW_ID', 'SPACE_ID', 'NAME', 'START_DATE', 'END_DATE', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_PROJECTS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('PROJECT_ID', 'SPACE_ID', 'PROJECT_NAME', 'STATUS', 'DESCRIPTION', 'SUCCESS_CRITERIA', 'SPONSOR', 'SPONSOR_USER_SOEID', 'STRATEGIC_OBJECTIVE', 'PRIORITY', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SPACE_MEMBERSHIPS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('MEMBERSHIP_ID', 'SPACE_ID', 'USER_ID', 'ROLE', 'STATUS', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_TEAMS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('TEAM_ID', 'SPACE_ID', 'NAME', 'DESCRIPTION', 'LEAD', 'DEFAULT_CAPACITY_PER_WEEK', 'DEFAULT_CAPACITY_FTE_MONTH', 'CAPACITY_UNIT', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_RESOURCE_ALLOCATIONS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('ALLOCATION_ID', 'SPACE_ID', 'WORK_ITEM_TYPE', 'WORK_ITEM_ID', 'ASSIGNEE_USER_SOEID', 'ASSIGNEE', 'TEAM_ID', 'WEEK_START', 'MONTH_START', 'HOURS', 'FTE_MONTHS', 'WINDOW_ID', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTIONS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('SOLUTION_ID', 'SPACE_ID', 'PROJECT_ID', 'SOLUTION_NAME', 'VERSION', 'STATUS', 'RAG_STATUS', 'RAG_REASON', 'PRIORITY', 'DUE_DATE', 'CURRENT_PHASE', 'DESCRIPTION', 'SUCCESS_CRITERIA', 'PROBLEM_STATEMENT', 'GITHUB_REPO_URL', 'OWNER', 'OWNER_USER_SOEID', 'ASSIGNEE', 'ASSIGNEE_USER_SOEID', 'APPROVER', 'APPROVER_USER_SOEID', 'KEY_STAKEHOLDER', 'BLOCKERS', 'RISKS', 'IMPACT_CONFIDENCE', 'PLANNED_START_DATE', 'RAG_CONFIDENCE', 'COMPLETED_AT', 'CAPACITY_HOURS', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_TEAM_MEMBERS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('TEAM_MEMBER_ID', 'SPACE_ID', 'TEAM_ID', 'MEMBER_NAME', 'ROLE', 'CAPACITY_OVERRIDE', 'CAPACITY_UNIT', 'HOURS_CAPACITY', 'CAPACITY_FTE_MONTH', 'POINTS_CAPACITY', 'PERCENT_CAPACITY', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTION_PHASES' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('SOLUTION_PHASE_ID', 'SOLUTION_ID', 'PHASE_ID', 'IS_ENABLED', 'SEQUENCE_OVERRIDE', 'CREATED_AT', 'UPDATED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SOLUTION_WEEKLY_SNAPSHOT' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('SNAPSHOT_ID', 'SOLUTION_ID', 'WEEK_START', 'RAG_STATUS', 'PROGRESS_NOTE', 'NEXT_WEEK_PLAN', 'CONFIDENCE_ON_DUE_DATE', 'OWNER_USER_ID', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
  UNION ALL
  SELECT 'TB_TA_PM_SUBCOMPONENTS' AS table_name, column_value AS column_name
  FROM TABLE(sys.odcivarchar2list('SUBCOMPONENT_ID', 'SPACE_ID', 'PROJECT_ID', 'SOLUTION_ID', 'SUBCOMPONENT_NAME', 'STATUS', 'PRIORITY', 'DUE_DATE', 'COMPLETED_AT', 'ASSIGNEE_USER_SOEID', 'ASSIGNEE', 'GITHUB_REPO_URL', 'ESTIMATE_HOURS', 'BLOCKED', 'BLOCKER_NOTE', 'DONE_CRITERIA', 'CAPACITY_HOURS', 'CREATED_AT', 'UPDATED_AT', 'DELETED_AT'))
),
actual_tables AS (
  SELECT table_name FROM user_tables WHERE table_name LIKE 'TB_TA_PM_%'
),
actual_columns AS (
  SELECT table_name, column_name
  FROM user_tab_columns
  WHERE table_name IN (SELECT table_name FROM expected_tables)
)
SELECT *
FROM (
  SELECT 'MISSING_TABLE' AS issue_type, e.table_name AS object_name, CAST(NULL AS VARCHAR2(128)) AS column_name
  FROM expected_tables e
  LEFT JOIN actual_tables a ON a.table_name = e.table_name
  WHERE a.table_name IS NULL

  UNION ALL

  SELECT 'UNEXPECTED_TABLE' AS issue_type, a.table_name AS object_name, CAST(NULL AS VARCHAR2(128)) AS column_name
  FROM actual_tables a
  LEFT JOIN expected_tables e ON e.table_name = a.table_name
  WHERE e.table_name IS NULL

  UNION ALL

  SELECT 'MISSING_COLUMN' AS issue_type, e.table_name AS object_name, e.column_name
  FROM expected_columns e
  LEFT JOIN actual_columns a ON a.table_name = e.table_name AND a.column_name = e.column_name
  WHERE a.column_name IS NULL

  UNION ALL

  SELECT 'UNEXPECTED_COLUMN' AS issue_type, a.table_name AS object_name, a.column_name
  FROM actual_columns a
  LEFT JOIN expected_columns e ON e.table_name = a.table_name AND e.column_name = a.column_name
  WHERE e.column_name IS NULL
)
ORDER BY issue_type, object_name, column_name;
