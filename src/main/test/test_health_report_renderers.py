from __future__ import annotations

import re
from datetime import date

import pytest

from backend.app.services.pdf_utils import _SimplePdfDoc
from backend.app.services.pm_command_report_pdf import build_pm_command_report_pdf
from backend.app.services.program_dashboard_report_pdf import build_program_dashboard_report_pdf


def test_pdf_fonts_declare_the_encoding_used_for_extended_text():
    document = _SimplePdfDoc()
    for bold in (False, True):
        document.text(20, 500, "André – € (München) \\ notes", bold=bold)

    pdf = document.build()
    fonts = re.findall(rb"<< /Type /Font\b[^>]+>>", pdf)
    assert len(fonts) == 2
    assert all(b"/Encoding /WinAnsiEncoding" in font for font in fonts)
    assert pdf.count(b"(Andr\xe9 \x96 \x80 \\(M\xfcnchen\\) \\\\ notes) Tj") == 2


@pytest.mark.parametrize("report_kind", ["program", "pm_command"])
def test_report_metadata_preserves_windows_latin_text(report_kind):
    space_name = "André’s € delivery"
    if report_kind == "program":
        pdf = build_program_dashboard_report_pdf(
            space_name=space_name,
            selected_program_label="0 selected",
            programs=[], projects=[], solutions=[], phases=[],
            collapsed_program_ids=set(), collapsed_project_ids=set(),
        )
    else:
        pdf = build_pm_command_report_pdf(
            space_name=space_name,
            today=date(2026, 11, 6),
            projects=[], solutions=[], tasks=[], users=[], allocations=[],
        )

    assert space_name.encode("cp1252") in pdf


def test_pdf_stream_lengths_and_xref_offsets_cover_extended_text():
    document = _SimplePdfDoc()
    document.text(20, 500, "André – €")
    document.new_page()
    document.text(20, 500, "München", bold=True)
    pdf = document.build()

    streams = list(re.finditer(rb"/Length (\d+) >>\nstream\n(.*?)endstream", pdf, flags=re.DOTALL))
    assert len(streams) == 2
    for match in streams:
        assert int(match.group(1)) == len(match.group(2))

    xref_offset = int(re.search(rb"startxref\n(\d+)\n", pdf).group(1))
    assert pdf[xref_offset:].startswith(b"xref\n")
    entries = pdf[xref_offset:].splitlines()[3:11]
    assert len(entries) == 8
    for object_id, entry in enumerate(entries, start=1):
        object_offset = int(entry.split()[0])
        assert pdf[object_offset:].startswith(f"{object_id} 0 obj\n".encode("ascii"))
