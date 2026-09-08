"""Regression tests for card structure, process visuals, and navigation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
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

    @staticmethod
    def mode_comment(mode: str) -> str:
        return f"<!-- Card mode: {mode}. Validate with --mode {mode}. -->"

    def card(self, body: str = "", mode: str = "complex") -> str:
        return (
            f"# A teaching topic\n\n{self.navigation}\n\n"
            f"{self.mode_comment(mode)}\n\n"
            "# Front\n\nWhat changes and why?\n\n"
            "# Back\n\nThe operation changes the stored state.\n\n"
            "![overview.svg](svg/overview.svg)\n\n"
            "![comparison.svg](svg/comparison.svg)\n\n"
            f"{body}\n\n# Sources\n\n"
            "- [Official reference](https://example.com/reference)\n"
        )

    def errors(self, text: str, mode: str = "complex", **options: bool) -> list[str]:
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

    def test_every_supported_step_depth_still_requires_a_diagram(self) -> None:
        for level in range(2, 7):
            with self.subTest(level=level):
                errors = self.errors(self.card(f"{'#' * level} Step 1 — Read\n\nRead the value."))
                self.assert_error(errors, "Step 1", "own local .svg")
                self.assertFalse(any("requires at least" in error for error in errors))
                if level != 2:
                    self.assert_error(errors, "Step 1", "##")

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
        content = f"{self.navigation}\n\n{self.mode_comment('simple')}"
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                errors = self.errors(self.card(example))
                self.assertFalse(any(
                    "navigation" in error or "card mode comment" in error or "header order" in error
                    for error in errors
                ), errors)

    def test_fenced_metadata_remains_in_countable_teaching_content(self) -> None:
        content = f"{self.navigation}\n\n{self.mode_comment('simple')}"
        for name, example in self.fenced_examples(content).items():
            with self.subTest(fence=name):
                counted = validator.countable_text(self.card(example))
                self.assertIn(self.navigation, counted)
                self.assertIn(self.mode_comment("simple"), counted)
                self.assertNotIn(self.mode_comment("complex"), counted)

    def test_fenced_metadata_cannot_supply_a_missing_navigation_link(self) -> None:
        for name, example in self.fenced_examples(self.navigation).items():
            with self.subTest(fence=name):
                text = self.card(example).replace(self.navigation + "\n\n", "", 1)
                errors = self.errors(text)
                self.assert_error(errors, "exactly one", "navigation")
                self.assertFalse(any("header order" in error for error in errors), errors)

    def test_fenced_metadata_cannot_supply_a_missing_mode_comment(self) -> None:
        comment = self.mode_comment("complex")
        for name, example in self.fenced_examples(comment).items():
            with self.subTest(fence=name):
                text = self.card(example).replace(comment + "\n\n", "", 1)
                self.assert_error(self.errors(text), "exactly one", "card mode comment")

    def test_header_order_diagnostic_survives_missing_or_legacy_front(self) -> None:
        for replacement in ("", "## Front"):
            with self.subTest(front=replacement):
                text = self.card().replace("# Front", replacement)
                text = text.replace(
                    f"{self.navigation}\n\n{self.mode_comment('complex')}",
                    f"{self.mode_comment('complex')}\n\n{self.navigation}",
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
