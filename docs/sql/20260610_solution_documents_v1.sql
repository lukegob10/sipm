-- SIPM solution documents migration v1
-- Adds DB-backed document attachments for solutions.
-- Safe to run once; table and index blocks check current Oracle schema state.

DECLARE
	v_count NUMBER;
BEGIN
	SELECT COUNT(*)
	INTO v_count
	FROM user_tables
	WHERE table_name = 'TB_TA_PM_SOLUTION_DOCUMENTS';

	IF v_count = 0 THEN
		EXECUTE IMMEDIATE '
			CREATE TABLE "TB_TA_PM_SOLUTION_DOCUMENTS" (
				document_id VARCHAR2(255 CHAR) NOT NULL,
				space_id VARCHAR2(255 CHAR),
				solution_id VARCHAR2(255 CHAR) NOT NULL,
				filename VARCHAR2(1024 CHAR) NOT NULL,
				content_type VARCHAR2(255 CHAR),
				size_bytes INTEGER NOT NULL,
				content BLOB NOT NULL,
				uploaded_by_user_id VARCHAR2(255 CHAR) NOT NULL,
				created_at DATE NOT NULL,
				updated_at DATE NOT NULL,
				deleted_at DATE,
				PRIMARY KEY (document_id),
				FOREIGN KEY(space_id) REFERENCES "TB_TA_PM_SPACES" (space_id),
				FOREIGN KEY(solution_id) REFERENCES "TB_TA_PM_SOLUTIONS" (solution_id)
			)';
	END IF;
END;
/

DECLARE
	PROCEDURE create_index_if_missing(p_index_name IN VARCHAR2, p_ddl IN VARCHAR2) IS
		v_count NUMBER;
	BEGIN
		SELECT COUNT(*)
		INTO v_count
		FROM user_indexes
		WHERE index_name = p_index_name;

		IF v_count = 0 THEN
			EXECUTE IMMEDIATE p_ddl;
		END IF;
	END;
BEGIN
	create_index_if_missing(
		'ix_TB_TA_PM_SOLUTION_DOCUMENTS_deleted_at',
		'CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_deleted_at" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (deleted_at)'
	);
	create_index_if_missing(
		'ix_TB_TA_PM_SOLUTION_DOCUMENTS_solution_id',
		'CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_solution_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (solution_id)'
	);
	create_index_if_missing(
		'ix_TB_TA_PM_SOLUTION_DOCUMENTS_space_id',
		'CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_space_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (space_id)'
	);
	create_index_if_missing(
		'ix_TB_TA_PM_SOLUTION_DOCUMENTS_uploaded_by_user_id',
		'CREATE INDEX "ix_TB_TA_PM_SOLUTION_DOCUMENTS_uploaded_by_user_id" ON "TB_TA_PM_SOLUTION_DOCUMENTS" (uploaded_by_user_id)'
	);
END;
/

COMMIT;
