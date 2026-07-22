-- SIPM Developer Mode v1: global user preferences and private My Work ordering.
-- Rerunnable for managed Oracle deployments.

DECLARE
    v_count INTEGER := 0;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM user_tables
    WHERE table_name = 'TB_TA_PM_USER_PREFERENCES';

    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE "TB_TA_PM_USER_PREFERENCES" (
                user_id VARCHAR2(255 CHAR) NOT NULL,
                developer_mode_enabled SMALLINT DEFAULT 0 NOT NULL,
                theme VARCHAR2(16 CHAR) DEFAULT ''dark'' NOT NULL,
                created_at DATE DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,
                updated_at DATE DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,
                PRIMARY KEY (user_id),
                FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
            )';
    END IF;
END;
/

DECLARE
    v_count INTEGER := 0;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM user_tables
    WHERE table_name = 'TB_TA_PM_USER_TASK_STATES';

    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE "TB_TA_PM_USER_TASK_STATES" (
                user_task_state_id VARCHAR2(255 CHAR) NOT NULL,
                user_id VARCHAR2(255 CHAR) NOT NULL,
                space_id VARCHAR2(255 CHAR) NOT NULL,
                task_id VARCHAR2(255 CHAR) NOT NULL,
                sort_rank INTEGER DEFAULT 0 NOT NULL,
                created_at DATE DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,
                updated_at DATE DEFAULT SYS_EXTRACT_UTC(SYSTIMESTAMP) NOT NULL,
                PRIMARY KEY (user_task_state_id),
                CONSTRAINT uix_user_task_state_user_task UNIQUE (user_id, task_id),
                FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id),
                FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
                FOREIGN KEY(task_id) REFERENCES "TB_TA_PM_TASKS" (task_id)
            )';
    END IF;
END;
/

DECLARE
    PROCEDURE create_index_if_missing(p_index_name IN VARCHAR2, p_ddl IN VARCHAR2) IS
        v_count INTEGER := 0;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM user_indexes
        WHERE index_name = UPPER(p_index_name);
        IF v_count = 0 THEN
            EXECUTE IMMEDIATE p_ddl;
        END IF;
    END;
BEGIN
    create_index_if_missing(
        'IDX_USER_TASK_STATE_QUEUE',
        'CREATE INDEX idx_user_task_state_queue ON "TB_TA_PM_USER_TASK_STATES" (user_id, space_id, sort_rank)'
    );
    create_index_if_missing(
        'IX_TB_TA_PM_USER_TASK_STATES_SPACE_ID',
        'CREATE INDEX "ix_TB_TA_PM_USER_TASK_STATES_space_id" ON "TB_TA_PM_USER_TASK_STATES" (space_id)'
    );
    create_index_if_missing(
        'IX_TB_TA_PM_USER_TASK_STATES_TASK_ID',
        'CREATE INDEX "ix_TB_TA_PM_USER_TASK_STATES_task_id" ON "TB_TA_PM_USER_TASK_STATES" (task_id)'
    );
    create_index_if_missing(
        'IX_TB_TA_PM_USER_TASK_STATES_USER_ID',
        'CREATE INDEX "ix_TB_TA_PM_USER_TASK_STATES_user_id" ON "TB_TA_PM_USER_TASK_STATES" (user_id)'
    );
END;
/
