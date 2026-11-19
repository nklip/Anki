"""Regression tests for card structure, process visuals, and navigation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent, indent
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check_anki_card.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("check_anki_card", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


ARTICLE_CONTENTS = (
    "1. [Stored state](#1-stored-state)\n"
    "2. [What survives?](#2-what-survives)\n"
    "3. [Check your understanding](#3-check-your-understanding)"
)
ARTICLE_SECTIONS = (
    "## 1. **Stored `state`**\n\nThe old value is zero.\n\n"
    "### A second update\n\nAn update changes it to one.\n\n"
    "## 2. What survives?\n\nA saved update survives a restart."
)
ARTICLE_REVIEW = "## 3. Check your understanding"
FIRST_ITEM = (
    "1. Predict the value after an update.\n\n"
    "   <details>\n   <summary>Answer</summary>\n\n"
    "   The value changes to one.\n\n   </details>"
)
SECOND_ITEM = (
    "2. What value will you see after restarting?\n\n"
    "   <details>\n   <summary>Answer</summary>\n\n"
    "   The saved value is one.\n\n   </details>"
)


class CardValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.card_path = self.root / "Subject" / "topic" / "card.md"
        image_directory = self.card_path.parent / "images"
        image_directory.mkdir(parents=True)
        for filename in ("overview.svg", "comparison.svg", "step.svg"):
            (image_directory / filename).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
            )
        self.index = self.root / "Subject" / "Readme.md"
        self.index.write_text("# Subject\n\n## Content\n", encoding="utf-8")
        self.navigation = "<sub>[Back to Subject](../Readme.md#content)</sub>"

    def simple_card(self, body: str = "") -> str:
        return (
            f"# A teaching topic\n\n{self.navigation}\n\n"
            "The operation changes the stored state.\n\n"
            "![overview.svg](images/overview.svg)\n\n"
            "![comparison.svg](images/comparison.svg)\n\n"
            f"{body}\n\n# Sources\n\n"
            "- [Official reference](https://example.com/reference)\n"
        )

    @staticmethod
    def review_item(number: int, title: str) -> str:
        indent = " " * len(f"{number}. ")
        return (
            f"{number}. Explain {title.lower()} in your own words.\n\n"
            f"{indent}<details>\n{indent}<summary>Answer</summary>\n\n"
            f"{indent}The update changes the stored value.\n\n{indent}</details>"
        )

    def card(self, body: str = "") -> str:
        """Supply an article outline for tests exercising other validator rules."""
        lines = body.split("\n")
        visible = validator.mask_comments(validator.mask_fenced_code(body))
        sections = []
        for index, line in enumerate(visible.splitlines()):
            heading = validator.HEADING_RE.fullmatch(line)
            if heading and heading[1] == "##":
                title = validator.heading_label(heading)
                if title not in {"Front", "Back", "Sources"}:
                    sections.append((index, title))
        if not sections:
            sections.append((len(lines) + 1, "Stored state"))
            lines.extend(["", "## Stored state", "", "The new value replaces the old one."])
        review = "\n\n".join(self.review_item(i, title) for i, (_, title) in enumerate(sections, 1))
        sections.append((len(lines) + 1, "Check your understanding"))
        lines.extend(["", "## Check your understanding", "", review])
        contents = []
        for number, (index, title) in enumerate(sections, 1):
            lines[index] = f"## {number}. {title}"
            anchor, = validator.markdown_anchors(lines[index])
            contents.append(f"{number}. [{title}](#{anchor})")
        return self.simple_card("\n".join(contents + [""] + lines))

    def errors(self, text: str, mode: str = "complex", **options: bool) -> list[str]:
        return validator.validate_text(text, self.card_path, mode, **options)

    def article_example(self) -> str:
        return self.simple_card("\n\n".join((
            ARTICLE_CONTENTS, ARTICLE_SECTIONS, ARTICLE_REVIEW, FIRST_ITEM, SECOND_ITEM,
        )))

    def assert_error(self, errors: list[str], *parts: str) -> None:
        self.assertTrue(
            any(all(part.lower() in error.lower() for part in parts) for error in errors),
            f"Expected an error containing {parts!r}; got {errors!r}",
        )

    @staticmethod
    def fenced_examples(content: str) -> dict[str, str]:
        return {
            "backticks": f"```markdown\n{content}\n```",
            "tildes": f"~~~markdown\n{content}\n~~~",
            "indented backticks": f"   ```markdown\n{content}\n   ```",
            "indented tildes": f"   ~~~markdown\n{content}\n   ~~~",
            "long fence with shorter inner fence": (
                f"````markdown\n```text\n{content}\n```\n````"
            ),
        }

    def test_valid_simple_and_complex_cards(self) -> None:
        self.assertEqual([], self.errors(self.simple_card(), "simple"))
        self.assertEqual([], self.errors(self.card(), "complex"))

    def test_article_counts_main_sections_and_accepts_more_prompts_than_sections(self) -> None:
        article = self.article_example()
        extra = self.review_item(3, "when to save the new value")
        for text in (article, article.replace(SECOND_ITEM, SECOND_ITEM + "\n\n" + extra)):
            self.assertEqual([], self.errors(text))
            self.assertEqual([], self.errors(text.replace("\n", "\r\n")))

    def test_article_rules_leave_simple_mode_optional(self) -> None:
        text = self.simple_card("## Stored state\n\nAn update replaces the old value.")
        self.assertEqual([], self.errors(text, "simple"))
        self.assertTrue(self.errors(text, "complex"))

    def test_two_digit_prompt_aligns_the_answer_under_its_text(self) -> None:
        first_nine = [FIRST_ITEM, SECOND_ITEM] + [
            self.review_item(i, "when an update is saved") for i in range(3, 10)
        ]
        last = (
            "10. Describe the recovery.\n\n"
            "    <details>\n    <summary>Answer</summary>\n\n"
            "    The saved value survives.\n\n    </details>"
        )
        article = self.article_example().replace(
            FIRST_ITEM + "\n\n" + SECOND_ITEM, "\n\n".join([*first_nine, last])
        )
        self.assertEqual([], self.errors(article))
        self.assertTrue(self.errors(article.replace(last, last.replace("\n    ", "\n   "))))

    def test_article_headings_are_numbered_consecutively_from_one(self) -> None:
        article = self.article_example()
        for original, replacement in (
            ("## 1. ", "## "), ("## 1. ", "## 0. "),
            ("## 2. ", "## 1. "), ("## 2. ", "## 4. "),
            ("## 3. ", "## 4. "),
        ):
            with self.subTest(original=original, replacement=replacement):
                self.assertTrue(self.errors(article.replace(original, replacement)))

    def test_article_requires_the_final_check_your_understanding_section(self) -> None:
        article = self.article_example()
        renamed = article.replace("Check your understanding", "Summary").replace(
            "check-your-understanding", "summary"
        )
        after_review = article.replace(
            ARTICLE_CONTENTS, ARTICLE_CONTENTS + "\n4. [Appendix](#4-appendix)"
        ).replace("# Sources", "## 4. Appendix\n\nA further example.\n\n# Sources")
        for text in (renamed, after_review):
            self.assertTrue(self.errors(text))

    def test_article_contents_links_match_sections_in_order(self) -> None:
        article = self.article_example()
        first, second, review = ARTICLE_CONTENTS.splitlines()
        variants = {
            "absent": "",
            "unordered": "\n".join("- " + line[3:] for line in (first, second, review)),
            "skipped number": ARTICLE_CONTENTS.replace("2. [", "4. ["),
            "order": "\n".join((second.replace("2. ", "1. "), first.replace("1. ", "2. "), review)),
            "missing review": first + "\n" + second,
            "wrong label": ARTICLE_CONTENTS.replace("[Stored state]", "[Recovery]"),
            "unnumbered fragment": ARTICLE_CONTENTS.replace("#1-stored-state", "#stored-state"),
            "different local heading": ARTICLE_CONTENTS.replace("#1-stored-state", "#2-what-survives"),
            "fenced example": "```markdown\n" + ARTICLE_CONTENTS + "\n```",
        }
        for name, contents in variants.items():
            with self.subTest(name=name):
                self.assertTrue(self.errors(article.replace(ARTICLE_CONTENTS, contents)))
        in_section = article.replace(ARTICLE_CONTENTS, "").replace(
            "The old value is zero.", "The old value is zero.\n\n" + ARTICLE_CONTENTS
        )
        self.assertTrue(self.errors(in_section))

    def test_only_top_level_review_prompts_count_toward_coverage(self) -> None:
        article = self.article_example()
        nested = indent(SECOND_ITEM, "   ")
        variants = {
            "no second prompt": FIRST_ITEM,
            "nested list": FIRST_ITEM + "\n\n" + nested,
            "inside an answer": FIRST_ITEM.replace("   </details>", nested + "\n\n   </details>"),
            "blockquote": FIRST_ITEM + "\n\n" + indent(SECOND_ITEM, "> "),
            "fenced list": FIRST_ITEM + "\n\n~~~markdown\n" + SECOND_ITEM + "\n~~~",
        }
        for name, review in variants.items():
            with self.subTest(name=name):
                text = article.replace(FIRST_ITEM + "\n\n" + SECOND_ITEM, review)
                self.assertTrue(self.errors(text))
        outside_review = article.replace(SECOND_ITEM, "").replace(
            "The old value is zero.", SECOND_ITEM + "\n\nThe old value is zero."
        )
        self.assertTrue(self.errors(outside_review))

    def test_each_visible_review_prompt_has_its_own_closed_expandable_answer(self) -> None:
        article = self.article_example()
        prompt, answer = SECOND_ITEM.split("\n\n", 1)
        variants = {
            "missing answer": prompt,
            "plain answer": prompt + "\n\n   The saved value is one.",
            "wrong label": SECOND_ITEM.replace(">Answer<", ">Solution<"),
            "expanded answer": SECOND_ITEM.replace("<details>", "<details open>"),
            "unclosed answer": SECOND_ITEM.replace("   </details>", ""),
            "unindented answer": prompt + "\n\n" + dedent(answer),
            "fenced answer": prompt + "\n\n   ```html\n" + answer + "\n   ```",
        }
        for name, replacement in variants.items():
            with self.subTest(name=name):
                self.assertTrue(self.errors(article.replace(SECOND_ITEM, replacement)))
        shared_answer = FIRST_ITEM.split("\n\n", 1)[0] + "\n\n" + SECOND_ITEM
        self.assertTrue(self.errors(article.replace(FIRST_ITEM + "\n\n" + SECOND_ITEM, shared_answer)))

    def test_bold_sub_items_within_subsections_are_allowed(self) -> None:
        for mode in ("simple", "complex"):
            for marker in ("**", "__"):
                for suffix in ("", " ####"):
                    with self.subTest(mode=mode, marker=marker, suffix=suffix):
                        body = (
                            "## Behavior\n\n### Retry handling\n\n"
                            f"#### {marker}Use case: Retrying an update{marker}{suffix}\n\n"
                            "Repeat the update after a failure.\n\n"
                            "#### **Use case: Resuming after restart**\n\nResume the work."
                        )
                        text = self.card(body)
                        self.assertEqual([], self.errors(text, mode))
                        self.assertEqual([], self.errors(text.replace("\n", "\r\n"), mode))

    def test_named_sub_items_need_no_prefix_and_may_include_inline_code(self) -> None:
        for mode in ("simple", "complex"):
            for label in (
                "**Web Servers**", "**Pull model**", "**Service Failure**",
                "**Scale the `bucket` table**", "**Use `__init__` in the ctor**",
                "**Use `**init**` in the ctor**", "__Use `__init__` in the ctor__",
                "**Use ``a ` ** b`` in the example**",
            ):
                with self.subTest(mode=mode, label=label):
                    body = f"## Behavior\n\n### Details\n\n#### {label}"
                    self.assertEqual([], self.errors(self.card(body), mode))

    def test_level_four_requires_fully_bold_text(self) -> None:
        for mode in ("simple", "complex"):
            for label in (
                "Use case: Retrying an update", "*Use case: Retrying an update*",
                "**Use case:** Retrying an update", "**Use case: Retrying an update__",
                "** **", "****", "** leading space**", "**trailing space **",
                "**Use case:** plain **x**", "**A** and **B**", "**a**b**c**",
                "__Use case:__ plain __x__", "__A__ and __B__", "__a__b__c__",
                "**A** `plain` **B**", "`**Literal bold markers**`",
            ):
                with self.subTest(mode=mode, label=label):
                    body = f"## Behavior\n\n### Retry handling\n\n#### {label}"
                    self.assert_error(self.errors(self.card(body), mode), "fully bold")

    def test_heading_diagnostics_omit_closing_atx_sequences(self) -> None:
        for heading in (
            "#### Plain label", "#### **Orphaned sub-item**", "##### **Deep sub-item**",
            "#### Step 3 — Publish", "#### **Step 3 — Publish**",
        ):
            with self.subTest(heading=heading):
                errors = self.errors(self.card(heading))
                self.assertTrue(errors)
                self.assertEqual(errors, self.errors(self.card(heading + " ####")))

    def test_level_four_requires_a_current_subsection(self) -> None:
        for mode in ("simple", "complex"):
            for prefix in (
                "", "## Behavior", "### Previous detail\n\n## New section",
                "### Previous detail\n\n# New section",
                "```markdown\n### Literal subsection\n```",
            ):
                with self.subTest(mode=mode, prefix=prefix):
                    body = prefix + "\n\n#### **Use case: Retrying an update**"
                    self.assert_error(
                        self.errors(self.card(body), mode), "nested within a ### subsection"
                    )

    def test_levels_five_and_six_remain_invalid(self) -> None:
        for mode in ("simple", "complex"):
            for level in (5, 6):
                with self.subTest(mode=mode, level=level):
                    body = (
                        "## Behavior\n\n### Retry handling\n\n"
                        f"{'#' * level} **Use case: Retrying an update**"
                    )
                    self.assert_error(self.errors(self.card(body), mode), "too deep")

    def test_fenced_heading_examples_do_not_affect_use_case_nesting(self) -> None:
        for mode in ("simple", "complex"):
            for name, example in self.fenced_examples(
                "## Literal section\n#### Unbolded example\n###### Deep example"
            ).items():
                with self.subTest(mode=mode, fence=name):
                    body = (
                        f"## Behavior\n\n### Retry handling\n\n{example}\n\n"
                        "#### **Use case: Retrying an update**"
                    )
                    self.assertEqual([], self.errors(self.card(body), mode))

    def test_explicit_mode_is_required_by_the_api(self) -> None:
        with self.assertRaises(TypeError):
            validator.validate_text(self.card(), self.card_path)
        for mode in ("auto", "", "article"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validator.validate_text(self.card(), self.card_path, mode)

    def test_shared_structure_passes_both_explicit_modes(self) -> None:
        text = self.card()
        self.assertNotIn("<!--", text)
        self.assertNotIn("# Front", text)
        self.assertNotIn("# Back", text)
        self.assertIn(self.navigation + "\n\nThe operation", text)
        for mode in ("simple", "complex"):
            self.assertEqual([], self.errors(text, mode))

    def test_crlf_cards_preserve_structure_and_body_budget(self) -> None:
        body = "## Explanation\n\n```markdown\n# Front\n\n## Back\n\n# Sources\n```"
        for mode in ("simple", "complex"):
            for suffix in ("", " \t"):
                with self.subTest(mode=mode, suffix=suffix):
                    text = self.card(body).replace(
                        "The operation changes the stored state.",
                        "**State updates were introduced in Example Platform 1.0.**",
                    ).replace("# Sources\n", "# Sources" + suffix + "\n")
                    crlf = text.replace("\n", "\r\n")
                    self.assertEqual([], self.errors(crlf, mode, require_version_lead=True))
                    self.assertEqual(validator.countable_text(text), validator.countable_text(crlf))

    def test_legacy_boundaries_are_rejected_in_both_modes(self) -> None:
        for mode in ("simple", "complex"):
            for heading in ("# Front", "# Back", "## Front", "## Back"):
                for suffix in ("", " \t", " ##"):
                    with self.subTest(mode=mode, heading=heading, suffix=suffix):
                        text = self.card(heading + suffix)
                        errors = self.errors(text, mode)
                        self.assert_error(errors, "boundary", heading, "not allowed")
                        self.assertEqual(1, sum("boundary" in error for error in errors), errors)
                        self.assertEqual(errors, self.errors(text.replace("\n", "\r\n"), mode))

    def test_legacy_boundary_rule_requires_exact_names_at_supported_levels(self) -> None:
        for mode in ("simple", "complex"):
            for heading in ("### Front", "### Back", "# Front details", "# Back details",
                            "## Front details", "## Back details"):
                with self.subTest(mode=mode, heading=heading):
                    self.assertEqual([], self.errors(self.card(heading), mode))

    def test_fenced_legacy_boundaries_are_literal_examples(self) -> None:
        boundaries = "# Front\n\n# Back\n\n## Front\n\n## Back"
        for mode in ("simple", "complex"):
            for name, example in self.fenced_examples(boundaries).items():
                with self.subTest(mode=mode, fence=name):
                    self.assertEqual([], self.errors(self.card(example), mode))

    def test_sources_requires_a_real_final_level_one_section(self) -> None:
        for mode in ("simple", "complex"):
            for replacement in ("", "# Sources details", "```markdown\n# Sources\n```"):
                with self.subTest(mode=mode, replacement=replacement):
                    text = self.card().replace("# Sources", replacement)
                    self.assert_error(self.errors(text, mode), "missing required heading", "# Sources")
            wrong_level = self.card().replace("# Sources", "## Sources")
            self.assert_error(self.errors(wrong_level, mode), "## Sources", "must use '# Sources'")
            self.assert_error(self.errors(self.card() + "\n# Sources\n", mode), "exactly one", "Sources")
            self.assert_error(self.errors(self.card() + "\n# Appendix\n", mode), "Sources", "final level-one")

    def test_source_links_outside_sources_do_not_supply_the_required_citation(self) -> None:
        source = "- [Official reference](https://example.com/reference)"
        text = self.card(source).replace("# Sources\n\n" + source, "# Sources\n")
        for mode in ("simple", "complex"):
            self.assert_error(self.errors(text, mode), "Sources", "HTTP(S)")

    def test_visual_minimum_uses_the_explicit_mode(self) -> None:
        text = self.card().replace("![comparison.svg](images/comparison.svg)\n\n", "", 1)
        self.assertEqual([], self.errors(text, "simple"))
        self.assert_error(self.errors(text, "complex"), "requires at least 2", "found 1")

    def test_only_simple_mode_has_a_default_character_limit(self) -> None:
        text = self.card("x" * (validator.SIMPLE_CHARACTER_LIMIT + 1))
        self.assert_error(self.errors(text, "simple"), f"allows at most {validator.SIMPLE_CHARACTER_LIMIT}")
        self.assertEqual([], self.errors(text, "complex"))

    def test_simple_budget_counts_unicode_body_characters_at_the_exact_limit(self) -> None:
        base = self.card("PAD")
        padding = validator.SIMPLE_CHARACTER_LIMIT - len(validator.countable_text(base)) + len("PAD")
        for character in ("x", "界", "🧠"):
            for newline in ("\n", "\r\n"):
                with self.subTest(character=character, newline=repr(newline)):
                    text = base.replace("PAD", character * padding).replace("\n", newline)
                    self.assertEqual(3500, len(validator.countable_text(text)))
                    self.assertEqual([], self.errors(text, "simple"))
                    too_long = text.replace(character * padding, character * (padding + 1))
                    self.assert_error(self.errors(too_long, "simple"), "teaching body", "found 3501")

    def test_title_navigation_and_final_sources_do_not_consume_the_body_budget(self) -> None:
        text = self.card()
        enlarged = text.replace("# A teaching topic", "# " + "t" * 5000)
        enlarged = enlarged.replace(self.navigation, self.navigation.replace("Subject", "n" * 5000))
        enlarged += "\n" + "s" * 5000
        self.assertEqual(validator.countable_text(text), validator.countable_text(enlarged))
        self.assertEqual([], self.errors(enlarged, "simple"))

    def test_all_body_markdown_counts_including_fenced_boundary_lookalikes(self) -> None:
        literal = (
            "## Example\n\n```markdown\n# Front\n# Back\n# Sources\n"
            + self.navigation + "\n![step.svg](images/step.svg)\n```"
        )
        text = self.simple_card(literal)
        expected = (
            "The operation changes the stored state.\n\n"
            "![overview.svg](images/overview.svg)\n\n"
            "![comparison.svg](images/comparison.svg)\n\n" + literal
        )
        self.assertEqual(expected, validator.countable_text(text))
        oversized = text.replace("# Front\n", "# Front\n" + "x" * 3500 + "\n")
        self.assert_error(self.errors(oversized, "simple"), "allows at most")

    def test_nonfinal_sources_and_legacy_front_do_not_hide_body_characters(self) -> None:
        for heading in ("# Sources", "# Front"):
            with self.subTest(heading=heading):
                body = heading + "\n\n" + "x" * 3500 + "\n\n# Explanation"
                text = self.card(body)
                self.assertIn(body, validator.countable_text(text))
                self.assert_error(self.errors(text, "simple"), "allows at most")

    def test_comment_boundaries_cannot_shorten_the_body_budget(self) -> None:
        body = "<!--\n# Sources\n-->\n\n" + "x" * 3500
        text = self.card(body)
        self.assertIn(body, validator.countable_text(text))
        errors = self.errors(text, "simple")
        self.assert_error(errors, "HTML comments")
        self.assert_error(errors, "allows at most")

    def test_comments_are_rejected_in_either_mode(self) -> None:
        for mode in ("simple", "complex"):
            for comment in (
                "<!-- Card mode: complex. Validate with --mode complex. -->",
                "<!-- An editorial note -->",
                "<!--\nA multiline note\n-->",
                "An inline <!-- hidden --> note.",
                "<!-- An unclosed note",
            ):
                with self.subTest(mode=mode, comment=comment):
                    self.assert_error(self.errors(self.card(comment), mode), "HTML comment")

    def test_comments_cannot_supply_legacy_boundaries(self) -> None:
        comment = "<!--\n# Front\n\n# Back\n\n## Front\n\n## Back\n-->"
        text = self.card(comment)
        errors = self.errors(text)
        self.assert_error(errors, "HTML comment")
        self.assertFalse(any("is not allowed" in error for error in errors), errors)

    def test_comments_cannot_supply_visuals_or_sources(self) -> None:
        images = "![overview.svg](images/overview.svg)\n\n![comparison.svg](images/comparison.svg)"
        source = "- [Official reference](https://example.com/reference)"
        text = self.card().replace(images, f"<!--\n{images}\n-->")
        text = text.replace(source, f"<!--\n{source}\n-->")
        errors = self.errors(text)
        self.assert_error(errors, "HTML comment")
        self.assert_error(errors, "requires at least 2", "found 0")
        self.assert_error(errors, "Sources", "HTTP(S)")

    def test_fenced_comments_are_allowed_literal_examples(self) -> None:
        for mode in ("simple", "complex"):
            for name, example in self.fenced_examples("<!-- A literal comment -->").items():
                with self.subTest(mode=mode, fence=name):
                    self.assertEqual([], self.errors(self.card(example), mode))

    def test_authoring_boilerplate_is_rejected_in_both_modes(self) -> None:
        examples = {
            "fact/source verification": (
                "Facts checked against AWS documentation on 17 November 2026.",
                "The claims were fact-checked against the official docs.",
                "Primary sources checked on 2026-09-17; examples use the documented rules.",
                "Official AWS documentation and resources, checked September 18, 2026:",
                "Official documentation consulted on September 16, 2026.",
                "Original article sources checked on 2026-09-17.",
                "**Verification date:** 2026-11-17.",
                "Last verified: November 17, 2026.",
                "Accessed on 17 November 2026.",
                "This September 2026 snapshot was verified on September 17, 2026.",
            ),
            "local-note migration history": (
                "Migrated and rewritten from “AWS IAM” in the local “AWS (sorting)” deck "
                "(note ID `1644236779110`).",
                "This article was rewritten from the local Anki note about scaling.",
                "Migrated from the Anki deck named AWS.",
                "- Original study note: **Java (sorting) → wait()**, including its images.",
                "Source record: local Anki note ID `1470247887577`.",
            ),
            "diagram production/provenance": (
                "Both SVGs are newly drawn, editable vectors.",
                "Their layouts and labels are newly drawn.",
                "The layouts were redrawn for this card.",
                "The four local diagrams are original teaching illustrations.",
                "- Diagram icon provenance: reused editable server geometry.",
                "## Diagram provenance",
                "Diagram provenance and adaptations are identified below.",
            ),
        }
        for mode in ("simple", "complex"):
            for reason, snippets in examples.items():
                for snippet in snippets:
                    with self.subTest(mode=mode, snippet=snippet):
                        errors = self.errors(self.card(snippet), mode)
                        self.assert_error(errors, "authoring boilerplate", reason, "line ")

    def test_boilerplate_normalization_preserves_wrapped_text_and_line_numbers(self) -> None:
        snippets = (
            "**Facts** checked against\n[AWS documentation](https://example.com/docs) "
            "on 17 November 2026.",
            "- **Original study note:**\n  Java concurrency.",
            "<em>Primary sources</em> checked\non 2026-09-17.",
            "The SVGs are **newly\ndrawn**, editable vectors.",
            "- Local Anki **note ID**\n  `1470247887577`.",
        )
        for snippet in snippets:
            for mode in ("simple", "complex"):
                with self.subTest(mode=mode, snippet=snippet):
                    text = self.card("Earlier teaching prose.\n\n" + snippet)
                    line = text[:text.index(snippet)].count("\n") + 1
                    errors = self.errors(text, mode)
                    self.assertEqual(1, len(errors), errors)
                    self.assert_error(errors, f"line {line}:", "authoring boilerplate")
                    self.assertEqual(errors, self.errors(text.replace("\n", "\r\n"), mode))

    def test_boilerplate_in_sources_is_also_rejected(self) -> None:
        for mode in ("simple", "complex"):
            for suffix in (
                "\nPrimary sources checked on 2026-09-17.\n",
                " (accessed on 2026-11-17)",
                " — accessed: November 17, 2026",
            ):
                with self.subTest(mode=mode, suffix=suffix):
                    text = self.card().rstrip() + suffix + "\n"
                    self.assert_error(self.errors(text, mode), "authoring boilerplate", "verification")

    def test_boilerplate_rules_do_not_join_separate_paragraphs(self) -> None:
        for separator in ("\n\n", "\n \n", "\r\n\r\n", "\r\n \r\n"):
            with self.subTest(separator=repr(separator)):
                text = self.card("Facts" + separator + "checked against AWS documentation.")
                self.assertEqual([], self.errors(text))

    def test_fenced_boilerplate_remains_a_literal_example(self) -> None:
        snippets = (
            "Facts checked against AWS documentation on 17 November 2026.\n"
            "Migrated from the local AWS deck.\n"
            "Local Anki note ID `1470247887577`.\n"
            "Both SVGs are newly drawn."
        )
        for mode in ("simple", "complex"):
            for name, example in self.fenced_examples(snippets).items():
                with self.subTest(mode=mode, fence=name):
                    self.assertEqual([], self.errors(self.card(example), mode))

    def test_teaching_facts_checks_examples_and_attribution_remain_valid(self) -> None:
        snippets = (
            "**The feature became final in JDK 25 with JEP 512.**",
            "The release date was September 16, 2025. This article covers Java SE 26.",
            "The database was migrated from a local server to a managed cluster.",
            "Sources are checked at runtime before the request is accepted.",
            "Claims are verified using the issuer's public key.",
            "Facts are checked against database constraints at runtime.",
            "The runtime checks arguments against the method's declared types.",
            "This diagram illustrates the article's example.",
            "The diagram provenance system records transformations of input data.",
            "The CPU values and four-instance result are an explicitly hypothetical example.",
            "Illustration adapted from Jane Doe, licensed under CC BY 4.0.",
            "- [Original diagram — Jane Doe, CC BY 4.0](https://example.com/diagram)",
            "- [Java SE 26 API documentation](https://example.com/docs)",
            "- [Release notes, November 17, 2026](https://example.com/release)",
            "- [Source](https://example.com/Facts%20checked%20against%20documentation)",
        )
        for mode in ("simple", "complex"):
            for snippet in snippets:
                with self.subTest(mode=mode, snippet=snippet):
                    self.assertEqual([], self.errors(self.card(snippet), mode))

    def test_version_lead_is_required_at_the_start_of_each_mode_body(self) -> None:
        ordinary_lead = "The operation changes the stored state."
        version_lead = "**State updates were introduced in Example Platform 1.0.**"
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                text = self.card()
                versioned = text.replace(ordinary_lead, version_lead + "\n\n" + ordinary_lead)
                self.assertEqual([], self.errors(versioned, mode, require_version_lead=True))
                self.assert_error(self.errors(text, mode, require_version_lead=True), "standalone bold sentence")
                late_lead = text.replace(ordinary_lead, ordinary_lead + "\n\n" + version_lead)
                self.assert_error(self.errors(late_lead, mode, require_version_lead=True), "standalone bold sentence")

    def test_cli_accepts_both_explicit_modes(self) -> None:
        self.card_path.write_text(self.card(), encoding="utf-8")
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--mode", mode, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(f"OK ({mode},", result.stdout)

    def test_cli_article_character_limit_and_uncapped_report(self) -> None:
        article = self.article_example()
        body = article.split(self.navigation + "\n\n", 1)[1].rsplit("\n\n# Sources", 1)[0]
        # Size the complete Markdown body by extending an answer in the review.
        answer = "The saved value is one."
        for count, limit, expected_status in (
            (4_999, "5K", 0),
            (5_000, "5K", 1),
            (9_999, "10000", 0),
            (9_999, "10K", 0),
            (10_000, "10k", 1),
            (10_001, "10000", 1),
            (14_999, "15k", 0),
            (15_000, "15k", 1),
            (50_001, None, 0),
        ):
            with self.subTest(count=count, limit=limit):
                text = article.replace(answer, answer + "界" * (count - len(body)))
                self.card_path.write_text(text, encoding="utf-8")
                flags = ["--under-chars", limit] if limit else []
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--mode", "complex", *flags, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(expected_status, result.returncode, result.stderr)
                if expected_status == 0:
                    self.assertIn(f"{count} teaching-body characters", result.stdout)
                else:
                    self.assertIn(str(count), result.stderr)

    def test_cli_looser_requested_limit_preserves_simple_cap(self) -> None:
        self.card_path.write_text(self.simple_card("x" * 3500), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--mode", "simple", "--under-chars", "10k", str(self.card_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("allows at most 3500", result.stderr)

    def test_cli_rejects_malformed_character_limits(self) -> None:
        self.card_path.write_text(self.article_example(), encoding="utf-8")
        for limit in ("0", "-1", "1.5k", "10kb"):
            with self.subTest(limit=limit):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--mode", "complex", "--under-chars", limit, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(2, result.returncode, result.stderr)
                self.assertIn("--under-chars", result.stderr)

    def test_cli_requires_mode_and_rejects_auto(self) -> None:
        self.card_path.write_text(self.card(), encoding="utf-8")
        for flags in ([], ["--mode", "auto"]):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *flags, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(2, result.returncode)
                self.assertIn("--mode", result.stderr)
                self.assertNotIn("OK (", result.stdout)

    def test_cli_self_test_needs_no_mode_or_card_path(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--self-test"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Self-test passed", result.stdout)

    def test_cli_reports_legacy_boundaries_for_both_modes(self) -> None:
        self.card_path.write_text(self.card("# Front\n\n# Back"), encoding="utf-8")
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--mode", mode, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(1, result.returncode)
                self.assertIn("boundary '# Front' is not allowed", result.stderr)
                self.assertIn("boundary '# Back' is not allowed", result.stderr)

    def test_every_recognized_step_depth_still_requires_a_diagram(self) -> None:
        for level in range(2, 7):
            for marker in ("", "**", "__"):
                with self.subTest(level=level, marker=marker):
                    body = (
                        "## Behavior\n\n### Details\n\n"
                        f"{'#' * level} {marker}Step 1 — Read{marker}\n\nRead the value."
                    )
                    text = self.card(body)
                    errors = self.errors(text)
                    self.assert_error(errors, "Step 1", "own local .svg")
                    self.assertFalse(any("requires at least" in error for error in errors))
                    if level > 3:
                        self.assert_error(errors, "Step 1", "must use", "##")
                    self.assertEqual(1 if level <= 3 else 2, len(errors), errors)
                    self.assertEqual(errors, self.errors(text.replace("\n", "\r\n")))

    def test_crlf_step_diagnostics_and_section_boundaries_match_lf(self) -> None:
        for level in (2, 3):
            with self.subTest(level=level):
                text = self.card(
                    "## Process\n\n"
                    f"{'#' * level} Step 1 — Read\n\nRead the value.\n\n"
                    "## Example\n\n![step.svg](images/step.svg)"
                )
                errors = self.errors(text)
                self.assert_error(errors, "Step 1", "own local .svg")
                self.assertEqual(1, len(errors), errors)
                self.assertEqual(errors, self.errors(text.replace("\n", "\r\n")))

    def test_step_with_a_diagram_still_reports_incorrect_level(self) -> None:
        for level in range(4, 7):
            for marker in ("", "**", "__"):
                with self.subTest(level=level, marker=marker):
                    errors = self.errors(self.card(
                        "## Process\n\n### Details\n\n"
                        f"{'#' * level} {marker}Step 1 — Read{marker}\n\n"
                        "![step.svg](images/step.svg)"
                    ))
                    self.assert_error(errors, "Step 1", "must use", "##")
                    self.assertEqual(1, len(errors), errors)

    def test_level_two_steps_with_diagrams_pass(self) -> None:
        body = (
            "## Step 1 — Read\n\n![step.svg](images/step.svg)\n\n"
            "### Detail\n\nObserve the value.\n\n"
            "## Step 2 — Write\n\n![step.svg](images/step.svg)"
        )
        for marker in ("", "**", "__"):
            with self.subTest(marker=marker):
                formatted = body.replace("Step 1 — Read", f"{marker}Step 1 — Read{marker}")
                formatted = formatted.replace("Step 2 — Write", f"{marker}Step 2 — Write{marker}")
                text = self.card(formatted)
                self.assertEqual([], self.errors(text))
                self.assertEqual([], self.errors(text.replace("\n", "\r\n")))

    def test_level_three_steps_within_level_two_sections_pass(self) -> None:
        body = (
            "## Recovery process\n\n### Overview\n\nRead before writing.\n\n"
            "### Step 1 — Read\n\n![step.svg](images/step.svg)\n\n"
            "#### **Detail**\n\nObserve the value.\n\n"
            "### Step 2 — Write\n\n![step.svg](images/step.svg)\n\n"
            "## Retry process\n\n### Step 1 — Read\n\n![step.svg](images/step.svg)"
        )
        for marker in ("", "**", "__"):
            with self.subTest(marker=marker):
                formatted = body.replace("Step 1 — Read", f"{marker}Step 1 — Read{marker}")
                formatted = formatted.replace("Step 2 — Write", f"{marker}Step 2 — Write{marker}")
                text = self.card(formatted)
                self.assertEqual([], self.errors(text))
                self.assertEqual([], self.errors(text.replace("\n", "\r\n")))

    def test_level_three_steps_require_a_current_level_two_section(self) -> None:
        prefixes = {
            "no parent": "",
            "level-one parent": "# New chapter\n\n",
            "level-one reset": "## Previous process\n\n# New chapter\n\n",
        }
        prefixes.update({
            f"fenced parent: {name}": example + "\n\n"
            for name, example in self.fenced_examples("## Literal process").items()
        })
        for name, prefix in prefixes.items():
            for marker in ("", "**", "__"):
                with self.subTest(parent=name, marker=marker):
                    text = self.card(
                        prefix + f"### {marker}Step 1 — Read{marker}\n\n"
                        "![step.svg](images/step.svg)"
                    )
                    errors = self.errors(text)
                    self.assert_error(errors, "Step 1", "##", "section")
                    self.assertEqual(1, len(errors), errors)
                    self.assertEqual(errors, self.errors(text.replace("\n", "\r\n")))

    def test_mixed_depth_steps_cannot_borrow_the_next_step_diagram(self) -> None:
        for first_level, second_level in ((2, 2), (2, 3), (3, 2), (3, 3), (3, 4), (4, 3)):
            for first_marker, second_marker in (("", ""), ("", "**"), ("**", "__"), ("__", "")):
                with self.subTest(levels=(first_level, second_level), markers=(first_marker, second_marker)):
                    errors = self.errors(self.card(
                        "## Process\n\n"
                        f"{'#' * first_level} {first_marker}Step 1 — Read{first_marker}\n\n"
                        "No diagram here.\n\n"
                        f"{'#' * second_level} {second_marker}Step 2 — Write{second_marker}\n\n"
                        "![step.svg](images/step.svg)"
                    ))
                    self.assert_error(errors, "Step 1", "own local .svg")
                    self.assertFalse(any("Step 2" in error and "own local .svg" in error for error in errors))

    def test_non_step_peer_or_parent_diagram_cannot_satisfy_previous_step(self) -> None:
        for step_level in (2, 3):
            for following_level in range(1, step_level + 1):
                with self.subTest(step_level=step_level, following_level=following_level):
                    text = self.card(
                        "## Process\n\n"
                        f"{'#' * step_level} Step 1 — Read\n\nNo diagram here.\n\n"
                        f"{'#' * following_level} Comparison\n\n![step.svg](images/step.svg)"
                    )
                    errors = self.errors(text)
                    self.assert_error(errors, "Step 1", "own local .svg")
                    self.assertEqual(1, len(errors), errors)
                    self.assertEqual(errors, self.errors(text.replace("\n", "\r\n")))

    def test_steps_inside_fences_are_literal_examples(self) -> None:
        content = "\n\n".join(
            f"{'#' * level} {marker}Step {level} — Literal{marker}"
            for level in range(2, 7) for marker in ("", "**", "__")
        )
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                errors = self.errors(self.card(example))
                self.assertFalse(any("Step" in error for error in errors), errors)

    def test_fenced_diagram_cannot_satisfy_a_real_step(self) -> None:
        for level in (2, 3):
            for name, example in self.fenced_examples("![step.svg](images/step.svg)").items():
                with self.subTest(level=level, fence=name):
                    errors = self.errors(self.card(
                        f"## Process\n\n{'#' * level} Step 1 — Read\n\n{example}"
                    ))
                    self.assert_error(errors, "Step 1", "own local .svg")
                    self.assertEqual(1, len(errors), errors)

    def test_fenced_images_do_not_satisfy_global_visual_minimum(self) -> None:
        images = "![overview.svg](images/overview.svg)\n\n![comparison.svg](images/comparison.svg)"
        for name, example in self.fenced_examples(images).items():
            with self.subTest(fence=name):
                text = self.card(example).replace(images + "\n\n", "", 1)
                self.assert_error(self.errors(text), "requires at least 2", "found 0")

    def test_fenced_metadata_does_not_duplicate_real_header_metadata(self) -> None:
        content = f"{self.navigation}\n\n<!-- A literal comment -->"
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                errors = self.errors(self.card(example))
                self.assertEqual([], errors)

    def test_fenced_metadata_remains_in_countable_teaching_content(self) -> None:
        comment = "<!-- A literal comment -->"
        content = f"{self.navigation}\n\n{comment}"
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                counted = validator.countable_text(self.card(example))
                self.assertIn(self.navigation, counted)
                self.assertIn(comment, counted)

    def test_fenced_metadata_cannot_supply_a_missing_navigation_link(self) -> None:
        for name, example in self.fenced_examples(self.navigation).items():
            with self.subTest(fence=name):
                text = self.card(example).replace(self.navigation + "\n\n", "", 1)
                errors = self.errors(text)
                self.assert_error(errors, "exactly one", "navigation")
                self.assertFalse(any("header order" in error for error in errors), errors)

    def test_header_order_requires_navigation_immediately_after_title(self) -> None:
        for mode in ("simple", "complex"):
            for intervening in ("Intervening prose", "## Topic"):
                with self.subTest(mode=mode, intervening=intervening):
                    text = self.card().replace(self.navigation, intervening + "\n\n" + self.navigation)
                    self.assert_error(self.errors(text, mode), "header order")

    def test_header_requires_blank_lines_and_nonempty_teaching_body(self) -> None:
        for mode in ("simple", "complex"):
            for text in (
                self.card().replace("# A teaching topic\n\n", "# A teaching topic\n"),
                self.card().replace(self.navigation + "\n\n", self.navigation + "\n"),
                "# A teaching topic\n\n" + self.navigation + "\n\n# Sources\n\n"
                "- [Official reference](https://example.com/reference)\n",
            ):
                with self.subTest(mode=mode, text=text):
                    self.assert_error(self.errors(text, mode), "header order")

    def test_missing_readme_diagnostic_excludes_fragment(self) -> None:
        self.index.unlink()
        errors = self.errors(self.card())
        self.assert_error(errors, "navigation README does not exist", "../Readme.md")
        diagnostic = next(error for error in errors if "navigation README does not exist" in error)
        self.assertNotIn("#content", diagnostic)

    def test_navigation_requires_exact_readme_filename_case(self) -> None:
        for spelling in ("README.md", "readme.md", "ReadMe.md"):
            with self.subTest(spelling=spelling):
                errors = self.errors(self.card().replace("../Readme.md", f"../{spelling}"))
                self.assertTrue(any(
                    "navigation" in error.lower()
                    and ("case" in error.lower() or "Readme.md" in error)
                    for error in errors
                ), errors)

    def test_navigation_accepts_actual_root_uppercase_readme(self) -> None:
        (self.root / "README.md").write_text("# Anki Flashcards\n", encoding="utf-8")
        text = self.card().replace(self.navigation, "<sub>[Back to Anki Flashcards](../../README.md)</sub>")
        self.assertEqual([], self.errors(text))

    def test_navigation_rejects_wrong_ancestor_directory_case(self) -> None:
        correct = self.card().replace("../Readme.md", "../../Subject/Readme.md")
        self.assertEqual([], self.errors(correct))
        wrong_case = correct.replace("../../Subject/Readme.md", "../../subject/Readme.md")
        self.assert_error(self.errors(wrong_case), "navigation")
        # The lexical check must also catch directory spelling hidden by '..'
        # normalization before checking the final README's existence.
        intermediate = self.card().replace("../Readme.md", "../TOPIC/../Readme.md")
        self.assert_error(self.errors(intermediate), "navigation", "case", "topic")

    def test_navigation_accepts_existing_heading_and_explicit_anchors(self) -> None:
        self.index.write_text(
            "# Subject\n\n## Content\n\n## Content\n\n"
            "## **Cache** and `Store`\n\n"
            '<a id="custom-index"></a>\n\n<a name="named-index"></a>\n',
            encoding="utf-8",
        )
        for anchor in ("content", "content-1", "cache-and-store", "custom-index", "named-index", "%63ontent"):
            with self.subTest(anchor=anchor):
                self.assertEqual([], self.errors(self.card().replace("#content)", f"#{anchor})")))

    def test_navigation_rejects_absent_and_case_mismatched_anchors(self) -> None:
        for anchor in ("missing", "Content", "content-1"):
            with self.subTest(anchor=anchor):
                errors = self.errors(self.card().replace("#content)", f"#{anchor})"))
                self.assert_error(errors, "navigation", "anchor", anchor)

    def test_fenced_readme_heading_does_not_create_an_anchor(self) -> None:
        self.index.write_text("# Subject\n\n```markdown\n## Content\n```\n", encoding="utf-8")
        self.assert_error(self.errors(self.card()), "navigation", "anchor", "content")

    def test_navigation_without_fragment_needs_no_content_heading(self) -> None:
        self.index.write_text("# Subject\n", encoding="utf-8")
        self.assertEqual([], self.errors(self.card().replace("#content)", ")")))

    def test_no_local_file_checks_skips_navigation_case_and_anchor_resolution(self) -> None:
        self.index.unlink()
        text = self.card().replace("../Readme.md#content", "../README.md#missing")
        self.assertEqual([], self.errors(text, check_local_files=False))


if __name__ == "__main__":
    unittest.main()
