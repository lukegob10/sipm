from backend.app.services.pdf_utils import _estimate_pdf_text_width, _wrap_pdf_text


def test_exact_line_limit_does_not_hide_text():
    assert _wrap_pdf_text("alpha beta", max_width=26, font_size=10, max_lines=2) == ["alpha", "beta"]


def test_long_word_after_short_word_stays_within_column():
    lines = _wrap_pdf_text("hi superlongword", max_width=26, font_size=10)
    assert "".join(lines).replace(" ", "") == "hisuperlongword"
    assert all(_estimate_pdf_text_width(line, 10) <= 26 for line in lines)


def test_ellipsis_indicates_actual_truncation():
    lines = _wrap_pdf_text("alpha beta gamma", max_width=26, font_size=10, max_lines=2)
    assert lines == ["alpha", "be..."]
