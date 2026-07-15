from __future__ import annotations

from typing import Optional


def _pdf_escape(value: str) -> str:
    safe = str(value or "").encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_number(value: float) -> str:
    text = f"{float(value):.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _pdf_rgb(color: tuple[int, int, int]) -> str:
    red, green, blue = color
    return f"{red / 255.0:.3f} {green / 255.0:.3f} {blue / 255.0:.3f}"


class _SimplePdfDoc:
    def __init__(self, width: float = 842.0, height: float = 595.0) -> None:
        self.width = float(width)
        self.height = float(height)
        self._pages: list[list[str]] = []
        self._active_page: Optional[list[str]] = None

    def new_page(self) -> None:
        page: list[str] = []
        self._pages.append(page)
        self._active_page = page

    def _cmd(self, value: str) -> None:
        if self._active_page is None:
            self.new_page()
        assert self._active_page is not None
        self._active_page.append(value)

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[tuple[int, int, int]] = None,
        stroke: Optional[tuple[int, int, int]] = None,
        line_width: float = 1.0,
    ) -> None:
        commands: list[str] = []
        if fill:
            commands.append(f"{_pdf_rgb(fill)} rg")
        if stroke:
            commands.append(f"{_pdf_rgb(stroke)} RG {_pdf_number(line_width)} w")
        commands.append(f"{_pdf_number(x)} {_pdf_number(y)} {_pdf_number(width)} {_pdf_number(height)} re")
        if fill and stroke:
            commands.append("B")
        elif fill:
            commands.append("f")
        else:
            commands.append("S")
        self._cmd(" ".join(commands))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: tuple[int, int, int] = (180, 186, 199),
        line_width: float = 1.0,
    ) -> None:
        self._cmd(
            f"{_pdf_rgb(stroke)} RG {_pdf_number(line_width)} w "
            f"{_pdf_number(x1)} {_pdf_number(y1)} m {_pdf_number(x2)} {_pdf_number(y2)} l S"
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 10.0,
        bold: bool = False,
        color: tuple[int, int, int] = (17, 24, 39),
    ) -> None:
        font_ref = "/F2" if bold else "/F1"
        text = _pdf_escape(value)
        self._cmd(
            f"BT {_pdf_rgb(color)} rg {font_ref} {_pdf_number(size)} Tf "
            f"1 0 0 1 {_pdf_number(x)} {_pdf_number(y)} Tm ({text}) Tj ET"
        )

    def build(self) -> bytes:
        if not self._pages:
            self.new_page()
        page_count = len(self._pages)
        font_regular_id = 3
        font_bold_id = 4
        object_map: dict[int, str] = {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            font_regular_id: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            font_bold_id: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        }

        next_id = 5
        page_ids: list[int] = []
        content_ids: list[int] = []
        for _ in self._pages:
            page_ids.append(next_id)
            content_ids.append(next_id + 1)
            next_id += 2

        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        object_map[2] = f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>"

        for idx, commands in enumerate(self._pages):
            content_text = "\n".join(commands) + "\n"
            content_length = len(content_text.encode("latin-1", errors="replace"))
            content_id = content_ids[idx]
            page_id = page_ids[idx]
            object_map[content_id] = f"<< /Length {content_length} >>\nstream\n{content_text}endstream"
            object_map[page_id] = (
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {_pdf_number(self.width)} {_pdf_number(self.height)}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )

        max_id = max(object_map.keys())
        out = bytearray()
        out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: list[int] = [0] * (max_id + 1)
        for object_id in range(1, max_id + 1):
            body = object_map.get(object_id, "<<>>")
            offsets[object_id] = len(out)
            out.extend(f"{object_id} 0 obj\n".encode("latin-1"))
            out.extend(body.encode("latin-1", errors="replace"))
            out.extend(b"\nendobj\n")

        xref_offset = len(out)
        out.extend(f"xref\n0 {max_id + 1}\n".encode("latin-1"))
        out.extend(b"0000000000 65535 f \n")
        for object_id in range(1, max_id + 1):
            out.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("latin-1"))
        out.extend(
            (
                f"trailer\n<< /Size {max_id + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_offset}\n%%EOF\n"
            ).encode("latin-1")
        )
        return bytes(out)


class _TopPdfPainter:
    def __init__(self, document: _SimplePdfDoc) -> None:
        self.document = document

    def _to_bottom_y(self, top_y: float, height: float = 0.0) -> float:
        return self.document.height - top_y - height

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Optional[tuple[int, int, int]] = None,
        stroke: Optional[tuple[int, int, int]] = None,
        line_width: float = 1.0,
    ) -> None:
        self.document.rect(
            x=x,
            y=self._to_bottom_y(y, height),
            width=width,
            height=height,
            fill=fill,
            stroke=stroke,
            line_width=line_width,
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: tuple[int, int, int] = (180, 186, 199),
        line_width: float = 1.0,
    ) -> None:
        self.document.line(
            x1=x1,
            y1=self._to_bottom_y(y1),
            x2=x2,
            y2=self._to_bottom_y(y2),
            stroke=stroke,
            line_width=line_width,
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 10.0,
        bold: bool = False,
        color: tuple[int, int, int] = (17, 24, 39),
    ) -> None:
        self.document.text(
            x=x,
            y=self._to_bottom_y(y, size),
            value=value,
            size=size,
            bold=bold,
            color=color,
        )


def _estimate_pdf_text_width(text: str, font_size: float) -> float:
    return max(len(str(text or "")), 1) * font_size * 0.52


def _wrap_pdf_text(
    text: str,
    max_width: float,
    font_size: float,
    max_lines: Optional[int] = None,
) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return [""]
    words = normalized.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if _estimate_pdf_text_width(candidate, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = word
        else:
            chunk = word
            while _estimate_pdf_text_width(chunk, font_size) > max_width and len(chunk) > 4:
                slice_size = max(int(max_width / (font_size * 0.52)), 1)
                lines.append(chunk[:slice_size])
                chunk = chunk[slice_size:]
            current = chunk
        if max_lines and len(lines) >= max_lines:
            break
    if current and (not max_lines or len(lines) < max_lines):
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    if max_lines and len(lines) == max_lines and words:
        last = lines[-1]
        if not last.endswith("...") and len(last) > 3:
            lines[-1] = f"{last[:-3]}..."
    return lines


def _draw_report_card(
    painter: _TopPdfPainter,
    x: float,
    y: float,
    width: float,
    height: float,
    accent: tuple[int, int, int],
    title: str,
    value: str,
    subtitle: str,
) -> None:
    painter.rect(x, y, width, height, fill=(248, 250, 255), stroke=(218, 225, 236))
    painter.rect(x, y, 6, height, fill=accent)
    painter.text(x + 14, y + 10, title, size=9, color=(96, 107, 129))
    painter.text(x + 14, y + 30, value, size=18, bold=True, color=(20, 35, 72))
    painter.text(x + 14, y + 56, subtitle, size=9, color=(96, 107, 129))
