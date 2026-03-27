-- Oracle migration: re-assert audit long-text columns as CLOB after partial or stale deploys.
-- This is intentionally idempotent and safe to rerun.
--
-- Why this exists:
-- Some environments already widened the primary project/solution tables but left
-- TB_TA_PM_CHANGE_LOG.OLD_VALUE or NEW_VALUE as VARCHAR2. That still breaks
-- create/update requests when audit logging writes long descriptions.
--
-- Run as a script so the anonymous block executes.

DECLARE
    PROCEDURE reassert_clob_column(
        p_table_name IN VARCHAR2,
        p_column_name IN VARCHAR2,
        p_tmp_column_name IN VARCHAR2
    ) IS
        l_column_exists NUMBER := 0;
        l_tmp_exists NUMBER := 0;
        l_data_type VARCHAR2(30);
        l_tmp_data_type VARCHAR2(30);
    BEGIN
        SELECT COUNT(*)
          INTO l_column_exists
          FROM user_tab_columns
         WHERE table_name = p_table_name
           AND column_name = p_column_name;

        SELECT COUNT(*)
          INTO l_tmp_exists
          FROM user_tab_columns
         WHERE table_name = p_table_name
           AND column_name = p_tmp_column_name;

        IF l_column_exists = 0 AND l_tmp_exists > 0 THEN
            SELECT data_type
              INTO l_tmp_data_type
              FROM user_tab_columns
             WHERE table_name = p_table_name
               AND column_name = p_tmp_column_name;

            IF l_tmp_data_type = 'CLOB' THEN
                EXECUTE IMMEDIATE
                    'ALTER TABLE "' || p_table_name || '" RENAME COLUMN "' || p_tmp_column_name || '" TO "' || p_column_name || '"';
                RETURN;
            END IF;

            raise_application_error(
                -20001,
                'Unexpected temp column type for ' || p_table_name || '.' || p_tmp_column_name || ': ' || l_tmp_data_type
            );
        END IF;

        IF l_column_exists = 0 THEN
            RETURN;
        END IF;

        SELECT data_type
          INTO l_data_type
          FROM user_tab_columns
         WHERE table_name = p_table_name
           AND column_name = p_column_name;

        IF l_data_type = 'CLOB' THEN
            IF l_tmp_exists > 0 THEN
                EXECUTE IMMEDIATE
                    'ALTER TABLE "' || p_table_name || '" DROP COLUMN "' || p_tmp_column_name || '"';
            END IF;
            RETURN;
        END IF;

        IF l_tmp_exists > 0 THEN
            EXECUTE IMMEDIATE
                'ALTER TABLE "' || p_table_name || '" DROP COLUMN "' || p_tmp_column_name || '"';
        END IF;

        EXECUTE IMMEDIATE
            'ALTER TABLE "' || p_table_name || '" ADD ("' || p_tmp_column_name || '" CLOB)';
        EXECUTE IMMEDIATE
            'UPDATE "' || p_table_name || '" SET "' || p_tmp_column_name || '" = "' || p_column_name || '"';
        COMMIT;

        EXECUTE IMMEDIATE
            'ALTER TABLE "' || p_table_name || '" DROP COLUMN "' || p_column_name || '"';
        EXECUTE IMMEDIATE
            'ALTER TABLE "' || p_table_name || '" RENAME COLUMN "' || p_tmp_column_name || '" TO "' || p_column_name || '"';
    END reassert_clob_column;
BEGIN
    reassert_clob_column('TB_TA_PM_CHANGE_LOG', 'OLD_VALUE', 'OLD_VALUE_CLOB_TMP');
    reassert_clob_column('TB_TA_PM_CHANGE_LOG', 'NEW_VALUE', 'NEW_VALUE_CLOB_TMP');
END;
/
