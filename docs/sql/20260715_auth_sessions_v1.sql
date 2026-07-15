-- SIPM interactive auth sessions migration v1.
-- Adds server-enforced inactivity tracking. Safe to rerun.

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO object_count
	FROM user_tables
	WHERE table_name = 'TB_TA_PM_AUTH_SESSIONS';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE q'[
			CREATE TABLE "TB_TA_PM_AUTH_SESSIONS" (
				session_id VARCHAR2(255 CHAR) NOT NULL,
				user_id VARCHAR2(255 CHAR) NOT NULL,
				last_activity_at DATE NOT NULL,
				revoked_at DATE,
				created_at DATE NOT NULL,
				updated_at DATE NOT NULL,
				CONSTRAINT auth_session_pk PRIMARY KEY (session_id),
				CONSTRAINT auth_session_user_fk FOREIGN KEY (user_id)
					REFERENCES "TB_TA_PM_USERS" (user_id)
			)
		]';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO object_count FROM user_indexes WHERE index_name = 'IDX_AUTH_SESSION_USER';
	IF object_count = 0 THEN
		EXECUTE IMMEDIATE 'CREATE INDEX idx_auth_session_user ON "TB_TA_PM_AUTH_SESSIONS" (user_id)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO object_count FROM user_indexes WHERE index_name = 'IDX_AUTH_SESSION_ACTIVITY';
	IF object_count = 0 THEN
		EXECUTE IMMEDIATE 'CREATE INDEX idx_auth_session_activity ON "TB_TA_PM_AUTH_SESSIONS" (last_activity_at)';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*) INTO object_count FROM user_indexes WHERE index_name = 'IDX_AUTH_SESSION_REVOKED';
	IF object_count = 0 THEN
		EXECUTE IMMEDIATE 'CREATE INDEX idx_auth_session_revoked ON "TB_TA_PM_AUTH_SESSIONS" (revoked_at)';
	END IF;
END;
/

COMMIT;
