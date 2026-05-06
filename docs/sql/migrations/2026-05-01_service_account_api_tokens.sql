-- Oracle migration: add service-account personal access tokens.
-- Apply through the external deployment migration process. Application startup
-- remains non-mutating.

BEGIN
	EXECUTE IMMEDIATE 'ALTER TABLE "TB_TA_PM_USERS" ADD (
		is_service_account SMALLINT DEFAULT 0 NOT NULL
	)';
EXCEPTION
	WHEN OTHERS THEN
		IF SQLCODE != -1430 THEN
			RAISE;
		END IF;
END;
/

BEGIN
	EXECUTE IMMEDIATE 'CREATE TABLE "TB_TA_PM_API_TOKENS" (
		token_id VARCHAR2(255 CHAR) NOT NULL,
		user_id VARCHAR2(255 CHAR) NOT NULL,
		name VARCHAR2(255 CHAR) NOT NULL,
		token_hash VARCHAR2(64 CHAR) NOT NULL,
		created_by_user_id VARCHAR2(255 CHAR) NOT NULL,
		last_used_at DATE,
		expires_at DATE,
		revoked_at DATE,
		created_at DATE NOT NULL,
		updated_at DATE NOT NULL,
		PRIMARY KEY (token_id),
		CONSTRAINT uix_api_token_hash UNIQUE (token_hash),
		FOREIGN KEY(user_id) REFERENCES "TB_TA_PM_USERS" (user_id)
	)';
EXCEPTION
	WHEN OTHERS THEN
		IF SQLCODE != -955 THEN
			RAISE;
		END IF;
END;
/

BEGIN
	EXECUTE IMMEDIATE 'CREATE INDEX idx_api_token_user ON "TB_TA_PM_API_TOKENS" (user_id)';
EXCEPTION
	WHEN OTHERS THEN
		IF SQLCODE != -955 THEN
			RAISE;
		END IF;
END;
/

BEGIN
	EXECUTE IMMEDIATE 'CREATE INDEX "ix_TB_TA_PM_API_TOKENS_revoked_at" ON "TB_TA_PM_API_TOKENS" (revoked_at)';
EXCEPTION
	WHEN OTHERS THEN
		IF SQLCODE != -955 THEN
			RAISE;
		END IF;
END;
/
