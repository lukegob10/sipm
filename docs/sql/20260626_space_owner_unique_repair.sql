-- SIPM repair migration: replace broad owner/kind uniqueness with personal-only uniqueness.
-- Safe to re-run.

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_constraints
	WHERE constraint_name = 'UIX_SPACE_OWNER_KIND';

	IF object_count > 0 THEN
		EXECUTE IMMEDIATE
			'ALTER TABLE "TB_TA_PM_SPACES" DROP CONSTRAINT uix_space_owner_kind';
	END IF;
END;
/

DECLARE
	object_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_indexes
	WHERE index_name = 'UIX_SPACE_OWNER_PERSONAL';

	IF object_count = 0 THEN
		EXECUTE IMMEDIATE q'[
			CREATE UNIQUE INDEX uix_space_owner_personal ON "TB_TA_PM_SPACES" (
				CASE WHEN space_kind = 'personal' THEN owner_user_id ELSE NULL END
			)
		]';
	END IF;
END;
/

COMMIT;
