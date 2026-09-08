"""Regression tests for card structure, process visuals, and navigation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check_anki_card.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("check_anki_card", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class CardValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.card_path = self.root / "Subject" / "topic" / "card.md"
        image_directory = self.card_path.parent / "svg"
        image_directory.mkdir(parents=True)
        for filename in ("overview.svg", "comparison.svg", "step.svg"):
            (image_directory / filename).write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
            )
        self.index = self.root / "Subject" / "Readme.md"
        self.index.write_text("# Subject\n\n## Content\n", encoding="utf-8")
        self.navigation = "<sub>[Back to Subject](../Readme.md#content)</sub>"

    def card(self, body: str = "", mode: str = "complex") -> str:
        boundaries = (
            "# Front\n\nWhat changes and why?\n\n# Back\n\n"
            if mode == "simple" else ""
        )
        return (
            f"# A teaching topic\n\n{self.navigation}\n\n"
            f"{boundaries}The operation changes the stored state.\n\n"
            "![overview.svg](svg/overview.svg)\n\n"
            "![comparison.svg](svg/comparison.svg)\n\n"
            f"{body}\n\n# Sources\n\n"
            "- [Official reference](https://example.com/reference)\n"
        )

    def errors(self, text: str, mode: str = "auto", **options: bool) -> list[str]:
        return validator.validate_text(text, self.card_path, mode, **options)

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
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                self.assertEqual([], self.errors(self.card(mode=mode), mode))

    def test_auto_mode_accepts_both_structures_without_comments(self) -> None:
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                text = self.card(mode=mode)
                self.assertNotIn("<!--", text)
                self.assertEqual(mode, validator.detect_mode(text))
                self.assertEqual([], validator.validate_text(text, self.card_path))
                self.assertEqual([], self.errors(text, "auto"))

    def test_crlf_cards_preserve_structure_and_counted_sections(self) -> None:
        body = "## Explanation\n\n```markdown\n# Front\n\n## Back\n\n# Sources\n```"
        for mode in ("simple", "complex"):
            for heading_suffix in ("", " \t"):
                with self.subTest(mode=mode, heading_suffix=heading_suffix):
                    text = self.card(body, mode=mode).replace(
                        "The operation changes the stored state.",
                        "**State updates were introduced in Example Platform 1.0.**",
                    )
                    for heading in ("# Front", "# Back", "# Sources"):
                        text = text.replace(heading + "\n", heading + heading_suffix + "\n")
                    crlf = text.replace("\n", "\r\n")
                    self.assertEqual(mode, validator.detect_mode(crlf))
                    for selected_mode in ("auto", mode):
                        self.assertEqual([], self.errors(crlf, selected_mode, require_version_lead=True))
                    self.assertEqual(
                        validator.countable_text(text),
                        validator.countable_text(crlf).replace("\r\n", "\n"),
                    )

    def test_article_body_starts_after_navigation_without_card_boundaries(self) -> None:
        text = self.card()
        self.assertNotIn("# Front", text)
        self.assertNotIn("# Back", text)
        self.assertIn(self.navigation + "\n\nThe operation", text)
        self.assertEqual([], self.errors(text))

    def test_partial_boundary_pair_is_an_invalid_simple_card(self) -> None:
        for missing in ("# Front", "# Back"):
            with self.subTest(missing=missing):
                text = self.card(mode="simple").replace(missing + "\n", "", 1)
                self.assertEqual("simple", validator.detect_mode(text))
                self.assert_error(self.errors(text), "missing required heading", missing)

    def test_legacy_boundaries_select_simple_mode_but_still_require_migration(self) -> None:
        for front, back in (("##", "##"), ("##", "#"), ("#", "##"), ("##", ""), ("", "##")):
            for comment in ("", "<!-- Card mode: simple. Validate with --mode simple. -->"):
                with self.subTest(front=front, back=back, comment=comment):
                    text = self.card(comment, mode="simple").replace(
                        "![comparison.svg](svg/comparison.svg)\n\n", "", 1
                    )
                    for name, level in (("Front", front), ("Back", back)):
                        text = text.replace(f"# {name}\n", f"{level} {name}\n" if level else "", 1)
                    self.assertEqual("simple", validator.detect_mode(text))
                    errors = self.errors(text)
                    self.assertEqual(self.errors(text, "simple"), errors)
                    for name, level in (("Front", front), ("Back", back)):
                        if level != "#":
                            self.assert_error(errors, "missing required heading", f"# {name}")
                    self.assertFalse(any("local visual" in error for error in errors), errors)
                    crlf = text.replace("\n", "\r\n")
                    self.assertEqual("simple", validator.detect_mode(crlf))
                    self.assertEqual(errors, self.errors(crlf))

    def test_mode_detection_requires_exact_boundary_names_at_supported_levels(self) -> None:
        for heading in (
            "### Front", "### Back", "# Front details", "# Back details",
            "## Front details", "## Back details",
        ):
            with self.subTest(heading=heading):
                self.assertEqual("complex", validator.detect_mode(self.card(heading)))

    def test_fenced_boundary_examples_do_not_select_simple_mode(self) -> None:
        boundaries = "# Front\n\n# Back\n\n## Front\n\n## Back"
        for name, example in self.fenced_examples(boundaries).items():
            with self.subTest(fence=name):
                text = self.card(example)
                self.assertEqual("complex", validator.detect_mode(text))
                self.assertEqual([], self.errors(text))

    def test_explicit_mode_rejects_the_other_structure(self) -> None:
        errors = self.errors(self.card(), "simple")
        for heading in ("# Front", "# Back"):
            self.assert_error(errors, "missing required heading", heading)
        errors = self.errors(self.card(mode="simple"), "complex")
        for heading in ("# Front", "# Back"):
            self.assert_error(errors, "complex", heading)

    def test_mode_specific_visual_minimum_is_inferred(self) -> None:
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                text = self.card(mode=mode).replace(
                    "![comparison.svg](svg/comparison.svg)\n\n", "", 1
                )
                if mode == "simple":
                    self.assertEqual([], self.errors(text))
                else:
                    self.assert_error(self.errors(text), "requires at least 2", "found 1")

    def test_only_inferred_simple_mode_has_a_character_limit(self) -> None:
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                errors = self.errors(self.card("x" * 3001, mode=mode))
                if mode == "simple":
                    self.assert_error(errors, "allows at most 3000")
                else:
                    self.assertEqual([], errors)

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
                    self.assert_error(self.errors(self.card(comment, mode=mode)), "HTML comment")

    def test_comment_contents_cannot_select_mode_or_supply_structure(self) -> None:
        comment = "<!--\n# Front\n\n# Back\n\n## Front\n\n## Back\n-->"
        text = self.card(comment)
        self.assertEqual("complex", validator.detect_mode(text))
        errors = self.errors(text)
        self.assert_error(errors, "HTML comment")
        self.assertFalse(any("missing required heading" in error for error in errors), errors)

    def test_comments_cannot_supply_visuals_or_sources(self) -> None:
        images = "![overview.svg](svg/overview.svg)\n\n![comparison.svg](svg/comparison.svg)"
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
                    self.assertEqual([], self.errors(self.card(example, mode=mode)))

    def test_version_lead_is_required_at_the_start_of_each_mode_body(self) -> None:
        ordinary_lead = "The operation changes the stored state."
        version_lead = "**State updates were introduced in Example Platform 1.0.**"
        for mode in ("simple", "complex"):
            with self.subTest(mode=mode):
                text = self.card(mode=mode)
                versioned = text.replace(ordinary_lead, version_lead + "\n\n" + ordinary_lead)
                self.assertEqual([], self.errors(versioned, require_version_lead=True))
                self.assert_error(self.errors(text, require_version_lead=True), "standalone bold sentence")
                late_lead = text.replace(ordinary_lead, ordinary_lead + "\n\n" + version_lead)
                self.assert_error(self.errors(late_lead, require_version_lead=True), "standalone bold sentence")

    def test_cli_defaults_to_inferred_mode_and_accepts_explicit_auto(self) -> None:
        for mode in ("simple", "complex"):
            self.card_path.write_text(self.card(mode=mode), encoding="utf-8")
            for flags in ([], ["--mode", "auto"]):
                with self.subTest(mode=mode, flags=flags):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), *flags, str(self.card_path)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn(f"OK ({mode},", result.stdout)

    def test_cli_reports_partial_boundary_pair_as_invalid_simple(self) -> None:
        text = self.card(mode="simple").replace("# Back\n", "", 1)
        self.card_path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.card_path)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("missing required heading: # Back", result.stderr)

    def test_cli_routes_legacy_card_to_simple_migration_without_an_extra_visual(self) -> None:
        text = self.card(mode="simple").replace(
            "![comparison.svg](svg/comparison.svg)\n\n", "", 1
        )
        for heading in ("# Front", "# Back", "# Sources"):
            text = text.replace(heading, "#" + heading, 1)
        self.card_path.write_text(text, encoding="utf-8")
        for flags in ([], ["--mode", "auto"]):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), *flags, str(self.card_path)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(1, result.returncode)
                for heading in ("# Front", "# Back", "# Sources"):
                    self.assertIn(f"missing required heading: {heading}", result.stderr)
                self.assertNotIn("local visual", result.stderr)

    def test_every_supported_step_depth_still_requires_a_diagram(self) -> None:
        for level in range(2, 7):
            with self.subTest(level=level):
                errors = self.errors(self.card(f"{'#' * level} Step 1 — Read\n\nRead the value."))
                self.assert_error(errors, "Step 1", "own local .svg")
                self.assertFalse(any("requires at least" in error for error in errors))
                if level != 2:
                    self.assert_error(errors, "Step 1", "##")

    def test_crlf_step_diagnostics_and_section_boundaries_match_lf(self) -> None:
        for level in (2, 3):
            with self.subTest(level=level):
                text = self.card(
                    f"{'#' * level} Step 1 — Read\n\nRead the value.\n\n"
                    "## Example\n\n![step.svg](svg/step.svg)"
                )
                errors = self.errors(text)
                self.assert_error(errors, "Step 1", "own local .svg")
                self.assertEqual(errors, self.errors(text.replace("\n", "\r\n")))

    def test_legacy_step_with_a_diagram_still_reports_migration(self) -> None:
        for level in range(3, 7):
            with self.subTest(level=level):
                errors = self.errors(self.card(
                    f"{'#' * level} Step 1 — Read\n\n![step.svg](svg/step.svg)"
                ))
                self.assert_error(errors, "Step 1", "##")
                self.assertFalse(any("own local .svg" in error for error in errors))

    def test_migrated_steps_with_diagrams_pass(self) -> None:
        body = (
            "## Step 1 — Read\n\n![step.svg](svg/step.svg)\n\n"
            "### Detail\n\nObserve the value.\n\n"
            "## Step 2 — Write\n\n![step.svg](svg/step.svg)"
        )
        self.assertEqual([], self.errors(self.card(body)))

    def test_mixed_depth_steps_cannot_borrow_the_next_step_diagram(self) -> None:
        for first_level, second_level in ((2, 3), (3, 2), (3, 4), (4, 3)):
            with self.subTest(first_level=first_level, second_level=second_level):
                errors = self.errors(self.card(
                    f"{'#' * first_level} Step 1 — Read\n\nNo diagram here.\n\n"
                    f"{'#' * second_level} Step 2 — Write\n\n![step.svg](svg/step.svg)"
                ))
                self.assert_error(errors, "Step 1", "own local .svg")
                self.assertFalse(any("Step 2" in error and "own local .svg" in error for error in errors))

    def test_non_step_sibling_diagram_cannot_satisfy_previous_step(self) -> None:
        errors = self.errors(self.card(
            "## Step 1 — Read\n\nNo diagram here.\n\n"
            "## Comparison\n\n![step.svg](svg/step.svg)"
        ))
        self.assert_error(errors, "Step 1", "own local .svg")

    def test_steps_inside_fences_are_literal_examples(self) -> None:
        content = "\n\n".join(f"{'#' * level} Step {level} — Literal" for level in range(2, 7))
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                errors = self.errors(self.card(example))
                self.assertFalse(any("Step" in error for error in errors), errors)

    def test_fenced_diagram_cannot_satisfy_a_real_step(self) -> None:
        for name, example in self.fenced_examples("![step.svg](svg/step.svg)").items():
            with self.subTest(fence=name):
                errors = self.errors(self.card(f"## Step 1 — Read\n\n{example}"))
                self.assert_error(errors, "Step 1", "own local .svg")

    def test_fenced_images_do_not_satisfy_global_visual_minimum(self) -> None:
        images = "![overview.svg](svg/overview.svg)\n\n![comparison.svg](svg/comparison.svg)"
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

    def test_header_order_diagnostic_survives_missing_or_legacy_front(self) -> None:
        for replacement in ("", "## Front"):
            with self.subTest(front=replacement):
                text = self.card(mode="simple").replace("# Front", replacement)
                text = text.replace(
                    f"{self.navigation}\n\n",
                    f"Intervening prose\n\n{self.navigation}\n\n",
                )
                errors = self.errors(text)
                self.assert_error(errors, "missing required heading", "# Front")
                self.assert_error(errors, "header order")

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
            '<a id="custom-index"></a>\n\n<a name="legacy-index"></a>\n',
            encoding="utf-8",
        )
        for anchor in ("content", "content-1", "cache-and-store", "custom-index", "legacy-index", "%63ontent"):
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
