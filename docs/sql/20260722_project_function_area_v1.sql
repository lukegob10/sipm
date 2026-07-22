-- SIPM project function and area migration v1.
-- Adds nullable free-form business classification fields. Safe to rerun.

DECLARE
	column_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_PROJECTS'
		AND column_name = 'FUNCTION';

	IF column_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_PROJECTS" ADD (function VARCHAR2(255 CHAR))';
	END IF;

	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_PROJECTS'
		AND column_name = 'AREA';

	IF column_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_PROJECTS" ADD (area VARCHAR2(255 CHAR))';
	END IF;
END;
/

COMMIT;
