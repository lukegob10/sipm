import re
from pathlib import Path


IMPORT_RE = re.compile(r'@import\s+"([^"]+)";')


def read_ui_styles(entrypoint: Path) -> str:
  text = entrypoint.read_text(encoding="utf-8")
  resolved = []
  for line in text.splitlines():
    match = IMPORT_RE.fullmatch(line.strip())
    if not match:
      resolved.append(line)
      continue
    target = (entrypoint.parent / match.group(1)).resolve()
    resolved.append(read_ui_styles(target))
  return "\n".join(resolved)
