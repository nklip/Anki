#!/usr/bin/env python3
"""Validate structural invariants for Anki Markdown cards."""

from __future__ import annotations

import argparse
import re
import sys
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from markdown_anchors import CODE_SPAN_RE, add_heading_anchor, markdown_anchors, plain_heading
from markdown_fences import mask_fenced_code, scan_fenced_code


IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SOURCE_RE = re.compile(r"^- \[[^\]]+\]\(https?://[^)]+\)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+([^\r\n]+?)[ \t]*\r?$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
NAVIGATION_RE = re.compile(
    r"^<sub>\[Back to ([^\]\n]+)\]\(([^)\s]+)\)</sub>[ \t]*(?:\r?\n|$)",
    re.MULTILINE,
)
STEP_LABEL_RE = re.compile(r"^(?:\*\*|__)?Step[ \t]+\d+\b")
SECTION_NUMBER_RE = re.compile(r"^([0-9]+)\.[ \t]+")
CONTENTS_ITEM_RE = re.compile(r" {0,3}([0-9]+)\.[ \t]+\[(.+)\]\(#([^\s)]+)\)[ \t]*")
REVIEW_TITLE = "Check your understanding"
REVIEW_ITEM_RE = re.compile(r"^( {0,3})([0-9]+)\.[ \t]+(?=\S)", re.MULTILINE)
DETAILS_BLOCK_RE = re.compile(
    r"^[ \t]*<details\b[^>\r\n]*>[ \t]*\r?\n.*?(?:^[ \t]*</details>[ \t]*\r?$|\Z)",
    re.MULTILINE | re.DOTALL,
)
BOLD_LABEL_RE = re.compile(
    r"\*\*(?!\s)(?:(?!\*\*).)+(?<!\s)\*\*|__(?!\s)(?:(?!__).)+(?<!\s)__"
)
VERSION_EVENT_RE = re.compile(
    r"\b(?:added|introduced|previewed|released|finalized|became|available)\b",
    re.IGNORECASE,
)
DATE_PATTERN = (
    r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},?\s+\d{4})"
)
# These are specific editorial statements, not a vocabulary blacklist. In
# particular, checks at runtime, release dates, version scope, and ordinary
# diagram explanations do not describe how the study material was authored.
AUTHORING_BOILERPLATE_RULES = (
    ("fact/source verification", re.compile(
        r"(?:^|(?<=[.!?;:(—])\s*)\s*(?:"
        r"(?:(?:all|the|these|key|technical|primary|official|original\s+article)\s+)*"
        r"(?:facts?|claims?|sources?)\s+"
        r"(?:(?:were|are|have\s+been)\s+)?(?:fact[- ]checked|checked|verified|rechecked)"
        r"(?:\s+against\s+[^.!?;]{0,100}\b(?:documentation|docs|sources?|references?|manuals?|"
        r"specifications?)\b|\s+(?:on\s+|as\s+of\s+)?" + DATE_PATTERN +
        r"|(?=\s*(?:[.;]|$)))"
        r"|(?:official\s+)?(?:[\w'-]+\s+){0,3}documentation"
        r"(?:\s+and\s+(?:resources|sources))?,?\s+"
        r"(?:(?:was|were|has\s+been|have\s+been)\s+)?"
        r"(?:consulted|checked|verified|accessed)\b"
        r"|(?:this|the)\s+(?:[\w-]+\s+){0,5}"
        r"(?:card|article|material|content|snapshot|explanation)\s+"
        r"(?:was|has\s+been)\s+(?:last\s+)?(?:checked|verified|rechecked)\s+on\s*"
        + DATE_PATTERN +
        r"|(?:fact[- ]checking|verification|access)\s+date\s*:\s*" + DATE_PATTERN +
        r"|(?:last\s+)?(?:fact[- ]checked|checked|verified|rechecked|accessed)"
        r"\s*(?:(?:on|as\s+of)\s+|:\s*)?" + DATE_PATTERN + r")",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("local-note migration history", re.compile(
        r"\blocal\s+(?:Anki\s+)?note\s+ID\s*[:#]?\s*\d+\b"
        r"|(?:^|(?<=[.!?;])\s+)\s*(?:"
        r"original\s+(?:study\s+|Anki\s+)?note\s*:"
        r"|(?:(?:this|the)\s+(?:card|article|lesson)\s+"
        r"(?:was|has\s+been)\s+)?"
        r"(?:migrated(?:\s+and\s+rewritten)?|rewritten)\s+from\b"
        r"[^.!?;]{0,180}\b(?:local\b[^.!?;]{0,100}\b(?:note|deck)"
        r"|Anki\s+(?:note|deck))\b)",
        re.IGNORECASE | re.MULTILINE,
    )),
    ("diagram production/provenance", re.compile(
        r"\b(?:local\s+)?(?:diagram|illustration|icon)s?\s+"
        r"(?:icon\s+)?provenance(?=\s*(?::|$)|\s+(?:and\s+adaptations\s+)?"
        r"(?:is|are)\s+(?:identified|listed|documented)\b)"
        r"|\b(?:diagrams?|SVGs?|illustrations?|visuals?)\s+"
        r"(?:are|were|have\s+been)\s+(?:all\s+)?"
        r"(?:newly\s+drawn|redrawn|original\s+teaching\s+illustrations?)\b"
        r"|\blayouts?(?:\s+and\s+labels)?\s+"
        r"(?:are|were|have\s+been)\s+(?:newly\s+)?(?:drawn|redrawn)\b",
        re.IGNORECASE | re.MULTILINE,
    )),
)
ALLOWED_IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
SIMPLE_CHARACTER_LIMIT = 3500
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


def heading_label(heading: re.Match[str]) -> str:
    """Remove an optional closing ATX sequence for checks and diagnostics."""
    return re.sub(r"[ \t]+#+$", "", heading.group(2)).strip()


def is_step_heading(heading: re.Match[str]) -> bool:
    """Recognize numbered steps, including labels with leading bold markup."""
    label = heading_label(heading)
    if heading.group(1) == "##":
        label = SECTION_NUMBER_RE.sub("", label)
    return len(heading.group(1)) >= 2 and bool(STEP_LABEL_RE.match(label))


def review_question_errors(review: str, required: int) -> list[str]:
    # Preserve offsets so each visible list item can be paired with its own answer.
    visible = DETAILS_BLOCK_RE.sub(lambda m: re.sub(r"[^\r\n]", " ", m[0]), review)
    items = list(REVIEW_ITEM_RE.finditer(visible))
    if items:
        list_indent = items[0][1]
        items = [item for item in items if item[1] == list_indent]

    errors = []
    if len(items) < required:
        errors.append(
            f"Check your understanding needs at least {required} numbered review questions "
            f"for {required} teaching sections; found {len(items)}"
        )
    for number, item in enumerate(items, 1):
        if item[2] != str(number):
            errors.append(f"review question {number} must start with {number}.")
        end = items[number].start() if number < len(items) else len(review)
        answers = DETAILS_BLOCK_RE.findall(review, item.end(), end)
        if len(answers) == 1:
            lines = [line.rstrip() for line in answers[0].splitlines() if line.strip()]
            indent = " " * len(item[0])
            if (lines[:2] == [indent + "<details>", indent + "<summary>Answer</summary>"]
                    and lines[-1] == indent + "</details>"):
                continue
        errors.append(
            f"review question {number} needs one indented, closed <details> answer "
            "with <summary>Answer</summary>"
        )
    return errors


def article_section_errors(article: str, headings: list[re.Match[str]]) -> list[str]:
    """Check the article outline and review count. Topic coverage needs an author."""
    errors = []
    generated: set[str] = set()
    sections = []
    expected = []
    reviews = []
    last_main_heading = None
    for section in headings:
        label = heading_label(section)
        fragment = add_heading_anchor(label, generated)
        in_article = section.start() < len(article)
        if in_article and len(section[1]) <= 2:
            last_main_heading = section
        if section[1] != "##":
            continue
        title = plain_heading(SECTION_NUMBER_RE.sub("", label))
        prefix = SECTION_NUMBER_RE.match(label)
        if title == REVIEW_TITLE:
            reviews.append(section)
            if prefix:
                errors.append(f"use the unnumbered heading '## {REVIEW_TITLE}'")
            continue
        if not in_article:
            continue
        sections.append(section)
        number = len(sections)
        if not prefix or prefix[1] != str(number):
            errors.append(f"article section {label!r} must start with '## {number}. '")
        expected.append((str(number), title, fragment))

    if len(reviews) != 1 or reviews[0] != last_main_heading:
        errors.append(f"place exactly one '## {REVIEW_TITLE}' section immediately before '# Sources'")
    else:
        errors.extend(review_question_errors(article[reviews[0].end():], len(sections)))
    if not sections:
        errors.append("include a numbered ## teaching section before Check your understanding")
        return errors

    list_items = re.findall(r"^ {0,3}[0-9]+[.)][ \t]+([^\r\n]+)", article, re.MULTILINE)
    if any(plain_heading(item).strip() == REVIEW_TITLE for item in list_items):
        errors.append(f"omit '{REVIEW_TITLE}' from numbered lists, including the contents")
    intro = article[:sections[0].start()]
    links = (CONTENTS_ITEM_RE.fullmatch(line) for line in intro.splitlines() if line.strip())
    for is_link_list, group in groupby(links, key=bool):
        if is_link_list:
            contents = [(link[1], plain_heading(link[2]), unquote(link[3])) for link in group]
            if contents == expected:
                break
    else:
        errors.append("include a numbered contents list before the first ## section with "
                      "one matching title and anchor per teaching section, in order")
    return errors


def is_fully_bold_label(label: str) -> bool:
    """Require one enclosing bold span; inline code contains literal markers."""
    masked_label = CODE_SPAN_RE.sub("code", label)
    return BOLD_LABEL_RE.fullmatch(masked_label) is not None


def mask_comments(text: str) -> str:
    """Hide HTML comments without changing offsets or line boundaries."""
    return HTML_COMMENT_RE.sub(lambda match: re.sub(r"[^\r\n]", " ", match[0]), text)


def authoring_boilerplate_errors(structural_text: str) -> list[str]:
    """Check unfenced prose with source offsets intact, including wrapped text.

    The caller has masked fences and comments. Ignore image markup and link
    destinations; retain link labels and inline text, including numeric note
    IDs in backticks. This intentionally is not a full Markdown/NLP parser.
    """
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\r\n]", " ", match[0])

    prose = IMAGE_RE.sub(blank, structural_text)
    prose = re.sub(
        r"\[([^\]]+)\]\((?:[^()\r\n]|\([^()\r\n]*\))*\)",
        lambda match: " " + match[1] + " " * (len(match[0]) - len(match[1]) - 1),
        prose,
    )
    prose = re.sub(r"</?[A-Za-z][^>]*>", blank, prose)
    prose = re.sub(r"[*_`]", " ", prose)
    prose = re.sub(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|[-+>][ \t]+|\d+[.)][ \t]+)", blank, prose)

    errors: list[str] = []
    seen: set[tuple[int, str]] = set()
    # Keep rule context inside a paragraph/list, without joining across blank
    # lines or fenced blocks. Single line wraps remain searchable whitespace.
    for paragraph in re.finditer(r"(?:[^\r\n]*\S[^\r\n]*(?:\r?\n|$))+", prose):
        for reason, pattern in AUTHORING_BOILERPLATE_RULES:
            for match in pattern.finditer(paragraph[0]):
                start = paragraph.start() + match.start()
                start += len(match[0]) - len(match[0].lstrip())
                line = prose.count("\n", 0, start) + 1
                if (line, reason) not in seen:
                    errors.append(
                        f"line {line}: authoring boilerplate ({reason}); "
                        "remove the process note; keep teaching content, source links, "
                        "and required attribution"
                    )
                    seen.add((line, reason))
    return errors


def countable_text(text: str) -> str:
    """Return body Markdown, excluding the title, navigation, and final Sources.

    Every body character counts, including code and image references. Trim
    only outer whitespace and normalize CRLF to LF before counting Unicode
    characters. Fenced/commented lookalikes cannot change the body boundaries.
    """
    structural_text = mask_comments(mask_fenced_code(text))
    title = re.match(r"^# [^\r\n]+\r?\n", structural_text)
    start = title.end() if title else 0
    navigation_links = list(NAVIGATION_RE.finditer(structural_text))
    if len(navigation_links) == 1:
        navigation = navigation_links[0]
        if navigation.start() >= start and not text[start:navigation.start()].strip():
            start = navigation.end()
    first_level_headings = [
        heading for heading in HEADING_RE.finditer(structural_text) if heading.group(1) == "#"
    ]
    end = len(text)
    if first_level_headings and heading_label(first_level_headings[-1]) == "Sources":
        end = max(start, first_level_headings[-1].start())
    return text[start:end].replace("\r\n", "\n").strip()


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
    under_chars: int | None = None,
) -> list[str]:
    errors: list[str] = []
    structural_text, blocks, fence_errors = scan_fenced_code(text)
    if mode not in {"simple", "complex"}:
        raise ValueError(f"unsupported card mode: {mode}")
    if HTML_COMMENT_RE.search(structural_text):
        errors.append(
            "HTML comments are not allowed outside fenced code; "
            "remove mode comments and select the mode explicitly"
        )
    structural_text = mask_comments(structural_text)
    errors.extend(authoring_boilerplate_errors(structural_text))

    title = re.match(r"^# [^\r\n]+\r?\n", text)
    if not title:
        errors.append("the first line must be one level-one title")

    headings = list(HEADING_RE.finditer(structural_text))
    sources = [
        heading for heading in headings
        if heading.group(1) == "#" and heading_label(heading) == "Sources"
    ]
    if not sources:
        if any(heading.group(1) == "##" and heading_label(heading) == "Sources"
               for heading in headings):
            errors.append("boundary '## Sources' must use '# Sources'")
        else:
            errors.append("missing required heading: # Sources")
    elif len(sources) > 1:
        errors.append("include exactly one required heading: # Sources")
    for heading in headings:
        if len(heading.group(1)) <= 2 and heading_label(heading) in {"Front", "Back"}:
            errors.append(
                f"boundary {heading.group(1) + ' ' + heading_label(heading)!r} is not allowed; "
                "both modes place teaching content directly after the navigation link"
            )

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

    header_parts = (title, navigation)
    invalid_header = any(
        previous is not None and following is not None and (
            following.start() < previous.end()
            or not re.fullmatch(r"(?:[ \t]*\r?\n)+", text[previous.end():following.start()])
        )
        for previous, following in zip(header_parts, header_parts[1:])
    )
    if navigation is not None:
        remainder = text[navigation.end():]
        body_end = sources[0].start() if sources else len(text)
        if (not re.match(r"[ \t]*\r?\n", remainder)
                or not text[navigation.end():body_end].strip()):
            invalid_header = True
    if invalid_header:
        errors.append(
            "header order must be title, navigation link, teaching content, "
            "with a blank line between each and no intervening content"
        )

    parent_level = 0
    for heading in headings:
        level = len(heading.group(1))
        label = heading_label(heading)
        if level <= 3:
            parent_level = level
        if mode == "complex" and is_step_heading(heading):
            # Step-level and diagram checks below take precedence over
            # generic sub-item advice, even when the step label is bold.
            continue
        if level == 4:
            if not is_fully_bold_label(label):
                errors.append(
                    f"level-four heading {label!r} must have fully bold text: "
                    "use #### **Named sub-item**"
                )
            if parent_level != 3:
                errors.append(
                    f"level-four heading {label!r} must be nested within a ### subsection"
                )
        elif level >= 5:
            errors.append(
                f"heading {label!r} is too deep: "
                "use ## for teaching sections, ### for subsections, "
                "and bold #### headings for named sub-items within subsections"
            )

    first_level_headings = [heading_label(match) for match in headings if match.group(1) == "#"]
    if first_level_headings and first_level_headings[-1] != "Sources":
        errors.append("# Sources must be the final level-one section")
    source_text = structural_text[sources[-1].end():] if sources else ""
    if not SOURCE_RE.search(source_text):
        errors.append("# Sources must contain at least one Markdown link to an HTTP(S) source")

    if require_version_lead:
        body_start = navigation
        first_body_line = ""
        if body_start:
            for line in text[body_start.end():].splitlines():
                if re.match(r"^#{1,6} ", line):
                    break
                if line.strip():
                    first_body_line = line.strip()
                    break
        if not re.fullmatch(r"\*\*\S(?:.*\S)?\*\*", first_body_line):
            errors.append(
                "a versioned feature card must start the teaching body "
                "with one standalone bold sentence"
            )
        else:
            lead_text = first_body_line[2:-2]
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
            f"in the teaching body; found {character_count}"
        )
    if under_chars is not None and character_count >= under_chars:
        errors.append(
            f"the teaching body must be under {under_chars} characters "
            f"(found {character_count})"
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
        article_end = sources[0].start() if sources else len(structural_text)
        errors.extend(article_section_errors(structural_text[:article_end], headings))
        step_matches = [heading for heading in headings if is_step_heading(heading)]
        for step_match in step_matches:
            heading = heading_label(step_match)
            level = len(step_match.group(1))
            # A level-three step belongs to the nearest preceding level-two
            # section, unless a level-one heading has closed that section.
            parent = next((match for match in reversed(headings)
                           if match.start() < step_match.start()
                           and len(match.group(1)) < level), None)
            if level != 2 and not (
                level == 3 and parent is not None and parent.group(1) == "##"
            ):
                errors.append(
                    f"step heading {heading!r} must use ## N. Step M … or "
                    "### Step N … nested within a ## section "
                    f"(found {step_match.group(1)})"
                )
            section_start = step_match.end()
            # Stop at the next peer/parent section or any subsequent step,
            # so nested steps cannot supply a previous step's own diagram.
            boundary = next((match for match in headings
                             if match.start() > step_match.start()
                             and (len(match.group(1)) <= len(step_match.group(1))
                                  or is_step_heading(match))), None)
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

An atomic update is observed as one indivisible action.

![atomic-update.svg](images/atomic-update.svg)

```java
counter.incrementAndGet();
```

# Sources

- [Java API](https://example.com/api)
"""
    process_contents = """1. [Step 1 — Read](#1-step-1--read)
2. [Step 2 — Write](#2-step-2--write)"""
    process_sections = """## 1. Step 1 — Read

![read.svg](images/read.svg)

Read the current count with `get()`.

## 2. Step 2 — Write

![write.svg](images/write.svg)

Increment the counter in one atomic operation."""
    review = """## Check your understanding

1. Can another thread change the value after your read?

   <details>
   <summary>Answer</summary>

   Yes. The read observes the value at one moment.

   </details>

2. Two threads each increment the counter once. What is the net change?

   <details>
   <summary>Answer</summary>

   The count rises by two because both increments take effect.

   </details>"""
    complex_card = simple.replace(
        "![atomic-update.svg](images/atomic-update.svg)",
        f"{process_contents}\n\n{process_sections}",
    ).replace("# Sources", f"{review}\n\n# Sources")
    assert not validate_text(simple, Path("card.md"), "simple", check_local_files=False)
    assert not validate_text(complex_card, Path("card.md"), "complex", check_local_files=False)

    # Editorial announcements are not study content; literal examples stay valid.
    boilerplate = "**Facts** checked against\nAWS documentation on 17 November 2026."
    for mode, card in (("simple", simple), ("complex", complex_card)):
        with_boilerplate = card.replace("# Sources", boilerplate + "\n\n# Sources")
        assert any("authoring boilerplate" in error for error in validate_text(
            with_boilerplate, Path("card.md"), mode, check_local_files=False,
        ))
        literal_boilerplate = card.replace(
            "```java", f"```markdown\n{boilerplate}\n```\n\n```java"
        )
        assert not validate_text(
            literal_boilerplate, Path("card.md"), mode, check_local_files=False,
        )

    # Navigation is required immediately after the title and is outside the budget.
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
        image_path = card_path.parent / "images" / "atomic-update.svg"
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

    # Sources still requires the exact level-one heading.
    for heading in ("# Sources",):
        for replacement in ("#" + heading, heading + " details"):
            expected = (
                f"boundary {replacement!r} must use {heading!r}"
                if replacement == "#" + heading else f"missing required heading: {heading}"
            )
            assert expected in validate_text(
                simple.replace(heading, replacement), Path("card.md"),
                "simple", check_local_files=False,
            )

    # Bold named sub-items may use #### within ### subsections; code remains literal.
    for mode, card in (("simple", simple), ("complex", complex_card)):
        parent = "## Explanation\n\n" if mode == "simple" else ""
        with_sections = card.replace("```java", f"{parent}### Key detail\n\n```java")
        assert not validate_text(with_sections, Path("card.md"), mode, check_local_files=False)
        with_use_case = with_sections.replace(
            "### Key detail", "### Key detail\n\n#### **Use case: Updating a counter**"
        )
        assert not validate_text(with_use_case, Path("card.md"), mode, check_local_files=False)
        for level in range(5, 7):
            with_deep_heading = with_sections.replace("### Key detail", "#" * level + " Key detail")
            assert any("is too deep" in error for error in validate_text(
                with_deep_heading, Path("card.md"), mode, check_local_files=False,
            ))
        assert any("# Sources must be the final level-one section" in error
                   for error in validate_text(
                       card + "\n# Appendix\n", Path("card.md"), mode, check_local_files=False,
                   ))
        with_literal_headings = card.replace(
            "```java", "```markdown\n#### Literal heading\n# Front\n# Back\n```\n\n```java"
        )
        assert not validate_text(
            with_literal_headings, Path("card.md"), mode, check_local_files=False
        )
        assert "#### Literal heading" in countable_text(with_literal_headings)

    # Both modes use the shared layout, with no legacy boundaries or metadata.
    simple_comment = "<!-- Card mode: simple. Validate with --mode simple. -->"
    complex_comment = "<!-- Card mode: complex. Validate with --mode complex. -->"
    for mode, card in (("simple", simple), ("complex", complex_card)):
        assert not validate_text(card, Path("card.md"), mode, check_local_files=False)
        crlf_card = card.replace("\n", "\r\n")
        assert not validate_text(crlf_card, Path("card.md"), mode, check_local_files=False)
        for heading in ("# Front", "# Back", "## Front", "## Back"):
            legacy = card.replace("# Sources", heading + "\n\n# Sources")
            assert any("is not allowed" in error for error in validate_text(
                legacy, Path("card.md"), mode, check_local_files=False,
            ))
        for comment in (simple_comment, complex_comment, "<!-- Editorial note -->"):
            with_comment = card.replace("# Sources", comment + "\n\n# Sources")
            assert any("HTML comments" in error for error in validate_text(
                with_comment, Path("card.md"), mode, check_local_files=False,
            ))
            literal_comment = card.replace("```java", f"```html\n{comment}\n```\n\n```java")
            assert not validate_text(
                literal_comment, Path("card.md"), mode, check_local_files=False,
            )
    assert not validate_text(complex_card, Path("card.md"), "simple", check_local_files=False)

    # Local image alt text names the linked file, with optional teaching context.
    descriptive_alt = simple.replace(
        "![atomic-update.svg]", "![atomic-update.svg — An indivisible update]"
    )
    assert not validate_text(
        descriptive_alt, Path("card.md"), "simple", check_local_files=False
    )
    nested_image = simple.replace("images/atomic-update.svg", "images/steps/atomic-update.svg")
    assert not validate_text(
        nested_image, Path("card.md"), "simple", check_local_files=False
    )
    for invalid_alt in ("Atomic update", "other-update.svg", "atomic-update"):
        missing_filename = simple.replace("![atomic-update.svg]", f"![{invalid_alt}]")
        assert any("alt text must include filename 'atomic-update.svg'" in error
                   for error in validate_text(
                       missing_filename, Path("card.md"), "simple", check_local_files=False
                   ))

    # The budget applies to the body only; padding goes there, not into Sources.
    padded = simple.replace("# Sources", "PAD\n\n# Sources")
    body = len(countable_text(padded))
    at_simple_limit = padded.replace("PAD", "界" * (SIMPLE_CHARACTER_LIMIT - body + 3))
    assert len(countable_text(at_simple_limit)) == SIMPLE_CHARACTER_LIMIT
    assert not validate_text(
        at_simple_limit, Path("card.md"), "simple", check_local_files=False
    )
    above_simple_limit = at_simple_limit.replace("\n\n# Sources", "x\n\n# Sources")
    assert any(f"allows at most {SIMPLE_CHARACTER_LIMIT}" in error for error in validate_text(
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

    grouped_contents = "1. [Working with a counter](#1-working-with-a-counter)"
    nested_process_card = complex_card.replace(process_contents, grouped_contents).replace(
        "## 1. Step 1", "## 1. Working with a counter\n\n### Step 1"
    ).replace("## 2. Step 2", "### Step 2")
    assert not validate_text(
        nested_process_card, Path("card.md"), "complex", check_local_files=False
    )
    orphaned_steps = nested_process_card.replace("## 1. Working with a counter\n\n", "")
    assert any("nested within a ## section" in error for error in validate_text(
        orphaned_steps, Path("card.md"), "complex", check_local_files=False
    ))
    for card in (complex_card, nested_process_card):
        missing_step_svg = card.replace("![write.svg](images/write.svg)", "Step explanation")
        assert any("requires its own local .svg" in error for error in validate_text(
            missing_step_svg, Path("card.md"), "complex", check_local_files=False
        ))

    no_image = simple.replace("![atomic-update.svg](images/atomic-update.svg)\n\n", "")
    assert any("requires at least" in error for error in validate_text(
        no_image, Path("card.md"), "simple", check_local_files=False
    ))

    # A huge opening title or Sources section must not push a card over budget.
    fat_title = simple.replace("# Atomic update", "# " + "t" * 5000)
    assert not validate_text(fat_title, Path("card.md"), "simple", check_local_files=False)
    fat_body_section = simple.replace(
        "An atomic update", "## Explanation\n\n" + "x" * 5000 + "\n\nAn atomic update"
    )
    assert any(f"allows at most {SIMPLE_CHARACTER_LIMIT}" in error for error in validate_text(
        fat_body_section, Path("card.md"), "simple", check_local_files=False,
    ))
    fat_sources = simple.replace(
        "- [Java API](https://example.com/api)",
        "- [Java API](https://example.com/api)\n\n  " + "s" * 5000,
    )
    assert not validate_text(fat_sources, Path("card.md"), "simple", check_local_files=False)
    assert "Sources" not in countable_text(simple)
    assert "Atomic update" not in countable_text(simple)
    assert "An atomic update" in countable_text(simple)

    bare_fence = simple.replace("```java", "```", 1)
    assert any("no language tag" in error for error in validate_text(
        bare_fence, Path("card.md"), "simple", check_local_files=False
    ))
    print("Self-test passed")


def parse_character_limit(value: str) -> int:
    match = re.fullmatch(r"([0-9]+)([kK]?)", value)
    if not match or int(match[1]) == 0:
        raise argparse.ArgumentTypeError("use a positive character limit such as 5000 or 10k")
    return int(match[1]) * (1000 if match[2] else 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("card", nargs="?", type=Path, help="Markdown card to validate")
    parser.add_argument(
        "--mode", choices=("simple", "complex"),
        help="required for card validation; select the intended size and visual requirements",
    )
    parser.add_argument(
        "--under-chars", type=parse_character_limit, metavar="N",
        help="require fewer than N teaching-body characters (e.g. 5K, 10k, or 15000)",
    )
    parser.add_argument(
        "--require-version-lead",
        action="store_true",
        help="require a bold opening body line naming a feature lifecycle event and version",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if args.card is None:
        parser.error("card path is required unless --self-test is used")
    if args.mode is None:
        parser.error("--mode simple or --mode complex is required unless --self-test is used")
    if args.card.suffix.lower() != ".md":
        print(f"ERROR: expected an .md file: {args.card}", file=sys.stderr)
        return 2
    if not args.card.is_file():
        print(f"ERROR: card does not exist: {args.card}", file=sys.stderr)
        return 2

    text = args.card.read_text(encoding="utf-8")
    mode = args.mode
    errors = validate_text(
        text,
        args.card,
        mode,
        require_version_lead=args.require_version_lead,
        under_chars=args.under_chars,
    )
    if errors:
        print(f"{args.card}: validation failed", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    images = len(IMAGE_RE.findall(mask_fenced_code(text)))
    counted = len(countable_text(text))
    budget = f"{counted} counted" if mode == "simple" else f"{counted} teaching-body"
    print(f"{args.card}: OK ({mode}, {budget} characters, {images} visual(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
