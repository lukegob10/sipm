-- SIPM My Work personal state v1.
-- Adds private placement, reminders, and notes. Safe to rerun.

DECLARE
    column_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO column_count
    FROM user_tab_columns
    WHERE table_name = 'TB_TA_PM_USER_TASK_STATES'
        AND column_name = 'BUCKET';

    IF column_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_USER_TASK_STATES" ADD (bucket VARCHAR2(16 CHAR) DEFAULT ''later'' NOT NULL)';
    END IF;

    SELECT COUNT(*) INTO column_count
    FROM user_tab_columns
    WHERE table_name = 'TB_TA_PM_USER_TASK_STATES'
        AND column_name = 'REMINDER_AT';

    IF column_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_USER_TASK_STATES" ADD (reminder_at DATE)';
    END IF;

    SELECT COUNT(*) INTO column_count
    FROM user_tab_columns
    WHERE table_name = 'TB_TA_PM_USER_TASK_STATES'
        AND column_name = 'PRIVATE_NOTE';

    IF column_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_USER_TASK_STATES" ADD (private_note CLOB)';
    END IF;
END;
/

COMMIT;
