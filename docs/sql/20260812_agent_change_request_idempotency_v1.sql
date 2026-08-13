-- SIPM AgentChangeRequest idempotency enforcement.
-- Adds the database invariant used to recover concurrent submissions safely.
-- Safe to re-run: the named constraint is created only when it is missing.

DECLARE
	object_count INTEGER;
	duplicate_group_count INTEGER;
BEGIN
	SELECT COUNT(*)
	INTO object_count
	FROM user_constraints
	WHERE table_name = 'TB_TA_PM_AGENT_CHANGE_REQUESTS'
	  AND constraint_name = 'UIX_AGENT_CR_IDEMPOTENCY';

	IF object_count = 0 THEN
		SELECT COUNT(*)
		INTO duplicate_group_count
		FROM (
			SELECT 1
			FROM "TB_TA_PM_AGENT_CHANGE_REQUESTS"
			GROUP BY space_id, proposed_by_user_id, idempotency_key
			HAVING COUNT(*) > 1
		);

		IF duplicate_group_count > 0 THEN
			RAISE_APPLICATION_ERROR(
				-20001,
				'Cannot add uix_agent_cr_idempotency: reconcile duplicate space, proposer, and idempotency-key rows first.'
			);
		END IF;

		EXECUTE IMMEDIATE
			'ALTER TABLE "TB_TA_PM_AGENT_CHANGE_REQUESTS" ADD CONSTRAINT uix_agent_cr_idempotency UNIQUE (space_id, proposed_by_user_id, idempotency_key)';
	END IF;
END;
/

COMMIT;
