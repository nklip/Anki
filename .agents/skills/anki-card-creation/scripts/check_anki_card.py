#!/usr/bin/env python3
"""Validate structural invariants for Anki Markdown cards."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from markdown_anchors import markdown_anchors
from markdown_fences import mask_fenced_code, scan_fenced_code


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SOURCE_RE = re.compile(r"^- \[[^\]]+\]\(https?://[^)]+\)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+([^\n]+?)[ \t]*$", re.MULTILINE)
CARD_MODE_RE = re.compile(
    r"^<!-- Card mode: (simple|complex)\. Validate with --mode (simple|complex)\. -->"
    r"[ \t]*(?:\r?\n|$)",
    re.MULTILINE,
)
NAVIGATION_RE = re.compile(
    r"^<sub>\[Back to ([^\]\n]+)\]\(([^)\s]+)\)</sub>[ \t]*(?:\r?\n|$)",
    re.MULTILINE,
)
STEP_HEADING_RE = re.compile(r"^ {0,3}(#{2,6})[ \t]+Step \d+\b[^\n]*$", re.MULTILINE)
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
    _, blocks, errors = scan_fenced_code(text)
    return blocks, errors


def card_headings(text: str) -> list[re.Match[str]]:
    """Find Markdown headings, ignoring literal examples inside fenced code."""
    return list(HEADING_RE.finditer(mask_fenced_code(text)))


def countable_text(text: str) -> str:
    """Return the teaching content that counts toward the simple-mode budget.

    The Front is a prompt rather than teaching content, and Sources are a
    verification requirement whose length must not push a card over budget.
    Both sections, the navigation link, and the card-mode comment are excluded.
    """
    structural_text = mask_fenced_code(text)
    spans = [match.span() for pattern in (CARD_MODE_RE, NAVIGATION_RE)
             for match in pattern.finditer(structural_text)]
    headings = list(HEADING_RE.finditer(structural_text))
    for index, match in enumerate(headings):
        if match.groups() not in {("#", "Front"), ("#", "Sources")}:
            continue
        following = next(
            (heading for heading in headings[index + 1:]
             if len(heading.group(1)) <= len(match.group(1))),
            None,
        )
        spans.append((match.start(), following.start() if following else len(text)))

    kept = []
    cursor = 0
    for start, end in sorted(spans):
        if start > cursor:
            kept.append(text[cursor:start])
        cursor = max(cursor, end)
    kept.append(text[cursor:])
    return "".join(kept)


def navigation_case_error(directory: Path, relative_path: Path) -> str | None:
    """Check directory entries, even on a case-insensitive filesystem."""
    current = directory
    for part in relative_path.parts:
        if part == "..":
            current = current.parent
            continue
        try:
            names = {entry.name for entry in current.iterdir()}
        except OSError:
            return None  # The ordinary existence check reports an unreadable path.
        if part not in names:
            alternatives = sorted(name for name in names if name.casefold() == part.casefold())
            if alternatives:
                return (
                    f"navigation README path case mismatch: {relative_path.as_posix()}; "
                    f"use {alternatives[0]!r} instead of {part!r}"
                )
            return None
        current /= part
    return None


def validate_text(
    text: str,
    card_path: Path,
    mode: str,
    *,
    check_local_files: bool = True,
    require_version_lead: bool = False,
) -> list[str]:
    errors: list[str] = []
    structural_text, blocks, fence_errors = scan_fenced_code(text)

    title = re.match(r"^# [^\n]+\n", text)
    if not title:
        errors.append("the first line must be one level-one title")

    headings = list(HEADING_RE.finditer(structural_text))
    required = ["# Front", "# Back", "# Sources"]
    required_matches = [
        next((match for match in headings if " ".join(match.groups()) == heading), None)
        for heading in required
    ]
    positions = [match.start() if match else -1 for match in required_matches]
    for heading, position in zip(required, positions):
        if position < 0:
            errors.append(f"missing required heading: {heading}")
    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append("required headings must appear in the order Front, Back, Sources")

    navigation_links = list(NAVIGATION_RE.finditer(structural_text))
    navigation = navigation_links[0] if len(navigation_links) == 1 else None
    if navigation is None:
        errors.append(
            "include exactly one standalone navigation link without a list marker: "
            "<sub>[Back to Subject](../Readme.md#content)</sub>"
        )
    else:
        target = navigation.group(2)
        url = urlsplit(target)
        relative_path = Path(unquote(url.path))
        card_directory = card_path.parent.resolve()
        target_path = (card_directory / relative_path).resolve()
        if (
            url.scheme or url.netloc or url.query or relative_path.is_absolute()
            or relative_path.name.lower() != "readme.md"
            or target_path == card_path.resolve()
            or target_path.parent not in (card_directory, *card_directory.parents)
        ):
            errors.append("navigation link must use a relative path to a containing index README")
        elif check_local_files:
            case_error = navigation_case_error(card_directory, relative_path)
            if case_error:
                errors.append(case_error)
            elif not target_path.is_file():
                errors.append(f"navigation README does not exist: {unquote(url.path)}")
            elif url.fragment:
                try:
                    anchors = markdown_anchors(target_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError) as error:
                    errors.append(f"cannot read navigation README {unquote(url.path)}: {error}")
                else:
                    if unquote(url.fragment) not in anchors:
                        errors.append(f"navigation README anchor does not exist: {target}")

    expected_comment = f"<!-- Card mode: {mode}. Validate with --mode {mode}. -->"
    mode_comments = list(CARD_MODE_RE.finditer(structural_text))
    mode_comment = mode_comments[0] if len(mode_comments) == 1 else None
    if len(mode_comments) != 1:
        errors.append(f"include exactly one card mode comment: {expected_comment}")
    else:
        if mode_comment.groups() != (mode, mode):
            errors.append(f"card mode comment must match validation --mode {mode}: {expected_comment}")

    front = required_matches[0]
    header_parts = (title, navigation, mode_comment, front)
    if front is None or (all(header_parts) and any(
        following.start() < previous.end()
        or not re.fullmatch(r"(?:[ \t]*\r?\n)+", text[previous.end():following.start()])
        for previous, following in zip(header_parts, header_parts[1:])
    )):
        errors.append(
            "header order must be title, navigation link, card mode comment, # Front, "
            "with a blank line between each and no intervening content"
        )

    for heading in headings:
        if len(heading.group(1)) >= 4:
            errors.append(
                f"heading {heading.group(2)!r} is too deep: "
                "use ## for teaching sections and ### for subsections"
            )

    first_level_headings = [match.group(2) for match in headings if match.group(1) == "#"]
    if first_level_headings and first_level_headings[-1].strip() != "Sources":
        errors.append("# Sources must be the final level-one section")
    if not SOURCE_RE.search(structural_text):
        errors.append("# Sources must contain at least one Markdown link to an HTTP(S) source")

    if require_version_lead:
        back_match = required_matches[1]
        first_back_line = ""
        if back_match:
            for line in text[back_match.end():].splitlines():
                if re.match(r"^#{1,6} ", line):
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

    images = IMAGE_RE.findall(structural_text)
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
        image_filename = Path(target).name
        if image_filename not in alt_text:
            errors.append(
                f"visual {target!r} alt text must include filename {image_filename!r}"
            )
        image_path = (card_path.parent / target).resolve()
        if image_path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            errors.append(f"visual {target!r} has an unsupported file type")
        if check_local_files and not image_path.is_file():
            errors.append(f"visual file does not exist: {target}")

    if mode == "complex":
        step_matches = list(STEP_HEADING_RE.finditer(structural_text))
        for step_match in step_matches:
            heading = step_match.group(0).lstrip(" #")
            if step_match.group(1) != "##":
                errors.append(
                    f"step heading {heading!r} must use ##; "
                    f"migrate {step_match.group(1)} Step to ## Step"
                )
            section_start = step_match.end()
            # Stop at the next peer/parent section or any subsequent step,
            # including a deeper legacy step during a partial migration.
            boundary = next((match for match in headings
                             if match.start() > step_match.start()
                             and (len(match.group(1)) <= len(step_match.group(1))
                                  or STEP_HEADING_RE.match(structural_text, match.start()))), None)
            section_end = boundary.start() if boundary else len(text)
            step_section = structural_text[section_start:section_end]
            step_images = IMAGE_RE.findall(step_section)
            if not any(Path(target).suffix.lower() == ".svg" and not urlsplit(target).scheme
                       and not target.startswith("//") for _, target in step_images):
                errors.append(f"{heading!r} requires its own local .svg diagram")

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

<sub>[Back to Java](../Readme.md#content)</sub>

<!-- Card mode: simple. Validate with --mode simple. -->

# Front

What is an atomic update?

# Back

An atomic update is observed as one indivisible action.

![atomic-update.svg](svg/atomic-update.svg)

```java
counter.incrementAndGet();
```

# Sources

- [Java API](https://example.com/api)
"""
    complex_card = simple.replace(
        "![atomic-update.svg](svg/atomic-update.svg)",
        "![before.svg](svg/before.svg)\n\n![after.svg](svg/after.svg)",
    ).replace("Card mode: simple. Validate with --mode simple.",
              "Card mode: complex. Validate with --mode complex.")
    assert not validate_text(simple, Path("card.md"), "simple", check_local_files=False)
    assert not validate_text(complex_card, Path("card.md"), "complex", check_local_files=False)

    # Navigation is required before the mode comment and is outside the budget.
    navigation = "<sub>[Back to Java](../Readme.md#content)</sub>"
    assert countable_text(simple) == countable_text(simple.replace(navigation + "\n", ""))
    invalid_navigation = (
        simple.replace(navigation, ""),
        simple.replace(navigation, navigation + "\n\n" + navigation),
        simple.replace(navigation, "- " + navigation),
        simple.replace(navigation + "\n\n", "") + "\n" + navigation + "\n",
        simple.replace(navigation + "\n\n", navigation + "\n"),
    )
    for invalid_card in invalid_navigation:
        assert any("navigation" in error for error in validate_text(
            invalid_card, Path("card.md"), "simple", check_local_files=False,
        ))
    for target in ("https://example.com/Readme.md", "/Readme.md", "../notes.md", "other/Readme.md"):
        assert any("relative path to a containing index README" in error
                   for error in validate_text(
                       simple.replace("../Readme.md#content", target),
                       Path("card.md"), "simple", check_local_files=False,
                   ))

    # Resolve navigation from the card directory, including deeper root fallbacks.
    with TemporaryDirectory() as directory:
        root = Path(directory)
        card_path = root / "subject" / "topic" / "card.md"
        image_path = card_path.parent / "svg" / "atomic-update.svg"
        image_path.parent.mkdir(parents=True)
        image_path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        index = root / "subject" / "Readme.md"
        index.write_text("# Java\n\n## Content\n", encoding="utf-8")
        assert not validate_text(simple, card_path, "simple")
        index.unlink()
        assert any("navigation README does not exist" in error
                   for error in validate_text(simple, card_path, "simple"))
        (root / "README.md").write_text("# Anki Flashcards\n", encoding="utf-8")
        fallback = simple.replace(navigation, "<sub>[Back to Anki Flashcards](../../README.md)</sub>")
        assert not validate_text(fallback, card_path, "simple")

    # Card boundaries use exact level-one headings, not legacy or prefix matches.
    for heading in ("# Front", "# Back", "# Sources"):
        for replacement in ("#" + heading, heading + " details"):
            assert any(f"missing required heading: {heading}" in error
                       for error in validate_text(
                           simple.replace(heading, replacement), Path("card.md"),
                           "simple", check_local_files=False,
                       ))

    # Teaching sections use ## and subsections use ###; code remains literal.
    for mode, card in (("simple", simple), ("complex", complex_card)):
        with_sections = card.replace(
            "An atomic update", "## Explanation\n\n### Key detail\n\nAn atomic update"
        )
        assert not validate_text(with_sections, Path("card.md"), mode, check_local_files=False)
        for level in range(4, 7):
            with_deep_heading = with_sections.replace("### Key detail", "#" * level + " Key detail")
            assert any("is too deep" in error for error in validate_text(
                with_deep_heading, Path("card.md"), mode, check_local_files=False,
            ))
        assert any("# Sources must be the final level-one section" in error
                   for error in validate_text(
                       card + "\n# Appendix\n", Path("card.md"), mode, check_local_files=False,
                   ))
        with_literal_headings = card.replace(
            "# Sources", "```markdown\n#### Literal heading\n# Front\n# Back\n```\n\n# Sources"
        )
        assert not validate_text(
            with_literal_headings, Path("card.md"), mode, check_local_files=False
        )
        assert "#### Literal heading" in countable_text(with_literal_headings)

    # Examples in code cannot supply missing card boundaries.
    fake_front = simple.replace("# Front", "```markdown\n# Front\n```")
    assert any("missing required heading: # Front" in error for error in validate_text(
        fake_front, Path("card.md"), "simple", check_local_files=False,
    ))

    # Mode metadata must be present, correctly positioned, and consistent with the CLI.
    simple_comment = "<!-- Card mode: simple. Validate with --mode simple. -->"
    complex_comment = "<!-- Card mode: complex. Validate with --mode complex. -->"
    without_comment = simple.replace(simple_comment + "\n", "")
    assert countable_text(simple) == countable_text(without_comment)
    assert not validate_text(
        simple.replace(simple_comment, simple_comment + "\n\n"),
        Path("card.md"), "simple", check_local_files=False,
    )
    invalid_comments = (
        without_comment,
        simple.replace(simple_comment, "\\" + simple_comment),
        simple.replace(simple_comment, simple_comment.replace("simple", "advanced")),
        simple.replace(simple_comment, simple_comment.replace("--mode simple", "--mode complex")),
        simple.replace(simple_comment, complex_comment),
        simple.replace(simple_comment, simple_comment + "\n" + complex_comment),
        simple.replace(simple_comment, simple_comment + "\nIntervening prose"),
        simple.replace(simple_comment, "Intervening prose\n\n" + simple_comment),
        simple.replace("# Atomic update\n\n", "# Atomic update\n", 1),
        simple.replace(simple_comment + "\n\n", simple_comment + "\n", 1),
        without_comment.replace("# Back", simple_comment + "\n# Back"),
    )
    for invalid_card in invalid_comments:
        assert any("card mode comment" in error for error in validate_text(
            invalid_card, Path("card.md"), "simple", check_local_files=False,
        ))
    assert any("must match validation --mode simple" in error for error in validate_text(
        complex_card, Path("card.md"), "simple", check_local_files=False,
    ))
    assert any("must match validation --mode complex" in error for error in validate_text(
        simple, Path("card.md"), "complex", check_local_files=False,
    ))

    # Local image alt text names the linked file, with optional teaching context.
    descriptive_alt = simple.replace(
        "![atomic-update.svg]", "![atomic-update.svg — An indivisible update]"
    )
    assert not validate_text(
        descriptive_alt, Path("card.md"), "simple", check_local_files=False
    )
    nested_image = simple.replace("svg/atomic-update.svg", "images/steps/atomic-update.svg")
    assert not validate_text(
        nested_image, Path("card.md"), "simple", check_local_files=False
    )
    for invalid_alt in ("Atomic update", "other-update.svg", "atomic-update"):
        missing_filename = simple.replace("![atomic-update.svg]", f"![{invalid_alt}]")
        assert any("alt text must include filename 'atomic-update.svg'" in error
                   for error in validate_text(
                       missing_filename, Path("card.md"), "simple", check_local_files=False
                   ))

    # The budget applies to the Back only; padding goes there, not into Sources.
    padded = simple.replace("# Sources", "PAD\n\n# Sources")
    body = len(countable_text(padded))
    at_simple_limit = padded.replace("PAD", "P" * (SIMPLE_CHARACTER_LIMIT - body + 3))
    assert len(countable_text(at_simple_limit)) == SIMPLE_CHARACTER_LIMIT
    assert not validate_text(
        at_simple_limit, Path("card.md"), "simple", check_local_files=False
    )
    above_simple_limit = at_simple_limit.replace("\n\n# Sources", "x\n\n# Sources")
    assert any("allows at most 3000" in error for error in validate_text(
        above_simple_limit, Path("card.md"), "simple", check_local_files=False
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
        check_local_files=False,
        require_version_lead=True,
    )
    assert any("standalone bold sentence" in error for error in validate_text(
        simple,
        Path("card.md"),
        "simple",
        check_local_files=False,
        require_version_lead=True,
    ))

    process_card = complex_card.replace(
        "# Sources",
        "## Step 1 — Read\n\n![read.svg](svg/read.svg)\n\n"
        "## Step 2 — Write\n\n![write.svg](svg/write.svg)\n\n# Sources",
    )
    assert not validate_text(process_card, Path("card.md"), "complex", check_local_files=False)

    missing_step_svg = process_card.replace("![write.svg](svg/write.svg)", "Step explanation")
    assert any("requires its own local .svg" in error for error in validate_text(
        missing_step_svg, Path("card.md"), "complex", check_local_files=False
    ))

    no_image = simple.replace("![atomic-update.svg](svg/atomic-update.svg)\n\n", "")
    assert any("requires at least" in error for error in validate_text(
        no_image, Path("card.md"), "simple", check_local_files=False
    ))

    # A huge Front or Sources section must not push a card over budget.
    fat_front = simple.replace(
        "What is an atomic update?", "What is an atomic update? " + "q" * 5000
    )
    assert not validate_text(fat_front, Path("card.md"), "simple", check_local_files=False)
    nested_front = fat_front.replace("What is an atomic update?", "## Prompt details")
    assert not validate_text(nested_front, Path("card.md"), "simple", check_local_files=False)
    fat_back_section = simple.replace(
        "An atomic update", "## Explanation\n\n" + "x" * 5000 + "\n\nAn atomic update"
    )
    assert any("allows at most 3000" in error for error in validate_text(
        fat_back_section, Path("card.md"), "simple", check_local_files=False,
    ))
    fat_sources = simple.replace(
        "- [Java API](https://example.com/api)",
        "- [Java API](https://example.com/api)\n\n  " + "s" * 5000,
    )
    assert not validate_text(fat_sources, Path("card.md"), "simple", check_local_files=False)
    assert "Front" not in countable_text(simple)
    assert "Sources" not in countable_text(simple)
    assert "Atomic update" in countable_text(simple)

    bare_fence = simple.replace("```java", "```", 1)
    assert any("no language tag" in error for error in validate_text(
        bare_fence, Path("card.md"), "simple", check_local_files=False
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

    images = len(IMAGE_RE.findall(mask_fenced_code(text)))
    counted = len(countable_text(text))
    budget = f"{counted} counted" if args.mode == "simple" else f"{len(text)}"
    print(f"{args.card}: OK ({args.mode}, {budget} characters, {images} visual(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
