-- Oracle migration: widen long-form project/solution narrative fields and audit values to CLOB.
-- Safe to run once per database. Each column is skipped if it is already CLOB.

DECLARE
    PROCEDURE widen_nullable_clob(
        p_table_name IN VARCHAR2,
        p_column_name IN VARCHAR2,
        p_tmp_column_name IN VARCHAR2
    ) IS
        l_data_type VARCHAR2(30);
        l_tmp_exists NUMBER := 0;
    BEGIN
        SELECT data_type
          INTO l_data_type
          FROM user_tab_columns
         WHERE table_name = p_table_name
           AND column_name = p_column_name;

        IF l_data_type = 'CLOB' THEN
            RETURN;
        END IF;

        SELECT COUNT(*)
          INTO l_tmp_exists
          FROM user_tab_columns
         WHERE table_name = p_table_name
           AND column_name = p_tmp_column_name;

        IF l_tmp_exists > 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE "' || p_table_name || '" DROP COLUMN "' || p_tmp_column_name || '"';
        END IF;

        EXECUTE IMMEDIATE 'ALTER TABLE "' || p_table_name || '" ADD ("' || p_tmp_column_name || '" CLOB)';
        EXECUTE IMMEDIATE 'UPDATE "' || p_table_name || '" SET "' || p_tmp_column_name || '" = "' || p_column_name || '"';
        COMMIT;

        EXECUTE IMMEDIATE 'ALTER TABLE "' || p_table_name || '" DROP COLUMN "' || p_column_name || '"';
        EXECUTE IMMEDIATE 'ALTER TABLE "' || p_table_name || '" RENAME COLUMN "' || p_tmp_column_name || '" TO "' || p_column_name || '"';
    END widen_nullable_clob;
BEGIN
    widen_nullable_clob('TB_TA_PM_PROJECTS', 'DESCRIPTION', 'DESCRIPTION_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_PROJECTS', 'SUCCESS_CRITERIA', 'SUCCESS_CRITERIA_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_SOLUTIONS', 'DESCRIPTION', 'DESCRIPTION_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_SOLUTIONS', 'SUCCESS_CRITERIA', 'SUCCESS_CRITERIA_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_SOLUTIONS', 'PROBLEM_STATEMENT', 'PROBLEM_STATEMENT_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_CHANGE_LOG', 'OLD_VALUE', 'OLD_VALUE_CLOB_TMP');
    widen_nullable_clob('TB_TA_PM_CHANGE_LOG', 'NEW_VALUE', 'NEW_VALUE_CLOB_TMP');
END;
/
