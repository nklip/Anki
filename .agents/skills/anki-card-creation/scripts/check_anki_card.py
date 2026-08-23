#!/usr/bin/env python3
"""Validate structural invariants for Anki Markdown cards."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SOURCE_RE = re.compile(r"^- \[[^\]]+\]\(https?://[^)]+\)\s*$", re.MULTILINE)
SECOND_LEVEL_HEADING_RE = re.compile(r"^## ([^#].*)$", re.MULTILINE)
STEP_HEADING_RE = re.compile(r"^(#{3,6}) Step \d+\b[^\n]*$", re.MULTILINE)
ALLOWED_IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SIMPLE_CHARACTER_LIMIT = 2500
JAVA_HINTS = (
    "public class ",
    "static void main",
    "System.out.",
    "synchronized (",
    "volatile ",
    "record ",
    "interface ",
    "enum ",
)


def fenced_blocks(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Return fenced blocks and syntax errors without parsing Markdown extensions."""
    blocks: list[tuple[str, str]] = []
    errors: list[str] = []
    language: str | None = None
    content: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("```"):
            if language is not None:
                content.append(line)
            continue

        fence_label = line[3:].strip()
        if language is None:
            if not fence_label:
                errors.append(f"line {line_number}: fenced code block has no language tag")
            language = fence_label
            content = []
        else:
            if fence_label:
                errors.append(f"line {line_number}: closing code fence must not have a language tag")
            blocks.append((language, "\n".join(content)))
            language = None
            content = []

    if language is not None:
        errors.append("unclosed fenced code block")
    return blocks, errors


def validate_text(
    text: str,
    card_path: Path,
    mode: str,
    *,
    check_image_files: bool = True,
) -> list[str]:
    errors: list[str] = []

    if not re.match(r"^# [^\n]+\n", text):
        errors.append("the first line must be one level-one title")

    required = ["## Front", "## Back", "## Sources"]
    positions = [text.find(heading) for heading in required]
    for heading, position in zip(required, positions):
        if position < 0:
            errors.append(f"missing required heading: {heading}")
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append("required headings must appear in the order Front, Back, Sources")

    second_level_headings = SECOND_LEVEL_HEADING_RE.findall(text)
    if second_level_headings and second_level_headings[-1].strip() != "Sources":
        errors.append("## Sources must be the final second-level section")
    if not SOURCE_RE.search(text):
        errors.append("## Sources must contain at least one Markdown link to an HTTP(S) source")

    character_count = len(text)
    if mode == "simple" and character_count > SIMPLE_CHARACTER_LIMIT:
        errors.append(
            f"simple mode allows at most {SIMPLE_CHARACTER_LIMIT} characters; "
            f"found {character_count}"
        )

    images = IMAGE_RE.findall(text)
    minimum_images = 1 if mode == "simple" else 2
    if len(images) < minimum_images:
        errors.append(
            f"{mode} mode requires at least {minimum_images} local visual(s); found {len(images)}"
        )

    for alt_text, target in images:
        if not alt_text.strip():
            errors.append(f"visual {target!r} needs meaningful alt text")
        if target.startswith(("http://", "https://", "data:")):
            errors.append(f"visual {target!r} must be a local repository file")
            continue
        image_path = (card_path.parent / target).resolve()
        if image_path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            errors.append(f"visual {target!r} has an unsupported file type")
        if check_image_files and not image_path.is_file():
            errors.append(f"visual file does not exist: {target}")

    if mode == "complex":
        step_matches = list(STEP_HEADING_RE.finditer(text))
        for index, step_match in enumerate(step_matches):
            section_start = step_match.end()
            section_end = step_matches[index + 1].start() if index + 1 < len(step_matches) else len(text)
            step_section = text[section_start:section_end]
            step_images = IMAGE_RE.findall(step_section)
            if not any(Path(target).suffix.lower() == ".svg" for _, target in step_images):
                heading = step_match.group(0).lstrip("# ")
                errors.append(f"{heading!r} requires its own local .svg diagram")

    blocks, fence_errors = fenced_blocks(text)
    errors.extend(fence_errors)
    for language, code in blocks:
        if language.lower() == "java" and language != "java":
            errors.append("Java fenced code blocks must use the lowercase language tag 'java'")
        if any(hint in code for hint in JAVA_HINTS) and language != "java":
            errors.append(
                f"a code block tagged {language!r} looks like Java; use the 'java' language tag"
            )

    return errors


def run_self_test() -> None:
    simple = """# Atomic update

## Front

What is an atomic update?

## Back

An atomic update is observed as one indivisible action.

![Atomic update](svg/atomic-update.svg)

```java
counter.incrementAndGet();
```

## Sources

- [Java API](https://example.com/api)
"""
    complex_card = simple.replace(
        "![Atomic update](svg/atomic-update.svg)",
        "![Before](svg/before.svg)\n\n![After](svg/after.svg)",
    )
    assert not validate_text(simple, Path("card.md"), "simple", check_image_files=False)
    assert not validate_text(complex_card, Path("card.md"), "complex", check_image_files=False)

    at_simple_limit = simple + " " * (SIMPLE_CHARACTER_LIMIT - len(simple))
    assert len(at_simple_limit) == SIMPLE_CHARACTER_LIMIT
    assert not validate_text(
        at_simple_limit, Path("card.md"), "simple", check_image_files=False
    )
    above_simple_limit = at_simple_limit + "x"
    assert any("allows at most 2500" in error for error in validate_text(
        above_simple_limit, Path("card.md"), "simple", check_image_files=False
    ))

    process_card = complex_card.replace(
        "## Sources",
        "### Step 1 — Read\n\n![Read](svg/read.svg)\n\n"
        "### Step 2 — Write\n\n![Write](svg/write.svg)\n\n## Sources",
    )
    assert not validate_text(process_card, Path("card.md"), "complex", check_image_files=False)

    missing_step_svg = process_card.replace("![Write](svg/write.svg)", "Step explanation")
    assert any("requires its own local .svg" in error for error in validate_text(
        missing_step_svg, Path("card.md"), "complex", check_image_files=False
    ))

    no_image = simple.replace("![Atomic update](svg/atomic-update.svg)\n\n", "")
    assert any("requires at least" in error for error in validate_text(
        no_image, Path("card.md"), "simple", check_image_files=False
    ))

    bare_fence = simple.replace("```java", "```", 1)
    assert any("no language tag" in error for error in validate_text(
        bare_fence, Path("card.md"), "simple", check_image_files=False
    ))
    print("Self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", nargs="?", type=Path, help="Markdown card to validate")
    parser.add_argument("--mode", choices=("simple", "complex"), default="simple")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if args.card is None:
        parser.error("card path is required unless --self-test is used")
    if args.card.suffix.lower() != ".md":
        print(f"ERROR: expected an .md file: {args.card}", file=sys.stderr)
        return 2
    if not args.card.is_file():
        print(f"ERROR: card does not exist: {args.card}", file=sys.stderr)
        return 2

    text = args.card.read_text(encoding="utf-8")
    errors = validate_text(text, args.card, args.mode)
    if errors:
        print(f"{args.card}: validation failed", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    images = len(IMAGE_RE.findall(text))
    print(f"{args.card}: OK ({args.mode}, {len(text)} characters, {images} visual(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
