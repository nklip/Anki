"""Regression tests for local README fragment validation."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from markdown_anchors import markdown_anchors


class MarkdownAnchorsTests(unittest.TestCase):
    def test_atx_headings_and_duplicates(self) -> None:
        text = "# Content\n## Content\n### Content-1\n#### Content\n"
        self.assertEqual(markdown_anchors(text), {"content", "content-1", "content-1-1", "content-2"})

    def test_formatting_links_code_and_entities(self) -> None:
        text = "## **The** _Content_ for [`foo_bar`](https://example.com/x(y)) &amp; <em>More</em>\n"
        self.assertEqual(markdown_anchors(text), {"the-content-for-foo_bar--more"})

    def test_literal_underscores_and_punctuation(self) -> None:
        text = "## use_foo and `__bar__` with \\_escaped\\_!\n"
        self.assertEqual(markdown_anchors(text), {"use_foo-and-__bar__-with-_escaped_"})

    def test_inline_code_contains_literal_html(self) -> None:
        text = "## Literal `<!--` and ` value `\n\n## Next\n"
        self.assertEqual(markdown_anchors(text), {"literal----and-value", "next"})

    def test_github_documented_unicode_example(self) -> None:
        text = "## This'll be a _Helpful_ Section About the Greek Letter Θ!\n"
        self.assertIn("thisll-be-a-helpful-section-about-the-greek-letter-Θ", markdown_anchors(text))

    def test_setext_and_closing_hashes(self) -> None:
        text = "Main title\n==========\n\nMultiple\nlines\n-----\n\n   ## Content ###\n"
        self.assertEqual(markdown_anchors(text), {"main-title", "multiple-lines", "content"})

    def test_custom_anchors_do_not_consume_suffixes(self) -> None:
        text = '<a name="content"></a>\n<a id=Custom></a>\n<div id="other&amp;value"></div>\n# Content\n'
        self.assertEqual(markdown_anchors(text), {"content", "Custom", "other&value"})

    def test_fenced_examples_do_not_produce_anchors(self) -> None:
        text = ('````markdown\n# Hidden\n```\n<a name="hidden-custom"></a>\n````\n'
                '~~~text\n## Also hidden\n~~~\n# Visible\n')
        self.assertEqual(markdown_anchors(text), {"visible"})

    def test_unclosed_fence_hides_to_end(self) -> None:
        self.assertEqual(markdown_anchors("# Visible\n```markdown\n# Hidden\n"), {"visible"})

    def test_comments_and_literal_html_are_not_anchors(self) -> None:
        text = ('<!--\n# Hidden `code`\n<a name="hidden"></a>\n-->\n'
                '`<a name="inline"></a>`\n'
                '    <a name="indented"></a>\n'
                '<pre><a name="pre"></a></pre>\n'
                '\\<a name="escaped"></a>\n'
                '## Real `<a name="code">`\n')
        self.assertEqual(markdown_anchors(text), {"real-a-namecode"})

    def test_non_headings_do_not_produce_anchors(self) -> None:
        text = "####### too deep\n#nospace\n    ## Indented\n\n---\n- list item\n---\n"
        self.assertEqual(markdown_anchors(text), set())


if __name__ == "__main__":
    unittest.main()
