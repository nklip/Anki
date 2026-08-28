from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "check_svg.py"
SPEC = importlib.util.spec_from_file_location("check_svg", SCRIPT_PATH)
assert SPEC and SPEC.loader
CHECK_SVG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECK_SVG
SPEC.loader.exec_module(CHECK_SVG)


def svg_with_label(text_y: float, transform: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="140" viewBox="0 0 200 140" role="img" aria-labelledby="title desc">
  <title id="title">Connector collision fixture</title>
  <desc id="desc">A rotated text label near a marker-ended connector.</desc>
  <!-- Reusable marker. -->
  <defs>
    <marker id="arrow" markerWidth="12" markerHeight="12" viewBox="0 0 12 12" refX="0" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 1L11 6L0 11Z"/></marker>
  </defs>
  <!-- Connector and label under test. -->
  <path d="M20 100H169" fill="none" stroke="#0b78b5" stroke-width="4" marker-end="url(#arrow)"/>
  <text x="100" y="{text_y}" text-anchor="middle" transform="{transform}" font-family="Arial, sans-serif" font-size="18">rotated label</text>
</svg>"""


def simple_svg(rect_x: int = 20, rect_width: int = 80) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Reference comparison fixture</title>
  <desc id="desc">A dark rectangle used to exercise raster comparison.</desc>
  <!-- Shared definitions. -->
  <defs/>
  <!-- Shape under test. -->
  <rect x="{rect_x}" y="20" width="{rect_width}" height="40" fill="#111111"/>
</svg>"""


def render_png(svg_path: Path, png_path: Path) -> None:
    runtime = CHECK_SVG.sharp_runtime()
    if runtime is None:
        raise unittest.SkipTest("Node.js with sharp is unavailable")
    node, environment = runtime
    process = subprocess.run(
        [
            node,
            "-e",
            "const sharp=require('sharp');sharp(process.argv[1]).png().toFile(process.argv[2]).catch(e=>{console.error(e);process.exit(1)})",
            str(svg_path),
            str(png_path),
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if process.returncode:
        raise AssertionError(process.stderr)


class CheckSvgTransformTests(unittest.TestCase):
    def report_for(self, source: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.svg"
            path.write_text(source, encoding="utf-8")
            return CHECK_SVG.check_file(path)

    def test_rotated_text_crossing_connector_is_reported(self) -> None:
        report = self.report_for(svg_with_label(104, "rotate(15 100 104)"))
        self.assertTrue(
            any("text/connector overlap" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_rotated_text_with_clearance_is_not_reported(self) -> None:
        report = self.report_for(svg_with_label(55, "rotate(15 100 55)"))
        self.assertFalse(
            any("text/connector overlap" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_parent_transform_is_applied_to_text_geometry(self) -> None:
        source = svg_with_label(54, "rotate(15 100 54)").replace(
            '<text x="100"',
            '<g transform="translate(0 50)"><text x="100"',
        ).replace("</text>\n</svg>", "</text></g>\n</svg>")
        report = self.report_for(source)
        self.assertTrue(
            any("text/connector overlap" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_diagonal_crossing_from_cdn_regression_is_reported(self) -> None:
        source = svg_with_label(55, "rotate(15 100 55)").replace(
            'd="M20 100H169"',
            'id="user-a-return" d="M435 181L157.64 108.06"',
        ).replace(
            'x="100" y="55" text-anchor="middle" transform="rotate(15 100 55)"',
            'x="351" y="197" text-anchor="middle" transform="rotate(-17.45 351 197)"',
        ).replace('viewBox="0 0 200 140"', 'viewBox="0 0 500 260"')
        report = self.report_for(source)
        self.assertTrue(
            any("user-a-return" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_symbol_use_without_dimensions_is_reported(self) -> None:
        source = svg_with_label(55, "rotate(15 100 55)").replace(
            "  </defs>",
            '    <symbol id="tile" viewBox="0 0 40 30"><rect width="40" height="30"/></symbol>\n  </defs>',
        ).replace(
            "  <!-- Connector and label under test. -->",
            '  <!-- Connector and label under test. -->\n  <use href="#tile" x="10" y="10"/>',
        )
        report = self.report_for(source)
        self.assertTrue(
            any("needs explicit width and height" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_symbol_use_with_dimensions_is_portable(self) -> None:
        source = svg_with_label(55, "rotate(15 100 55)").replace(
            "  </defs>",
            '    <symbol id="tile" viewBox="0 0 40 30"><rect width="40" height="30"/></symbol>\n  </defs>',
        ).replace(
            "  <!-- Connector and label under test. -->",
            '  <!-- Connector and label under test. -->\n  <use href="#tile" x="10" y="10" width="40" height="30"/>',
        )
        report = self.report_for(source)
        self.assertFalse(
            any("symbol #tile needs explicit" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_tspan_line_is_checked_against_labeled_manual_connector(self) -> None:
        source = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Tspan fixture</title>
  <desc id="desc">A second text line crossed by a manually headed connector shaft.</desc>
  <!-- Text under test. -->
  <text x="20" y="20" font-size="14"><tspan x="20">First</tspan><tspan x="20" dy="20">Second</tspan></text>
  <!-- Manual arrow shaft under test. -->
  <line id="flow-shaft" x1="0" y1="40" x2="110" y2="40" stroke="#000" stroke-width="2"/>
</svg>"""
        report = self.report_for(source)
        self.assertTrue(
            any("'Second'" in warning and "text/connector overlap" in warning for warning in report.warnings),
            report.warnings,
        )
        self.assertFalse(any("use <tspan>" in warning for warning in report.warnings), report.warnings)

    def test_transform_only_text_uses_default_origin_for_collision_check(self) -> None:
        source = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Transform-only text fixture</title>
  <desc id="desc">Text positioned only by a transform is crossed by a manually headed connector shaft.</desc>
  <!-- Transform-only label under test. -->
  <text transform="translate(20 40)" font-size="14">crossed label</text>
  <!-- Manual arrow shaft under test. -->
  <line id="flow-shaft" x1="0" y1="40" x2="115" y2="40" stroke="#000" stroke-width="2"/>
</svg>"""
        report = self.report_for(source)
        self.assertTrue(
            any("'crossed label'" in warning and "text/connector overlap" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_unparseable_single_line_text_position_is_reported(self) -> None:
        source = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Unparseable text position fixture</title>
  <desc id="desc">A single-line label has a position that cannot be estimated structurally.</desc>
  <!-- Label with an unsupported coordinate under test. -->
  <text x="calc(50%)" y="40" font-size="14">uncertain label</text>
</svg>"""
        report = self.report_for(source)
        self.assertTrue(
            any("single-line <text> element" in warning for warning in report.warnings),
            report.warnings,
        )

    def test_connector_hint_is_detected_inside_natural_identifiers(self) -> None:
        for identifier in ("mainArrow", "arrow2", "dataflow", "arrowline", "edgeArrowTop"):
            with self.subTest(identifier=identifier):
                source = f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Connector identifier fixture</title>
  <desc id="desc">A manual connector with a natural identifier crossing a text label.</desc>
  <!-- Label under test. -->
  <text x="20" y="44" font-size="14">crossed label</text>
  <!-- Manual connector under test. -->
  <line id="{identifier}" x1="0" y1="40" x2="115" y2="40" stroke="#000" stroke-width="2"/>
</svg>"""
                report = self.report_for(source)
                self.assertTrue(
                    any(
                        "text/connector overlap" in warning and f"<line#{identifier}>" in warning
                        for warning in report.warnings
                    ),
                    report.warnings,
                )

    def test_line_without_connector_hint_is_not_classified_as_connector(self) -> None:
        source = """<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80" role="img" aria-labelledby="title desc">
  <title id="title">Neutral line fixture</title>
  <desc id="desc">A line without a connector hint crossing a text label.</desc>
  <!-- Label under test. -->
  <text x="20" y="44" font-size="14">crossed label</text>
  <!-- Neutral guide under test. -->
  <line id="baselineGuide" x1="0" y1="40" x2="115" y2="40" stroke="#000" stroke-width="2"/>
</svg>"""
        report = self.report_for(source)
        self.assertFalse(any("text/connector overlap" in warning for warning in report.warnings), report.warnings)

    def test_embedded_raster_reference_is_rejected(self) -> None:
        source = simple_svg().replace(
            "  <!-- Shape under test. -->",
            '  <!-- Shape under test. -->\n  <image href="fixture.png" x="0" y="0" width="120" height="80"/>',
        )
        report = self.report_for(source)
        self.assertTrue(any("<image>" in error for error in report.errors), report.errors)


class CheckSvgReferenceTests(unittest.TestCase):
    def test_matching_same_stem_png_passes_reference_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            svg = root / "fixture.svg"
            png = root / "fixture.png"
            svg.write_text(simple_svg(), encoding="utf-8")
            render_png(svg, png)
            report = CHECK_SVG.check_file(
                svg,
                CHECK_SVG.CheckOptions(reference_mode="auto", compare_max_size=256),
            )
            self.assertTrue(report.reference_checked)
            self.assertEqual([], report.errors)
            self.assertEqual([], report.warnings)

    def test_correct_nonidentical_recreation_passes_default_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_source = root / "reference-source.svg"
            candidate = root / "fixture.svg"
            reference = root / "fixture.png"
            candidate_render = root / "candidate-render.png"
            reference_source.write_text(simple_svg(), encoding="utf-8")
            candidate.write_text(
                simple_svg().replace(
                    '<rect x="20" y="20" width="80" height="40" fill="#111111"/>',
                    '<path d="M21 20H101V60H21Z" fill="#151515"/>',
                ),
                encoding="utf-8",
            )
            render_png(reference_source, reference)
            render_png(candidate, candidate_render)
            self.assertNotEqual(reference.read_bytes(), candidate_render.read_bytes())

            report = CHECK_SVG.check_file(
                candidate,
                CHECK_SVG.CheckOptions(reference_mode="auto", compare_max_size=256),
            )
            self.assertTrue(report.reference_checked)
            self.assertEqual([], report.errors)
            self.assertEqual([], report.warnings)

    def test_scaled_viewbox_with_matching_root_size_has_no_dimension_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            svg = root / "fixture.svg"
            png = root / "fixture.png"
            source = simple_svg().replace(
                'width="120" height="80" viewBox="0 0 120 80"',
                'width="1400" height="980" viewBox="0 0 200 140"',
            )
            svg.write_text(source, encoding="utf-8")
            render_png(svg, png)
            report = CHECK_SVG.check_file(
                svg,
                CHECK_SVG.CheckOptions(reference_mode="auto", compare_max_size=256),
            )
            self.assertTrue(report.reference_checked)
            self.assertEqual([], report.errors)
            self.assertEqual([], report.warnings)

    def test_missing_and_displaced_content_fails_reference_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_source = root / "reference-source.svg"
            candidate = root / "fixture.svg"
            reference = root / "fixture.png"
            reference_source.write_text(simple_svg(), encoding="utf-8")
            candidate.write_text(simple_svg(rect_x=85, rect_width=35), encoding="utf-8")
            render_png(reference_source, reference)
            report = CHECK_SVG.check_file(
                candidate,
                CHECK_SVG.CheckOptions(reference_mode="auto", compare_max_size=256),
            )
            messages = [*report.errors, *report.warnings]
            self.assertTrue(report.reference_checked)
            self.assertTrue(any("reference ink recall" in message for message in messages), messages)
            self.assertTrue(any("reference ink precision" in message for message in messages), messages)

    def test_required_reference_reports_missing_png(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            svg = Path(directory) / "fixture.svg"
            svg.write_text(simple_svg(), encoding="utf-8")
            report = CHECK_SVG.check_file(svg, CHECK_SVG.CheckOptions(reference_mode="required"))
            self.assertTrue(any("no same-stem PNG reference" in error for error in report.errors), report.errors)

    def test_prohibited_raster_content_is_not_rendered_for_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_source = root / "reference-source.svg"
            candidate = root / "fixture.svg"
            reference = root / "fixture.png"
            reference_source.write_text(simple_svg(), encoding="utf-8")
            candidate.write_text(
                simple_svg().replace(
                    "  <!-- Shape under test. -->",
                    '  <!-- Shape under test. -->\n  <image href="fixture.png" x="0" y="0" width="120" height="80"/>',
                ),
                encoding="utf-8",
            )
            render_png(reference_source, reference)
            report = CHECK_SVG.check_file(candidate, CHECK_SVG.CheckOptions(reference_mode="auto"))
            self.assertFalse(report.reference_checked)
            self.assertTrue(any("<image>" in error for error in report.errors), report.errors)
            self.assertTrue(any("comparison skipped" in note for note in report.notes), report.notes)


if __name__ == "__main__":
    unittest.main()
