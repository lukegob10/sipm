-- SIPM task assignment repair v1. Safe to rerun.
-- Oracle stores empty strings as NULL. Allow the task editor and batch actions
-- to save unassigned tasks without violating the assignee NOT NULL constraint.
-- Existing assignments and task status values are preserved.

DECLARE
	column_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
		AND column_name = 'ASSIGNEE'
		AND nullable = 'N';

	IF column_count > 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_TASKS" MODIFY (assignee NULL)';
	END IF;
END;
/
