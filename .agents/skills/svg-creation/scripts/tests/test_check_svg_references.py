from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_check_svg import CHECK_SVG, svg_with_label


class CheckSvgReferenceTests(unittest.TestCase):
    def report_for(self, source: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.svg"
            path.write_text(source, encoding="utf-8")
            return CHECK_SVG.check_file(path)

    def with_reference(self, value: str, location: str) -> str:
        source = svg_with_label(55, "")
        attribute_value = value.replace('"', "&quot;")
        if location == "attribute":
            replacement = f'marker-end="{attribute_value}"'
        elif location == "inline":
            replacement = f'style="stroke:#0b78b5;marker-end:{attribute_value}"'
        else:
            replacement = 'class="edge"'
            source = source.replace("</defs>", f"</defs><style>.edge {{ marker-end: {value}; }}</style>")
        return source.replace('marker-end="url(#arrow)"', replacement)

    def test_missing_local_reference_is_rejected_in_attributes_inline_and_stylesheets(self) -> None:
        for location in ("attribute", "inline", "stylesheet"):
            for value in ("url(#missing)", "url('#missing')", 'url( "#missing" )'):
                with self.subTest(location=location, value=value):
                    report = self.report_for(self.with_reference(value, location))
                    self.assertIn("unresolved reference #missing", report.errors)

    def test_existing_local_reference_accepts_each_quoting_and_style_location(self) -> None:
        for location in ("attribute", "inline", "stylesheet"):
            for value in ("url(#arrow)", "url('#arrow')", 'URL( "#arrow" )'):
                with self.subTest(location=location, value=value):
                    report = self.report_for(self.with_reference(value, location))
                    self.assertEqual([], report.errors)
                    self.assertEqual([], report.warnings)

    def test_css_references_still_validate_marker_dimensions(self) -> None:
        for location in ("inline", "stylesheet"):
            with self.subTest(location=location):
                source = self.with_reference("url('#arrow')", location).replace(' markerWidth="12"', "")
                report = self.report_for(source)
                self.assertIn("marker #arrow should declare markerWidth", report.warnings)

    def test_css_marker_shorthand_is_validated(self) -> None:
        source = self.with_reference("url('#arrow')", "stylesheet").replace("marker-end:", "marker:")
        source = source.replace(' markerWidth="12"', "")
        report = self.report_for(source)
        self.assertIn("marker #arrow should declare markerWidth", report.warnings)

    def test_marker_reference_to_non_marker_element_is_rejected(self) -> None:
        for location in ("attribute", "inline", "stylesheet"):
            with self.subTest(location=location):
                source = self.with_reference("url('#title')", location)
                report = self.report_for(source)
                self.assertIn("marker reference #title does not target a <marker> element", report.errors)

    def test_css_comments_and_quoted_content_do_not_create_references(self) -> None:
        source = self.with_reference("url('#arrow')", "stylesheet").replace(
            ".edge {", "/* marker-start:url(#commented) */ .edge { content:'url(#literal)';"
        ).replace(
            'class="edge"', 'class="edge" style="/* marker-end:url(#inline-comment) */ stroke:#0b78b5"'
        )
        report = self.report_for(source)
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_non_marker_stylesheet_references_are_validated(self) -> None:
        source = self.with_reference("url(#arrow)", "stylesheet").replace(
            "marker-end: url(#arrow);", 'marker-end:url(#arrow); filter:url("#missing-filter");'
        )
        report = self.report_for(source)
        self.assertIn("unresolved reference #missing-filter", report.errors)

    def test_quoted_css_marker_is_checked_for_text_collisions(self) -> None:
        for location in ("attribute", "inline", "stylesheet"):
            with self.subTest(location=location):
                source = self.with_reference("url('#arrow')", location).replace('y="55"', 'y="104"')
                report = self.report_for(source)
                self.assertTrue(any("text/connector overlap" in warning for warning in report.warnings))

    def test_url_extraction_decodes_css_escapes_and_ignores_external_targets(self) -> None:
        value = r'''url(#\61 rrow) URL("#arrow") url('#arrow') url(other.svg#external) "url(#literal)"'''
        self.assertEqual({"arrow"}, CHECK_SVG.local_url_references(value))

    def test_inline_declarations_preserve_semicolons_inside_quoted_urls(self) -> None:
        self.assertEqual(
            {"stroke": "black", "marker-end": 'url("#arrow;variant")', "fill": "none"},
            CHECK_SVG.parse_style_attribute('stroke:black;marker-end:url("#arrow;variant");fill:none'),
        )

    def test_quoted_url_punctuation_does_not_split_stylesheet_rules(self) -> None:
        source = self.with_reference('url("#arrow{variant};")', "stylesheet")
        source = source.replace('id="arrow"', 'id="arrow{variant};"').replace(' markerWidth="12"', "")
        report = self.report_for(source)
        self.assertEqual([], report.errors)
        self.assertIn("marker #arrow{variant}; should declare markerWidth", report.warnings)


if __name__ == "__main__":
    unittest.main()
