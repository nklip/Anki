from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test_check_svg import CHECK_SVG


def diagram(contents: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="240" height="220"
      viewBox="0 0 240 220" role="img" aria-labelledby="title desc">
      <title id="title">Geometry regression</title>
      <desc id="desc">Labels near a connector exercise the rendered geometry.</desc>
      <!-- Shared definitions. --><defs/>
      <!-- Geometry under test. -->{contents}</svg>'''


class SvgGeometryTests(unittest.TestCase):
    def report_for(self, contents: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.svg"
            path.write_text(diagram(contents), encoding="utf-8")
            return CHECK_SVG.check_file(path)

    def collisions(self, contents: str) -> list[str]:
        report = self.report_for(contents)
        self.assertEqual([], report.errors)
        return [message for message in report.warnings if "text/connector overlap" in message]

    def arc_fixture(self, path: str, x: int = 90, y: int = 25) -> str:
        return f'''<path id="connector" d="{path}" fill="none" stroke="black"/>
          <text x="{x}" y="{y}" font-size="14">Hit</text>'''

    def test_arc_crossing_label_is_reported_once(self) -> None:
        messages = self.collisions(self.arc_fixture("M20 100 A80 80 0 0 1 180 100"))
        self.assertEqual(1, len(messages), messages)

    def test_label_on_arc_chord_has_clearance(self) -> None:
        self.assertEqual([], self.collisions(self.arc_fixture("M20 100 A80 80 0 0 1 180 100", y=100)))

    def test_arc_sweep_selects_the_other_semicircle(self) -> None:
        path = "M20 100 A80 80 0 0 0 180 100"
        self.assertEqual([], self.collisions(self.arc_fixture(path)))
        self.assertTrue(self.collisions(self.arc_fixture(path, y=185)))

    def test_relative_arc_and_compact_flags_render_the_same_curve(self) -> None:
        for path in ("M20 100 a80 80 0 0 1 160 0", "M20 100 A80 80 0 01180 100"):
            with self.subTest(path=path):
                self.assertTrue(self.collisions(self.arc_fixture(path)))
                self.assertEqual([], self.collisions(self.arc_fixture(path, y=100)))

    def test_small_and_negative_radii_receive_svg_radius_correction(self) -> None:
        for path in ("M20 100 A20 20 0 0 1 180 100", "M20 100 A-80 -80 0 0 1 180 100"):
            with self.subTest(path=path):
                self.assertTrue(self.collisions(self.arc_fixture(path)))

    def test_large_arc_visits_the_opposite_side_of_the_ellipse(self) -> None:
        self.assertTrue(self.collisions(self.arc_fixture("M180 100 A80 80 0 1 0 100 180")))
        self.assertEqual([], self.collisions(self.arc_fixture("M180 100 A80 80 0 0 0 100 180")))

    def test_rotated_ellipse_uses_both_radii(self) -> None:
        path = "M100 20 A80 40 90 0 1 100 180"
        self.assertTrue(self.collisions(self.arc_fixture(path, x=134, y=105)))
        self.assertEqual([], self.collisions(self.arc_fixture(path, x=90, y=105)))

    def test_degenerate_arcs_follow_svg_line_and_empty_rules(self) -> None:
        self.assertTrue(self.collisions(self.arc_fixture("M20 100 A0 80 0 0 1 180 100", y=100)))
        self.assertEqual([], self.collisions(self.arc_fixture("M90 20 A80 80 0 1 1 90 20")))

    def test_transformed_arc_collisions_follow_the_transformed_curve(self) -> None:
        self.assertTrue(self.collisions('''<g transform="translate(10 10) scale(.5)">
          <path id="connector" d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="black"/>
          </g><text x="55" y="25" font-size="14">Hit</text>'''))

    def test_parent_text_and_tail_are_checked_around_a_tspan(self) -> None:
        for label, connector_x in (("Prefix", 15), ("Tail", 173)):
            with self.subTest(label=label):
                messages = self.collisions(f'''<text x="10" y="100" font-size="14">Prefix<tspan x="130">Span</tspan>Tail</text>
                  <line id="connector" x1="{connector_x}" y1="60" x2="{connector_x}" y2="120" stroke="black"/>''')
                self.assertTrue(any(label in message for message in messages), messages)

    def test_explicit_x_span_advances_the_next_inline_span(self) -> None:
        report = self.report_for('''<text x="20" y="100" font-size="14"><tspan x="20">First</tspan><tspan>Second</tspan></text>''')
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_nested_spans_preserve_parent_and_tail_styles(self) -> None:
        messages = self.collisions('''<text x="10" y="100" font-size="14">A<tspan x="60" font-size="24">B<tspan x="100">Nested</tspan>Tail</tspan></text>
          <line id="connector" x1="188" y1="85" x2="188" y2="95" stroke="black"/>''')
        self.assertTrue(any("Tail" in message for message in messages), messages)

    def test_anchor_applies_to_the_complete_mixed_text_chunk(self) -> None:
        for anchor in ("middle", "end"):
            with self.subTest(anchor=anchor):
                contents = f'''<text x="120" y="100" font-size="14" text-anchor="{anchor}">Left<tspan>Right</tspan>Tail</text>'''
                report = self.report_for(contents)
                self.assertEqual([], report.errors)
                self.assertEqual([], report.warnings)
                # All glyphs end at/before x=120 for end, or well before x=170
                # for middle. Anchoring each run independently extends farther.
                edge = 170 if anchor == "middle" else 124
                messages = self.collisions(contents + f'''<line id="connector" x1="{edge}" y1="90" x2="{edge}" y2="110" stroke="black"/>''')
                self.assertEqual([], messages)

    def test_explicit_x_creates_separate_centered_lines(self) -> None:
        report = self.report_for('''<text x="120" y="80" font-size="14" text-anchor="middle">
          <tspan x="120">First line</tspan>
          <tspan x="120" dy="2em">Second line</tspan>
          </text>''')
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_y_only_span_continues_from_the_anchored_cursor(self) -> None:
        # The second line inherits the first line's painted ending position.
        # Checking the unanchored cursor misses these actual intersections.
        for anchor, connector_x in (("end", 105), ("middle", 150)):
            with self.subTest(anchor=anchor):
                messages = self.collisions(f'''<text x="150" y="80" font-size="20" text-anchor="{anchor}"><tspan x="150">First</tspan><tspan y="120">Second</tspan></text>
                  <line id="connector" x1="{connector_x}" y1="103" x2="{connector_x}" y2="121" stroke="black"/>''')
                self.assertTrue(any("'Second' with" in message for message in messages), messages)

    def test_y_only_span_does_not_extend_to_the_unanchored_cursor(self) -> None:
        for anchor, connector_x in (("end", 175), ("middle", 225)):
            with self.subTest(anchor=anchor):
                messages = self.collisions(f'''<text x="150" y="80" font-size="20" text-anchor="{anchor}"><tspan x="150">First</tspan><tspan y="120">Second</tspan></text>
                  <line id="connector" x1="{connector_x}" y1="103" x2="{connector_x}" y2="121" stroke="black"/>''')
                self.assertEqual([], messages)

    def test_descriptive_elements_do_not_create_phantom_collisions(self) -> None:
        for tag in ("title", "desc", "metadata"):
            with self.subTest(tag=tag):
                messages = self.collisions(f'''<text x="20" y="80" font-size="20"><{tag}>Long descriptive label</{tag}><tspan>Visible</tspan></text>
                  <line id="connector" x1="150" y1="60" x2="150" y2="85" stroke="black"/>''')
                self.assertEqual([], messages)

    def test_skipping_descriptions_preserves_visible_nested_text_and_tails(self) -> None:
        # Consecutive visible letters must retain their positions across ignored
        # descriptions, nested spans, links, and each element's following text.
        contents = '''<text x="20" y="100" font-size="40"><title>Hidden title</title>A<tspan>B<desc>Hidden description</desc>C<tspan>D</tspan>E</tspan><metadata><record>Hidden metadata</record></metadata>F<a>G</a>H</text>'''
        for label, connector_x in zip("ABCDEFGH", (31, 53, 76, 98, 121, 143, 165, 188)):
            with self.subTest(label=label):
                messages = self.collisions(contents + f'''<line id="connector" x1="{connector_x}" y1="70" x2="{connector_x}" y2="105" stroke="black"/>''')
                self.assertTrue(any(f"'{label}' with" in message for message in messages), messages)

    def test_inline_whitespace_remains_between_words(self) -> None:
        # A narrow line is in the space between the actual glyph estimates.
        # Collapsing each run with strip() would move B onto the connector.
        messages = self.collisions('''<text x="20" y="100" font-size="40">A <tspan>B</tspan></text>
          <line id="connector" x1="49" y1="80" x2="49" y2="110" stroke="black"/>''')
        self.assertEqual([], messages)

    def test_default_origin_and_relative_offsets_apply_to_nested_text(self) -> None:
        messages = self.collisions('''<text transform="translate(20 80)" font-size="14"><tspan dx="2em" dy="1em">Hit</tspan></text>
          <line id="connector" x1="50" y1="80" x2="50" y2="110" stroke="black"/>''')
        self.assertTrue(any("Hit" in message for message in messages), messages)

    def test_unsupported_span_positions_warn_instead_of_using_a_prefix(self) -> None:
        for position in ("20 100", "50%", "calc(50%)"):
            with self.subTest(position=position):
                report = self.report_for(f'''<text x="10" y="100"><tspan x="{position}">Uncertain</tspan></text>''')
                self.assertTrue(any("could not estimate" in message for message in report.warnings), report.warnings)


if __name__ == "__main__":
    unittest.main()
