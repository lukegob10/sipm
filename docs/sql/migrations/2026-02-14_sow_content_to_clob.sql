-- Oracle migration: widen TB_TA_PM_SOW_DOCUMENTS.CONTENT from VARCHAR2(255) to CLOB.
-- Safe to run once per database. If CONTENT is already CLOB, it exits with no changes.

DECLARE
    l_content_type VARCHAR2(30);
    l_tmp_exists NUMBER := 0;
BEGIN
    SELECT data_type
      INTO l_content_type
      FROM user_tab_columns
     WHERE table_name = 'TB_TA_PM_SOW_DOCUMENTS'
       AND column_name = 'CONTENT';

    IF l_content_type = 'CLOB' THEN
        RETURN;
    END IF;

    -- Defensive cleanup in case of an interrupted prior run.
    SELECT COUNT(*)
      INTO l_tmp_exists
      FROM user_tab_columns
     WHERE table_name = 'TB_TA_PM_SOW_DOCUMENTS'
       AND column_name = 'CONTENT_CLOB_TMP';

    IF l_tmp_exists > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOW_DOCUMENTS" DROP COLUMN "CONTENT_CLOB_TMP"';
    END IF;

    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOW_DOCUMENTS" ADD ("CONTENT_CLOB_TMP" CLOB)';
    EXECUTE IMMEDIATE 'UPDATE "TB_TA_PM_SOW_DOCUMENTS" SET "CONTENT_CLOB_TMP" = "CONTENT"';
    COMMIT;

    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOW_DOCUMENTS" DROP COLUMN "CONTENT"';
    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOW_DOCUMENTS" RENAME COLUMN "CONTENT_CLOB_TMP" TO "CONTENT"';
    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SOW_DOCUMENTS" MODIFY ("CONTENT" NOT NULL)';
END;
/
