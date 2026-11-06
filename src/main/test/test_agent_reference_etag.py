from fastapi import Response

from backend.app.models import Phase
from backend.app.routes.agent import discovery


def test_reference_etag_tracks_content_and_is_stable(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        phase = Phase(phase_id="backlog", phase_group="Intake", phase_name="Initial", sequence=1)
        session.add(phase)
        session.commit()

        def reference():
            response = Response()
            data = discovery.get_reference_data(response, session, None)
            return response.headers["etag"], data.model_dump(mode="json")

        first_tag, first_data = reference()
        assert first_tag.startswith(f'W/"agent-reference-{discovery.REFERENCE_VERSION}-')
        assert reference() == (first_tag, first_data)

        phase.phase_name = "Updated"
        session.commit()
        changed_tag, changed_data = reference()
        assert changed_data["phases"] != first_data["phases"]
        assert changed_tag != first_tag
        assert reference() == (changed_tag, changed_data)

        changed_fields = {**discovery.CREATE_FIELDS, "project": set(discovery.CREATE_FIELDS["project"]) | {"new_field"}}
        monkeypatch.setattr(discovery, "CREATE_FIELDS", changed_fields)
        fields_tag, fields_data = reference()
        assert fields_data["fields"] != changed_data["fields"]
        assert fields_tag != changed_tag
