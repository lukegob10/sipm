import pytest


@pytest.mark.anyio
async def test_space_name_and_slug_respect_database_column_limits(client):
    created = await client.post("/project-manager/api/spaces", json={"name": "Valid Space", "slug": "valid-space"})
    assert created.status_code == 201
    space_id = created.json()["space_id"]

    too_long_name = await client.post("/project-manager/api/spaces", json={"name": "x" * 256})
    assert too_long_name.status_code == 400
    too_long_slug = await client.post(
        "/project-manager/api/spaces", json={"name": "Another Space", "slug": "x" * 256}
    )
    assert too_long_slug.status_code == 400
    rename = await client.patch(f"/project-manager/api/spaces/{space_id}", json={"name": "x" * 256})
    assert rename.status_code == 400

    boundary = await client.post(
        "/project-manager/api/spaces", json={"name": "x" * 255, "slug": "x" * 255}
    )
    assert boundary.status_code == 201, boundary.text


@pytest.mark.anyio
async def test_generated_personal_space_name_respects_column_limit(client, test_user, db_sessionmaker):
    from backend.app.models import Space

    test_user.soeid = "x" * 249
    response = await client.post("/project-manager/api/spaces/personal", json={})
    assert response.status_code == 400
    with db_sessionmaker() as session:
        assert session.query(Space).filter_by(space_kind="personal").count() == 0
