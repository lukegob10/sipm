-- SIPM solution escalation migration v1
-- Adds a short escalation field to solutions.
-- Safe to rerun; the block checks current Oracle schema state.

DECLARE
	v_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_SOLUTIONS'
	  AND column_name = 'ESCALATION';

	IF v_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOLUTIONS" ADD (escalation VARCHAR2(255 CHAR))';
	END IF;
END;
/

COMMIT;
