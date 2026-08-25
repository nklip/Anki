from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
