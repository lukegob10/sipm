-- Oracle migration: widen TB_TA_PM_CHECKLIST_ITEMS.TITLE from VARCHAR2(255) to CLOB.
-- Safe to run once per database. If TITLE is already CLOB, it exits with no changes.

DECLARE
    l_title_type VARCHAR2(30);
    l_tmp_exists NUMBER := 0;
BEGIN
    SELECT data_type
      INTO l_title_type
      FROM user_tab_columns
     WHERE table_name = 'TB_TA_PM_CHECKLIST_ITEMS'
       AND column_name = 'TITLE';

    IF l_title_type = 'CLOB' THEN
        RETURN;
    END IF;

    -- Defensive cleanup in case of an interrupted prior run.
    SELECT COUNT(*)
      INTO l_tmp_exists
      FROM user_tab_columns
     WHERE table_name = 'TB_TA_PM_CHECKLIST_ITEMS'
       AND column_name = 'TITLE_CLOB_TMP';

    IF l_tmp_exists > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_CHECKLIST_ITEMS" DROP COLUMN "TITLE_CLOB_TMP"';
    END IF;

    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_CHECKLIST_ITEMS" ADD ("TITLE_CLOB_TMP" CLOB)';
    EXECUTE IMMEDIATE 'UPDATE "TB_TA_PM_CHECKLIST_ITEMS" SET "TITLE_CLOB_TMP" = "TITLE"';
    COMMIT;

    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_CHECKLIST_ITEMS" DROP COLUMN "TITLE"';
    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_CHECKLIST_ITEMS" RENAME COLUMN "TITLE_CLOB_TMP" TO "TITLE"';
    EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_CHECKLIST_ITEMS" MODIFY ("TITLE" NOT NULL)';
END;
/
