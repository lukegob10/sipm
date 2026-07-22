-- SIPM project owner migration v1.
-- Adds project-level owner identity. Safe to rerun.

DECLARE
	column_count INTEGER;
	index_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_PROJECTS'
		AND column_name = 'OWNER';

	IF column_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_PROJECTS" ADD (owner VARCHAR2(255 CHAR))';
	END IF;

	EXECUTE IMMEDIATE 'UPDATE "TB_TA_PM_PROJECTS" SET owner = sponsor WHERE owner IS NULL';
	EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_PROJECTS" MODIFY (owner NOT NULL)';

	SELECT COUNT(*) INTO column_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_PROJECTS'
		AND column_name = 'OWNER_USER_SOEID';

	IF column_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_PROJECTS" ADD (owner_user_soeid VARCHAR2(255 CHAR))';
	END IF;

	SELECT COUNT(*) INTO index_count
	FROM user_indexes
	WHERE UPPER(index_name) = UPPER('ix_TB_TA_PM_PROJECTS_owner_user_soeid');

	IF index_count = 0 THEN
		EXECUTE IMMEDIATE 'CREATE INDEX "ix_TB_TA_PM_PROJECTS_owner_user_soeid" ON "TB_TA_PM_PROJECTS" (owner_user_soeid)';
	END IF;
END;
/

COMMIT;
