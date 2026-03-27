-- Oracle migration: drop stale document and digest tables removed from this branch.
-- Destructive by design. Run only after confirming those legacy tables are not needed.
-- Safe to rerun: each table is dropped only if it exists.
--
-- Dropping the tables also removes their dependent indexes automatically.

DECLARE
    PROCEDURE drop_table_if_exists(p_table_name IN VARCHAR2) IS
        l_exists NUMBER := 0;
    BEGIN
        SELECT COUNT(*)
          INTO l_exists
          FROM user_tables
         WHERE table_name = p_table_name;

        IF l_exists > 0 THEN
            EXECUTE IMMEDIATE
                'DROP TABLE "' || p_table_name || '" CASCADE CONSTRAINTS PURGE';
        END IF;
    END drop_table_if_exists;
BEGIN
    drop_table_if_exists('TB_TA_PM_TASK_CARD_DIGESTS');
    drop_table_if_exists('TB_TA_PM_SOLUTION_CARD_DIGESTS');
    drop_table_if_exists('TB_TA_PM_PROJECT_CARD_DIGESTS');
    drop_table_if_exists('TB_TA_PM_EXTERNAL_DOCUMENTS');
    drop_table_if_exists('TB_TA_PM_PROJECT_DECISION_LOGS');
    drop_table_if_exists('TB_TA_PM_PROJECT_PLANS');
    drop_table_if_exists('TB_TA_PM_PROJECT_CHARTERS');
    drop_table_if_exists('TB_TA_PM_CHECKLIST_ITEMS');
    drop_table_if_exists('TB_TA_PM_SOW_DOCUMENTS');
END;
/
