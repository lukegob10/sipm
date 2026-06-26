-- SIPM repair migration: preserve existing Main work space and create separate Home lobby.
-- Use this if an earlier onboarding migration reclassified slug 'main' as the lobby.
-- Safe to re-run.

DECLARE
	main_count INTEGER;
	main_name_conflict_count INTEGER;
	home_slug_count INTEGER;
	home_name_conflict_count INTEGER;
	home_name VARCHAR2(255 CHAR);
BEGIN
	SELECT COUNT(*)
	INTO main_count
	FROM "TB_TA_PM_SPACES"
	WHERE slug = 'main'
	  AND deleted_at IS NULL;

	IF main_count > 0 THEN
		SELECT COUNT(*)
		INTO main_name_conflict_count
		FROM "TB_TA_PM_SPACES"
		WHERE name = 'Main'
		  AND slug <> 'main'
		  AND deleted_at IS NULL;

		IF main_name_conflict_count = 0 THEN
			UPDATE "TB_TA_PM_SPACES"
			SET name = CASE WHEN name = 'Home' THEN 'Main' ELSE name END,
				space_kind = 'collaboration',
				owner_user_id = NULL,
				is_active = 1,
				archived_at = NULL,
				updated_at = SYSDATE
			WHERE slug = 'main'
			  AND deleted_at IS NULL;
		ELSE
			UPDATE "TB_TA_PM_SPACES"
			SET space_kind = 'collaboration',
				owner_user_id = NULL,
				is_active = 1,
				archived_at = NULL,
				updated_at = SYSDATE
			WHERE slug = 'main'
			  AND deleted_at IS NULL;
		END IF;
	END IF;

	SELECT COUNT(*)
	INTO home_slug_count
	FROM "TB_TA_PM_SPACES"
	WHERE slug = 'home'
	  AND deleted_at IS NULL;

	SELECT COUNT(*)
	INTO home_name_conflict_count
	FROM "TB_TA_PM_SPACES"
	WHERE name = 'Home'
	  AND slug <> 'home'
	  AND deleted_at IS NULL;

	home_name := CASE WHEN home_name_conflict_count = 0 THEN 'Home' ELSE 'Home Lobby' END;

	IF home_slug_count = 0 THEN
		INSERT INTO "TB_TA_PM_SPACES" (
			space_id,
			name,
			slug,
			is_active,
			space_kind,
			owner_user_id,
			public_program_dashboard_enabled,
			archived_at,
			created_at,
			updated_at,
			deleted_at
		)
		VALUES (
			LOWER(RAWTOHEX(SYS_GUID())),
			home_name,
			'home',
			1,
			'lobby',
			NULL,
			0,
			NULL,
			SYSDATE,
			SYSDATE,
			NULL
		);
	ELSE
		UPDATE "TB_TA_PM_SPACES"
		SET name = home_name,
			space_kind = 'lobby',
			owner_user_id = NULL,
			is_active = 1,
			archived_at = NULL,
			updated_at = SYSDATE
		WHERE slug = 'home'
		  AND deleted_at IS NULL;
	END IF;
END;
/

INSERT INTO "TB_TA_PM_SPACE_MEMBERSHIPS" (
	membership_id,
	space_id,
	user_id,
	role,
	status,
	created_at,
	updated_at,
	deleted_at
)
SELECT
	LOWER(RAWTOHEX(SYS_GUID())),
	home_space.space_id,
	users.user_id,
	'member',
	'active',
	SYSDATE,
	SYSDATE,
	NULL
FROM "TB_TA_PM_USERS" users
CROSS JOIN (
	SELECT space_id
	FROM "TB_TA_PM_SPACES"
	WHERE slug = 'home'
	  AND deleted_at IS NULL
	FETCH FIRST 1 ROW ONLY
) home_space
WHERE users.is_active = 1
  AND users.is_service_account = 0
  AND NOT EXISTS (
	SELECT 1
	FROM "TB_TA_PM_SPACE_MEMBERSHIPS" memberships
	WHERE memberships.space_id = home_space.space_id
	  AND memberships.user_id = users.user_id
);

UPDATE "TB_TA_PM_SPACE_MEMBERSHIPS" memberships
SET status = 'active',
	deleted_at = NULL,
	updated_at = SYSDATE
WHERE memberships.space_id IN (
	SELECT space_id
	FROM "TB_TA_PM_SPACES"
	WHERE slug = 'home'
	  AND deleted_at IS NULL
  )
  AND memberships.user_id IN (
	SELECT user_id
	FROM "TB_TA_PM_USERS"
	WHERE is_active = 1
	  AND is_service_account = 0
  )
  AND (
	memberships.status <> 'active'
	OR memberships.deleted_at IS NOT NULL
  );

COMMIT;
