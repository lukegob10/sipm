from types import SimpleNamespace

import pytest

from backend.app.routes.solutions import documents


@pytest.mark.anyio
@pytest.mark.parametrize("content", [b"", b"\n" * 4096 + b"\x00\xff"], ids=["empty", "many-newlines"])
async def test_document_download_preserves_bytes_without_line_based_dispatch(monkeypatch, content):
    document = SimpleNamespace(
        filename="report.bin",
        content=content,
        content_type="application/octet-stream",
    )
    monkeypatch.setattr(documents, "_get_document_or_404", lambda *args, **kwargs: document)
    response = documents.download_solution_document(
        "solution", "document", session=None, space_ctx=None,
    )
    messages = []

    async def send(message):
        messages.append(message)

    async def receive():
        raise AssertionError("ASGI 2.4 response should not read from the request")

    await response(
        {"type": "http", "method": "GET", "asgi": {"spec_version": "2.4"}},
        receive,
        send,
    )

    start = messages[0]
    assert start["type"] == "http.response.start"
    assert start["status"] == 200
    headers = dict(start["headers"])
    assert headers[b"content-type"] == b"application/octet-stream"
    assert b'filename="report.bin"' in headers[b"content-disposition"]
    body_messages = [message for message in messages if message["type"] == "http.response.body"]
    assert b"".join(message.get("body", b"") for message in body_messages) == content
    assert not body_messages[-1].get("more_body", False)
    assert len(body_messages) <= 2
