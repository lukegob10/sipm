-- SIPM public program dashboard migration v1
-- Adds a per-space switch for exposing the read-only public program dashboard.
-- Safe to rerun; the block checks current Oracle schema state.

DECLARE
	v_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_SPACES'
	  AND column_name = 'PUBLIC_PROGRAM_DASHBOARD_ENABLED';

	IF v_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SPACES" ADD (public_program_dashboard_enabled SMALLINT DEFAULT 0 NOT NULL)';
	END IF;
END;
/

COMMIT;
