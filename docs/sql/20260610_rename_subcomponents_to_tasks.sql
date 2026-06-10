-- SIPM rename subcomponents to tasks migration v1
-- Preserves existing data while applying the breaking storage rename:
-- Program -> Project -> Solution -> Task.
-- Run after the program umbrella migration if the target schema still uses
-- TB_TA_PM_SUBCOMPONENTS and subcomponent_id/subcomponent_name columns.

ALTER TABLE "TB_TA_PM_SUBCOMPONENTS" RENAME TO "TB_TA_PM_TASKS";

ALTER TABLE "TB_TA_PM_TASKS" RENAME COLUMN subcomponent_id TO task_id;
ALTER TABLE "TB_TA_PM_TASKS" RENAME COLUMN subcomponent_name TO task_name;

ALTER TABLE "TB_TA_PM_TASKS" RENAME CONSTRAINT uix_subcomponent_solution_name TO uix_task_solution_name;

ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_assignee_user_soeid" RENAME TO "ix_TB_TA_PM_TASKS_assignee_user_soeid";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_blocked" RENAME TO "ix_TB_TA_PM_TASKS_blocked";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_deleted_at" RENAME TO "ix_TB_TA_PM_TASKS_deleted_at";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_due_date" RENAME TO "ix_TB_TA_PM_TASKS_due_date";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_priority" RENAME TO "ix_TB_TA_PM_TASKS_priority";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_project_id" RENAME TO "ix_TB_TA_PM_TASKS_project_id";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_solution_id" RENAME TO "ix_TB_TA_PM_TASKS_solution_id";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_space_id" RENAME TO "ix_TB_TA_PM_TASKS_space_id";
ALTER INDEX "ix_TB_TA_PM_SUBCOMPONENTS_status" RENAME TO "ix_TB_TA_PM_TASKS_status";

UPDATE "TB_TA_PM_RESOURCE_ALLOCATIONS"
SET work_item_type = 'task'
WHERE work_item_type = 'subcomponent';

UPDATE "TB_TA_PM_CHANGE_LOG"
SET entity_type = 'task'
WHERE entity_type = 'subcomponent';

COMMIT;
