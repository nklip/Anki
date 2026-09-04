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
VERSION_EVENT_RE = re.compile(
    r"\b(?:added|introduced|previewed|released|finalized|became|available)\b",
    re.IGNORECASE,
)
ALLOWED_IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SIMPLE_CHARACTER_LIMIT = 3000
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


def countable_text(text: str) -> str:
    """Return the teaching content that counts toward the simple-mode budget.

    The Front is a prompt rather than teaching content, and Sources are a
    verification requirement whose length must not push a card over budget.
    Both sections are excluded so the limit constrains only the Back.
    """
    spans: list[tuple[int, int]] = []
    for match in SECOND_LEVEL_HEADING_RE.finditer(text):
        if match.group(1).strip() not in {"Front", "Sources"}:
            continue
        following = SECOND_LEVEL_HEADING_RE.search(text, match.end())
        spans.append((match.start(), following.start() if following else len(text)))

    kept = []
    cursor = 0
    for start, end in sorted(spans):
        if start > cursor:
            kept.append(text[cursor:start])
        cursor = max(cursor, end)
    kept.append(text[cursor:])
    return "".join(kept)


def validate_text(
    text: str,
    card_path: Path,
    mode: str,
    *,
    check_image_files: bool = True,
    require_version_lead: bool = False,
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

    if require_version_lead:
        back_match = re.search(r"^## Back\s*$", text, re.MULTILINE)
        first_back_line = ""
        if back_match:
            for line in text[back_match.end():].splitlines():
                if line.startswith("## "):
                    break
                if line.strip():
                    first_back_line = line.strip()
                    break
        if not re.fullmatch(r"\*\*\S(?:.*\S)?\*\*", first_back_line):
            errors.append(
                "a versioned feature card must start the Back with one standalone bold sentence"
            )
        else:
            lead_text = first_back_line[2:-2]
            if not VERSION_EVENT_RE.search(lead_text):
                errors.append(
                    "the version lead must state a lifecycle event such as introduced, "
                    "previewed, or became final"
                )
            if not re.search(r"\d", lead_text):
                errors.append("the version lead must state the release or version")

    character_count = len(countable_text(text))
    if mode == "simple" and character_count > SIMPLE_CHARACTER_LIMIT:
        errors.append(
            f"simple mode allows at most {SIMPLE_CHARACTER_LIMIT} characters "
            f"outside Front and Sources; found {character_count}"
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

    # The budget applies to the Back only; padding goes there, not into Sources.
    padded = simple.replace("## Sources", "PAD\n\n## Sources")
    body = len(countable_text(padded))
    at_simple_limit = padded.replace("PAD", "P" * (SIMPLE_CHARACTER_LIMIT - body + 3))
    assert len(countable_text(at_simple_limit)) == SIMPLE_CHARACTER_LIMIT
    assert not validate_text(
        at_simple_limit, Path("card.md"), "simple", check_image_files=False
    )
    above_simple_limit = at_simple_limit.replace("\n\n## Sources", "x\n\n## Sources")
    assert any("allows at most 3000" in error for error in validate_text(
        above_simple_limit, Path("card.md"), "simple", check_image_files=False
    ))

    versioned_feature = simple.replace(
        "An atomic update is observed as one indivisible action.",
        "**Atomic updates were introduced in Example Platform 1.0.**\n\n"
        "An atomic update is observed as one indivisible action.",
    )
    assert not validate_text(
        versioned_feature,
        Path("card.md"),
        "simple",
        check_image_files=False,
        require_version_lead=True,
    )
    assert any("standalone bold sentence" in error for error in validate_text(
        simple,
        Path("card.md"),
        "simple",
        check_image_files=False,
        require_version_lead=True,
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

    # A huge Front or Sources section must not push a card over budget.
    fat_front = simple.replace(
        "What is an atomic update?", "What is an atomic update? " + "q" * 5000
    )
    assert not validate_text(fat_front, Path("card.md"), "simple", check_image_files=False)
    fat_sources = simple.replace(
        "- [Java API](https://example.com/api)",
        "- [Java API](https://example.com/api)\n\n  " + "s" * 5000,
    )
    assert not validate_text(fat_sources, Path("card.md"), "simple", check_image_files=False)
    assert "Front" not in countable_text(simple)
    assert "Sources" not in countable_text(simple)
    assert "Atomic update" in countable_text(simple)

    bare_fence = simple.replace("```java", "```", 1)
    assert any("no language tag" in error for error in validate_text(
        bare_fence, Path("card.md"), "simple", check_image_files=False
    ))
    print("Self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", nargs="?", type=Path, help="Markdown card to validate")
    parser.add_argument("--mode", choices=("simple", "complex"), default="simple")
    parser.add_argument(
        "--require-version-lead",
        action="store_true",
        help="require a bold first Back line naming a feature lifecycle event and version",
    )
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
    errors = validate_text(
        text,
        args.card,
        args.mode,
        require_version_lead=args.require_version_lead,
    )
    if errors:
        print(f"{args.card}: validation failed", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    images = len(IMAGE_RE.findall(text))
    counted = len(countable_text(text))
    budget = f"{counted} counted" if args.mode == "simple" else f"{len(text)}"
    print(f"{args.card}: OK ({args.mode}, {budget} characters, {images} visual(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
