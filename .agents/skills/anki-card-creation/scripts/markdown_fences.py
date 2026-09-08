"""Shared fence handling for Markdown structure and literal code examples."""

from __future__ import annotations

import re


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def scan_fenced_code(text: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Mask fenced code without shifting offsets; collect code and syntax errors."""
    masked: list[str] = []
    blocks: list[tuple[str, str]] = []
    errors: list[str] = []
    fence: str | None = None
    language = ""
    content: list[str] = []

    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        marker = FENCE_RE.match(line.rstrip("\r\n"))
        inside_fence = fence is not None
        if fence is None:
            # Backticks cannot occur in the info string of a backtick fence.
            if marker and not (marker[1][0] == "`" and "`" in marker[2]):
                fence, info = marker.groups()
                language = info.strip().split()[0] if info.strip() else ""
                content = []
                inside_fence = True
                if not language:
                    errors.append(f"line {line_number}: fenced code block has no language tag")
        elif (marker and marker[1][0] == fence[0]
              and len(marker[1]) >= len(fence) and not marker[2].strip()):
            blocks.append((language, "".join(content)))
            fence = None
        else:
            content.append(line)

        masked.append(re.sub(r"[^\r\n]", " ", line) if inside_fence else line)

    if fence is not None:
        errors.append("unclosed fenced code block")
        blocks.append((language, "".join(content)))
    return "".join(masked), blocks, errors


def mask_fenced_code(text: str) -> str:
    """Return only unfenced Markdown, retaining every original source offset."""
    return scan_fenced_code(text)[0]
