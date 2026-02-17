from sqlalchemy import Text

from backend.app.models import ChecklistItem, SOWDocument


def test_sow_document_content_uses_text_type():
    assert isinstance(SOWDocument.__table__.c.content.type, Text)


def test_checklist_item_title_uses_text_type():
    assert isinstance(ChecklistItem.__table__.c.title.type, Text)
