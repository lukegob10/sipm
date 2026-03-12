-- Oracle migration: replace global project/team name uniqueness with space-scoped uniqueness.
-- Safe to run once per database. Existing global uniqueness means the new constraints
-- should apply cleanly without data cleanup.

DECLARE
    PROCEDURE drop_constraint_if_exists(
        p_table_name IN VARCHAR2,
        p_constraint_name IN VARCHAR2
    ) IS
        l_exists NUMBER := 0;
    BEGIN
        SELECT COUNT(*)
          INTO l_exists
          FROM user_constraints
         WHERE table_name = p_table_name
           AND constraint_name = UPPER(p_constraint_name);

        IF l_exists > 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE "' || p_table_name || '" DROP CONSTRAINT "' || UPPER(p_constraint_name) || '"';
        END IF;
    END drop_constraint_if_exists;

    PROCEDURE add_unique_if_missing(
        p_table_name IN VARCHAR2,
        p_constraint_name IN VARCHAR2,
        p_columns_sql IN VARCHAR2
    ) IS
        l_exists NUMBER := 0;
    BEGIN
        SELECT COUNT(*)
          INTO l_exists
          FROM user_constraints
         WHERE table_name = p_table_name
           AND constraint_name = UPPER(p_constraint_name);

        IF l_exists = 0 THEN
            EXECUTE IMMEDIATE
                'ALTER TABLE "' || p_table_name || '" ADD CONSTRAINT "' || UPPER(p_constraint_name) || '" UNIQUE ' || p_columns_sql;
        END IF;
    END add_unique_if_missing;
BEGIN
    drop_constraint_if_exists('TB_TA_PM_PROJECTS', 'uix_project_name');
    add_unique_if_missing('TB_TA_PM_PROJECTS', 'uix_project_space_name', '("SPACE_ID", "PROJECT_NAME")');

    drop_constraint_if_exists('TB_TA_PM_TEAMS', 'uix_team_name');
    add_unique_if_missing('TB_TA_PM_TEAMS', 'uix_team_space_name', '("SPACE_ID", "NAME")');
END;
/
