-- SIPM task description migration v1.
-- Adds task-level context. Safe to rerun.

DECLARE
	column_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
		AND column_name = 'DESCRIPTION';

	IF column_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_TASKS" ADD (description CLOB)';
	END IF;
END;
/

COMMIT;
