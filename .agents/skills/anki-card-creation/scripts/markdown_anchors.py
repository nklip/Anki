"""Extract the GitHub-style anchors used by ordinary repository README files.

This deliberately bounded, dependency-free parser handles standalone ATX and
Setext headings, common inline formatting, and explicit HTML id/name anchors.
It is not a complete GFM renderer: headings inside lists/block quotes, raw HTML
headings, and extension-generated content need review in GitHub's rendered view.

Rules: https://docs.github.com/en/get-started/writing-on-github/
getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax
"""

from __future__ import annotations

from html.parser import HTMLParser
import re
import unicodedata

from markdown_fences import mask_fenced_code


ATX_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*?)|[ \t]*)$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
CODE_SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.*?)\1(?!`)", re.DOTALL)
HTML_LITERAL_RE = re.compile(
    r"(?P<inline>(?<!`)(?P<ticks>`+)(?!`).*?(?P=ticks)(?!`))|"
    r"<!--.*?(?:-->|$)|<(?P<tag>pre|code)\b[^>]*>.*?</(?P=tag)\s*>",
    re.DOTALL | re.IGNORECASE,
)
BLOCK_START_RE = re.compile(
    r"^ {0,3}(?:>|[-+*][ \t]+|\d+[.)][ \t]+|<|\[[^\]]+\]:|"
    r"(?:\*[ \t]*){3,}$|(?:_[ \t]*){3,}$)"
)


def _blank(match: re.Match[str]) -> str:
    return "".join("\n" if character == "\n" else " " for character in match.group())


def _mask_html_literals(text: str) -> str:
    """Hide comments and raw code without interpreting inline-code contents."""
    return HTML_LITERAL_RE.sub(
        lambda match: match.group() if match.group("inline") else _blank(match), text
    )


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.anchors: set[str] = set()

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if value and (key == "id" or (tag == "a" and key == "name")):
                self.anchors.add(value)


def _plain_heading(text: str) -> str:
    """Get the visible text for ordinary heading inline syntax."""
    # Protect code and escaped punctuation before stripping HTML/Markdown.
    literals: list[str] = []

    def literal(value: str) -> str:
        literals.append(value)
        return f"\ue000{len(literals) - 1}\ue001"

    def code_literal(match: re.Match[str]) -> str:
        value = match.group(2).replace("\n", " ")
        if value.startswith(" ") and value.endswith(" ") and value.strip():
            value = value[1:-1]
        return literal(value)

    text = CODE_SPAN_RE.sub(code_literal, text)
    text = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])",
                  lambda match: literal(match.group(1)), text)
    # HTML heading text excludes images' alt attributes, as does Markdown here.
    text = re.sub(r"!\[[^\]]*\](?:\([^\n]*?\)|\[[^\]]*\])", "", text)
    # Include link labels, not destinations; allow balanced parentheses in URLs.
    text = re.sub(r"\[([^\]]+)\]\((?:[^()\n]|\([^()\n]*\))*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    # Intraword underscores are literal; paired emphasis delimiters are markup.
    text = re.sub(r"(?<!\w)(_+)(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", text)
    text = text.replace("*", "").replace("~~", "")
    parser = _HTMLText()
    parser.feed(text)
    visible = "".join(parser.text)
    return re.sub(r"\ue000(\d+)\ue001", lambda match: literals[int(match.group(1))], visible)


def _slug(text: str) -> str:
    # GitHub's documented example preserves non-ASCII uppercase letters (Θ).
    # Word characters include combining marks and connector punctuation.
    text = text.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
    return "".join(
        "-" if character == " " else character
        for character in text.strip()
        if character in " -" or unicodedata.category(character)[0] in "LMN"
        or unicodedata.category(character) == "Pc"
    )


def markdown_anchors(text: str) -> set[str]:
    """Return decoded, case-sensitive fragment names in a local README.

    Explicit HTML anchors do not consume generated heading suffixes. Fenced and
    indented code, HTML comments, and inline code cannot create HTML anchors.
    """
    visible = mask_fenced_code(text)
    visible = _mask_html_literals(visible)
    visible = re.sub(r"^(?: {4}|\t)[^\n]*", _blank, visible, flags=re.MULTILINE)

    explicit = _HTMLText()
    html_text = CODE_SPAN_RE.sub(_blank, visible)
    html_text = re.sub(r"\\<", "&lt;", html_text)
    explicit.feed(html_text)
    anchors = explicit.anchors
    generated: set[str] = set()
    paragraph: list[str] = []

    def add_heading(heading: str) -> None:
        base = _slug(_plain_heading(heading))
        candidate = base
        suffix = 0
        while candidate in generated:
            suffix += 1
            candidate = f"{base}-{suffix}"
        generated.add(candidate)
        anchors.add(candidate)

    for line in visible.splitlines():
        heading = ATX_RE.match(line)
        if heading:
            content = heading.group(1) or ""
            content = re.sub(r"[ \t]+#+[ \t]*$", "", content)
            add_heading(content.strip())
            paragraph = []
        elif SETEXT_RE.match(line) and paragraph:
            add_heading(" ".join(paragraph))
            paragraph = []
        elif not line.strip() or BLOCK_START_RE.match(line) or SETEXT_RE.match(line):
            paragraph = []
        else:
            paragraph.append(line.strip())
    return anchors
