from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "check_svg.py"
SPEC = importlib.util.spec_from_file_location("check_svg_dark", SCRIPT_PATH)
assert SPEC and SPEC.loader
CHECK_SVG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECK_SVG
SPEC.loader.exec_module(CHECK_SVG)


def diagram(background: str = "#111111", foreground: str = "#ffffff", *, content: bool = True) -> str:
    lesson = f"""<g fill="{foreground}">
    <text x="40" y="55" font-family="Arial, sans-serif" font-size="24">Read, then practise</text>
    <path d="M40 107H275V100L295 110L275 120V113H40Z"/>
  </g>""" if content else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200" viewBox="0 0 400 200" role="img" aria-labelledby="title desc">
  <title id="title">Background comparison fixture</title>
  <desc id="desc">A short lesson and an arrow on a uniform canvas.</desc>
  <!-- Canvas background. -->
  <rect width="400" height="200" fill="{background}"/>
  <!-- Teaching text and arrow. -->
  {lesson}
</svg>"""


class CheckSvgDarkBackgroundTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime = CHECK_SVG.sharp_runtime()
        if runtime is None:
            self.skipTest("Node.js with sharp is unavailable")
        self.node, self.environment = runtime
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def sharp(self, script: str, *arguments: Path) -> str:
        process = subprocess.run(
            [self.node, "-e", script, *(str(argument) for argument in arguments)],
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        return process.stdout

    def compare(self, candidate_source: str, reference_source: str, *, artifacts: bool = False):
        reference_svg = self.directory / "reference.svg"
        reference_png = self.directory / "fixture.png"
        candidate = self.directory / "fixture.svg"
        reference_svg.write_text(reference_source, encoding="utf-8")
        candidate.write_text(candidate_source, encoding="utf-8")
        self.sharp(
            "require('sharp')(process.argv[1]).png().toFile(process.argv[2])"
            ".catch(error=>{console.error(error);process.exit(1)})",
            reference_svg,
            reference_png,
        )
        report = CHECK_SVG.check_file(
            candidate,
            CHECK_SVG.CheckOptions(diff_dir=self.directory / "diff" if artifacts else None),
        )
        self.assertTrue(report.reference_checked, report.errors)
        return report

    def assert_passes(self, report) -> None:
        self.assertEqual([], report.errors)
        self.assertEqual([], report.warnings)

    def test_matching_dark_diagram_passes(self) -> None:
        report = self.compare(diagram(), diagram())
        self.assert_passes(report)
        self.assertTrue(any("background #111111" in note for note in report.notes), report.notes)

    def test_small_position_and_color_differences_pass_on_dark_canvas(self) -> None:
        candidate = diagram("#141414", "#fafafa").replace('<g fill=', '<g transform="translate(1 0)" fill=')
        self.assert_passes(self.compare(candidate, diagram()))

    def test_missing_all_light_teaching_content_fails_despite_small_pixel_error(self) -> None:
        report = self.compare(diagram(content=False), diagram())
        messages = report.errors + report.warnings
        self.assertTrue(any("reference ink recall 0.000" in message for message in messages), messages)
        self.assertFalse(any("normalized mean pixel error" in message for message in messages), messages)

    def test_extra_light_teaching_content_on_dark_canvas_fails(self) -> None:
        report = self.compare(diagram(), diagram(content=False))
        messages = report.errors + report.warnings
        self.assertTrue(any("reference ink precision 0.000" in message for message in messages), messages)
        self.assertFalse(any("normalized mean pixel error" in message for message in messages), messages)

    def test_missing_arrow_is_detected_while_text_remains(self) -> None:
        candidate = diagram().replace('<path d="M40 107H275V100L295 110L275 120V113H40Z"/>', "")
        report = self.compare(candidate, diagram())
        messages = report.errors + report.warnings
        self.assertTrue(any("reference ink recall" in message for message in messages), messages)

    def test_colored_canvases_match_and_missing_content_fails(self) -> None:
        for background, foreground in (("#284b63", "#fff4d6"), ("#cce4bb", "#173b23"), ("#b43c3c", "#3c793c")):
            with self.subTest(background=background, foreground=foreground):
                reference = diagram(background, foreground)
                self.assert_passes(self.compare(reference, reference))
                report = self.compare(diagram(background, content=False), reference)
                messages = report.errors + report.warnings
                self.assertTrue(any("reference ink recall 0.000" in message for message in messages), messages)

    def test_candidate_uses_reference_background_for_foreground_mask(self) -> None:
        report = self.compare(diagram("#777777"), diagram())
        messages = report.errors + report.warnings
        self.assertTrue(any("reference ink precision" in message for message in messages), messages)

    def test_thin_black_frame_does_not_replace_white_background(self) -> None:
        source = diagram("#ffffff", "#111111").replace(
            '<!-- Teaching text and arrow. -->',
            '<rect x="0.5" y="0.5" width="399" height="199" fill="none" stroke="#000000"/>\n'
            '  <!-- Teaching text and arrow. -->',
        )
        report = self.compare(source, source)
        self.assert_passes(report)
        self.assertTrue(any("background #ffffff" in note for note in report.notes), report.notes)

    def test_dark_difference_colors_show_missing_extra_and_equal_contrast_changes(self) -> None:
        for candidate, reference, expected in (
            (diagram(content=False), diagram(), [255, 0, 255]),
            (diagram(), diagram(content=False), [0, 255, 255]),
            (diagram(foreground="#9d8033"), diagram(foreground="#808080"), [127, 127, 127]),
        ):
            with self.subTest(expected=expected):
                self.compare(candidate, reference, artifacts=True)
                pixel = self.sharp(
                    "require('sharp')(process.argv[1]).extract({left:100,top:110,width:1,height:1})"
                    ".removeAlpha().raw().toBuffer().then(data=>console.log(JSON.stringify([...data])))"
                    ".catch(error=>{console.error(error);process.exit(1)})",
                    self.directory / "diff/fixture.difference.png",
                )
                self.assertEqual(expected, json.loads(pixel))


class ForegroundContrastTests(unittest.TestCase):
    def test_white_background_preserves_previous_luminance_exactly(self) -> None:
        colors = [(red, green, blue) for red in range(0, 256, 15) for green in range(0, 256, 15) for blue in range(0, 256, 15)]
        pixels = bytes(channel for color in colors for channel in color)
        expected = bytearray(255 - ((77*red + 150*green + 29*blue) >> 8) for red, green, blue in colors)
        self.assertEqual(expected, CHECK_SVG.foreground_contrast(pixels, (255, 255, 255)))


if __name__ == "__main__":
    unittest.main()
