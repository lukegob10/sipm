-- SIPM partial task rename repair
-- Repairs Oracle schemas where TB_TA_PM_SUBCOMPONENTS was renamed to
-- TB_TA_PM_TASKS but subcomponent_id/subcomponent_name columns, constraints,
-- or indexes were not renamed.
-- Safe to run after a successful migration; each block checks current state.

DECLARE
	v_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_count
	FROM user_tables
	WHERE table_name = 'TB_TA_PM_SUBCOMPONENTS';

	IF v_count > 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_SUBCOMPONENTS" RENAME TO "TB_TA_PM_TASKS"';
	END IF;
END;
/

DECLARE
	v_old_count NUMBER;
	v_new_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_old_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
	AND column_name = 'SUBCOMPONENT_ID';

	SELECT COUNT(*)
	INTO v_new_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
	AND column_name = 'TASK_ID';

	IF v_old_count > 0 AND v_new_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_TASKS" RENAME COLUMN subcomponent_id TO task_id';
	END IF;
END;
/

DECLARE
	v_old_count NUMBER;
	v_new_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_old_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
	AND column_name = 'SUBCOMPONENT_NAME';

	SELECT COUNT(*)
	INTO v_new_count
	FROM user_tab_columns
	WHERE table_name = 'TB_TA_PM_TASKS'
	AND column_name = 'TASK_NAME';

	IF v_old_count > 0 AND v_new_count = 0 THEN
		EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_TASKS" RENAME COLUMN subcomponent_name TO task_name';
	END IF;
END;
/

DECLARE
	v_old_name VARCHAR2(128);
	v_new_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_new_count
	FROM user_constraints
	WHERE table_name = 'TB_TA_PM_TASKS'
	AND UPPER(constraint_name) = 'UIX_TASK_SOLUTION_NAME';

	IF v_new_count = 0 THEN
		BEGIN
			SELECT constraint_name
			INTO v_old_name
			FROM user_constraints
			WHERE table_name = 'TB_TA_PM_TASKS'
			AND UPPER(constraint_name) = 'UIX_SUBCOMPONENT_SOLUTION_NAME'
			AND ROWNUM = 1;

			EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_TASKS" RENAME CONSTRAINT "' || v_old_name || '" TO uix_task_solution_name';
		EXCEPTION
			WHEN NO_DATA_FOUND THEN
				NULL;
		END;
	END IF;
END;
/

DECLARE
	PROCEDURE rename_index_if_needed(old_name IN VARCHAR2, new_name IN VARCHAR2) IS
		v_old_count NUMBER;
		v_new_count NUMBER;
	BEGIN
		SELECT COUNT(*)
		INTO v_old_count
		FROM user_indexes
		WHERE index_name = old_name;

		SELECT COUNT(*)
		INTO v_new_count
		FROM user_indexes
		WHERE index_name = new_name;

		IF v_old_count > 0 AND v_new_count = 0 THEN
			EXECUTE IMMEDIATE 'ALTER INDEX "' || old_name || '" RENAME TO "' || new_name || '"';
		END IF;
	END;
BEGIN
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_assignee_user_soeid', 'ix_TB_TA_PM_TASKS_assignee_user_soeid');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_blocked', 'ix_TB_TA_PM_TASKS_blocked');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_deleted_at', 'ix_TB_TA_PM_TASKS_deleted_at');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_due_date', 'ix_TB_TA_PM_TASKS_due_date');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_priority', 'ix_TB_TA_PM_TASKS_priority');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_project_id', 'ix_TB_TA_PM_TASKS_project_id');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_solution_id', 'ix_TB_TA_PM_TASKS_solution_id');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_space_id', 'ix_TB_TA_PM_TASKS_space_id');
	rename_index_if_needed('ix_TB_TA_PM_SUBCOMPONENTS_status', 'ix_TB_TA_PM_TASKS_status');
END;
/

UPDATE "TB_TA_PM_RESOURCE_ALLOCATIONS"
SET work_item_type = 'task'
WHERE work_item_type = 'subcomponent';

UPDATE "TB_TA_PM_CHANGE_LOG"
SET entity_type = 'task'
WHERE entity_type = 'subcomponent';

COMMIT;
