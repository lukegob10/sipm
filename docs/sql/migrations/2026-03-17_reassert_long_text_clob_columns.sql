-- Oracle migration: re-assert audit long-text columns as CLOB after partial or stale deploys.
-- This is intentionally idempotent and safe to rerun.
--
-- Why this exists:
-- Some environments already widened the primary project/solution tables but left
-- TB_TA_PM_CHANGE_LOG.OLD_VALUE or NEW_VALUE as VARCHAR2. That still breaks
-- create/update requests when audit logging writes long descriptions.
--
-- Run as a script so every anonymous block executes.

DECLARE
    l_table_name CONSTANT VARCHAR2(128) := 'TB_TA_PM_CHANGE_LOG';
    l_column_name CONSTANT VARCHAR2(128) := 'OLD_VALUE';
    l_tmp_column_name CONSTANT VARCHAR2(128) := 'OLD_VALUE_CLOB_TMP';
    l_column_exists NUMBER := 0;
    l_tmp_exists NUMBER := 0;
    l_data_type VARCHAR2(30);
    l_tmp_data_type VARCHAR2(30);
BEGIN
    SELECT COUNT(*)
      INTO l_column_exists
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_column_name;

    SELECT COUNT(*)
      INTO l_tmp_exists
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_tmp_column_name;

    IF l_column_exists = 0 AND l_tmp_exists > 0 THEN
        SELECT data_type
          INTO l_tmp_data_type
          FROM user_tab_columns
         WHERE table_name = l_table_name
           AND column_name = l_tmp_column_name;

        IF l_tmp_data_type = 'CLOB' THEN
            EXECUTE IMMEDIATE
                'ALTER TABLE "' || l_table_name || '" RENAME COLUMN "' || l_tmp_column_name || '" TO "' || l_column_name || '"';
        END IF;
        RETURN;
    END IF;

    IF l_column_exists = 0 THEN
        RETURN;
    END IF;

    SELECT data_type
      INTO l_data_type
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_column_name;

    IF l_data_type = 'CLOB' THEN
        IF l_tmp_exists > 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_tmp_column_name || '"';
        END IF;
        RETURN;
    END IF;

    IF l_tmp_exists > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_tmp_column_name || '"';
    END IF;

    EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" ADD ("' || l_tmp_column_name || '" CLOB)';
    EXECUTE IMMEDIATE 'UPDATE "' || l_table_name || '" SET "' || l_tmp_column_name || '" = "' || l_column_name || '"';
    COMMIT;

    EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_column_name || '"';
    EXECUTE IMMEDIATE
        'ALTER TABLE "' || l_table_name || '" RENAME COLUMN "' || l_tmp_column_name || '" TO "' || l_column_name || '"';
END;
/

DECLARE
    l_table_name CONSTANT VARCHAR2(128) := 'TB_TA_PM_CHANGE_LOG';
    l_column_name CONSTANT VARCHAR2(128) := 'NEW_VALUE';
    l_tmp_column_name CONSTANT VARCHAR2(128) := 'NEW_VALUE_CLOB_TMP';
    l_column_exists NUMBER := 0;
    l_tmp_exists NUMBER := 0;
    l_data_type VARCHAR2(30);
    l_tmp_data_type VARCHAR2(30);
BEGIN
    SELECT COUNT(*)
      INTO l_column_exists
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_column_name;

    SELECT COUNT(*)
      INTO l_tmp_exists
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_tmp_column_name;

    IF l_column_exists = 0 AND l_tmp_exists > 0 THEN
        SELECT data_type
          INTO l_tmp_data_type
          FROM user_tab_columns
         WHERE table_name = l_table_name
           AND column_name = l_tmp_column_name;

        IF l_tmp_data_type = 'CLOB' THEN
            EXECUTE IMMEDIATE
                'ALTER TABLE "' || l_table_name || '" RENAME COLUMN "' || l_tmp_column_name || '" TO "' || l_column_name || '"';
        END IF;
        RETURN;
    END IF;

    IF l_column_exists = 0 THEN
        RETURN;
    END IF;

    SELECT data_type
      INTO l_data_type
      FROM user_tab_columns
     WHERE table_name = l_table_name
       AND column_name = l_column_name;

    IF l_data_type = 'CLOB' THEN
        IF l_tmp_exists > 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_tmp_column_name || '"';
        END IF;
        RETURN;
    END IF;

    IF l_tmp_exists > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_tmp_column_name || '"';
    END IF;

    EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" ADD ("' || l_tmp_column_name || '" CLOB)';
    EXECUTE IMMEDIATE 'UPDATE "' || l_table_name || '" SET "' || l_tmp_column_name || '" = "' || l_column_name || '"';
    COMMIT;

    EXECUTE IMMEDIATE 'ALTER TABLE "' || l_table_name || '" DROP COLUMN "' || l_column_name || '"';
    EXECUTE IMMEDIATE
        'ALTER TABLE "' || l_table_name || '" RENAME COLUMN "' || l_tmp_column_name || '" TO "' || l_column_name || '"';
END;
/
