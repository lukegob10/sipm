from sqlalchemy import Text

from backend.app.models import ChangeLog, ChecklistItem, Project, SOWDocument, Solution


def test_sow_document_content_uses_text_type():
    assert isinstance(SOWDocument.__table__.c.content.type, Text)


def test_checklist_item_title_uses_text_type():
    assert isinstance(ChecklistItem.__table__.c.title.type, Text)


def test_project_long_text_fields_use_text_type():
    assert isinstance(Project.__table__.c.description.type, Text)
    assert isinstance(Project.__table__.c.success_criteria.type, Text)


def test_solution_long_text_fields_use_text_type():
    assert isinstance(Solution.__table__.c.description.type, Text)
    assert isinstance(Solution.__table__.c.success_criteria.type, Text)
    assert isinstance(Solution.__table__.c.problem_statement.type, Text)


def test_change_log_value_fields_use_text_type():
    assert isinstance(ChangeLog.__table__.c.old_value.type, Text)
    assert isinstance(ChangeLog.__table__.c.new_value.type, Text)
