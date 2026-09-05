#!/usr/bin/env python3
"""Structural and heuristic checks for maintainable SVG diagrams."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


CSS_ESCAPE = r"\\(?:[0-9a-fA-F]{1,6}(?:\r\n|[\t\n\f\r ])?|.)"
CSS_VALUE_TOKEN_RE = re.compile(
    rf"/\*.*?\*/|(?<![\w-])url\(\s*(?:"
    rf'"(?P<double>(?:{CSS_ESCAPE}|[^"\\])*)"|'
    rf"'(?P<single>(?:{CSS_ESCAPE}|[^'\\])*)'|"
    rf"(?P<bare>(?:{CSS_ESCAPE}|[^\s()'\"\\])*))\s*\)"
    rf'|"(?:{CSS_ESCAPE}|[^"\\])*"|'
    rf"'(?:{CSS_ESCAPE}|[^'\\])*'",
    re.DOTALL | re.IGNORECASE,
)
CSS_ESCAPE_RE = re.compile(
    r"\\(?:([0-9a-fA-F]{1,6})(?:\r\n|[\t\n\f\r ])?|(\r\n|[\n\r\f])|(.))",
    re.DOTALL,
)
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
PATH_TOKEN_RE = re.compile(r"[A-Za-z]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
CONNECTOR_HINT_RE = re.compile(r"arrow|connector|flow|shaft", re.IGNORECASE)
MARKER_PROPERTIES = {"marker", "marker-start", "marker-mid", "marker-end"}


def local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def number(value: str | None) -> float | None:
    if value is None:
        return None
    match = NUMBER_RE.match(value.strip())
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def local_url_references(value: str) -> set[str]:
    """Read local CSS url() targets without treating comments or strings as references."""
    def unescape(match: re.Match[str]) -> str:
        if match.group(1):
            codepoint = int(match.group(1), 16)
            if 0 < codepoint <= 0x10FFFF and not 0xD800 <= codepoint <= 0xDFFF:
                return chr(codepoint)
            return "\ufffd"
        return "" if match.group(2) else match.group(3)

    references: set[str] = set()
    for match in CSS_VALUE_TOKEN_RE.finditer(value):
        target = next((part for part in match.groups() if part is not None), None)
        if target is None:
            continue
        target = CSS_ESCAPE_RE.sub(unescape, target)
        if target.startswith("#"):
            references.add(target[1:])
    return references


def without_css_comments(value: str) -> str:
    """Remove comments while preserving identical character sequences inside strings."""
    return CSS_VALUE_TOKEN_RE.sub(
        lambda match: " " if match.group(0).startswith("/*") else match.group(0), value
    )


def css_structure(value: str) -> str:
    """Mask strings and URL tokens so their punctuation is not CSS structure."""
    return CSS_VALUE_TOKEN_RE.sub(lambda match: " " * len(match.group(0)), value)


def stylesheet_rules(value: str) -> Iterable[tuple[str, str]]:
    """Yield leaf rule blocks, including rules nested in @media-style groups."""
    value = without_css_comments(value)
    blocks: list[tuple[str, int]] = []
    boundary = 0
    for index, character in enumerate(css_structure(value)):
        if character == "{":
            blocks.append((value[boundary:index].strip(), index + 1))
            boundary = index + 1
        elif character == "}":
            if blocks:
                selector, start = blocks.pop()
                if "{" not in css_structure(value[start:index]):
                    yield selector, value[start:index]
            boundary = index + 1
        elif character == ";":
            boundary = index + 1


def parse_style_attribute(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    value = without_css_comments(value)
    # Ignore semicolons inside quoted strings and url() when separating declarations.
    declarations: list[str] = []
    start = 0
    for index, character in enumerate(css_structure(value)):
        if character == ";":
            declarations.append(value[start:index])
            start = index + 1
    declarations.append(value[start:])
    return {
        key.strip().lower(): item.strip()
        for declaration in declarations
        for key, separator, item in [declaration.partition(":")]
        if separator and re.fullmatch(r"[\w-]+", key.strip())
    }


def parse_styles(root: ET.Element) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if local_name(element.tag) != "style" or not element.text:
            continue
        for selectors, body in stylesheet_rules(element.text):
            declarations = parse_style_attribute(body)
            for selector in selectors.split(","):
                selector = selector.strip()
                if selector:
                    rules.setdefault(selector, {}).update(declarations)
    return rules


def inherited_property(
    element: ET.Element,
    property_name: str,
    parents: dict[ET.Element, ET.Element],
    styles: dict[str, dict[str, str]],
) -> str | None:
    current: ET.Element | None = element
    while current is not None:
        inline = parse_style_attribute(current.attrib.get("style"))
        if property_name in inline:
            return inline[property_name]
        for class_name in current.attrib.get("class", "").split():
            value = styles.get(f".{class_name}", {}).get(property_name)
            if value is not None:
                return value
        value = styles.get(local_name(current.tag), {}).get(property_name)
        if value is not None:
            return value
        if property_name in current.attrib:
            return current.attrib[property_name]
        current = parents.get(current)
    return None


Matrix = tuple[float, float, float, float, float, float]
Point = tuple[float, float]


IDENTITY_MATRIX: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass(frozen=True)
class CheckOptions:
    reference_mode: str = "auto"
    reference: Path | None = None
    reference_dir: Path | None = None
    diff_dir: Path | None = None
    compare_max_size: int = 1024
    pixel_tolerance: int = 2
    ink_threshold: int = 32
    min_ink_recall: float = 0.88
    min_ink_precision: float = 0.88
    max_mean_error: float = 0.08
    max_bounds_drift: float = 0.025
    max_ink_ratio_delta: float = 0.30


def multiply_matrices(outer: Matrix, inner: Matrix) -> Matrix:
    """Return the affine matrix for outer(inner(point))."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def apply_matrix(matrix: Matrix, point: Point) -> Point:
    a, b, c, d, e, f = matrix
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


def parse_transform(value: str | None) -> Matrix:
    matrix = IDENTITY_MATRIX
    if not value:
        return matrix
    for name, raw_arguments in TRANSFORM_RE.findall(value):
        values = [number(item) for item in re.split(r"[\s,]+", raw_arguments.strip()) if item]
        if any(item is None for item in values):
            continue
        args = [float(item) for item in values if item is not None]
        operation = IDENTITY_MATRIX
        if name == "matrix" and len(args) == 6:
            operation = tuple(args)  # type: ignore[assignment]
        elif name == "translate" and len(args) in {1, 2}:
            operation = (1.0, 0.0, 0.0, 1.0, args[0], args[1] if len(args) == 2 else 0.0)
        elif name == "scale" and len(args) in {1, 2}:
            operation = (args[0], 0.0, 0.0, args[1] if len(args) == 2 else args[0], 0.0, 0.0)
        elif name == "rotate" and len(args) in {1, 3}:
            radians = math.radians(args[0])
            cosine, sine = math.cos(radians), math.sin(radians)
            rotation = (cosine, sine, -sine, cosine, 0.0, 0.0)
            if len(args) == 3:
                cx, cy = args[1], args[2]
                operation = multiply_matrices(
                    (1.0, 0.0, 0.0, 1.0, cx, cy),
                    multiply_matrices(rotation, (1.0, 0.0, 0.0, 1.0, -cx, -cy)),
                )
            else:
                operation = rotation
        elif name == "skewX" and len(args) == 1:
            operation = (1.0, 0.0, math.tan(math.radians(args[0])), 1.0, 0.0, 0.0)
        elif name == "skewY" and len(args) == 1:
            operation = (1.0, math.tan(math.radians(args[0])), 0.0, 1.0, 0.0, 0.0)
        matrix = multiply_matrices(matrix, operation)
    return matrix


def cumulative_matrix(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> Matrix:
    chain: list[ET.Element] = []
    current: ET.Element | None = element
    while current is not None:
        chain.append(current)
        current = parents.get(current)
    matrix = IDENTITY_MATRIX
    for item in reversed(chain):
        matrix = multiply_matrices(matrix, parse_transform(item.attrib.get("transform")))
    return matrix


def is_definition_element(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    current: ET.Element | None = element
    while current is not None:
        if local_name(current.tag) in {"defs", "marker", "symbol", "clipPath", "mask", "pattern"}:
            return True
        current = parents.get(current)
    return False


def estimate_text_width(text: str, font_size: float, bold: bool) -> float:
    units = 0.0
    for char in text:
        if char.isspace():
            units += 0.32
        elif char in "ilI1|.,:;'`!":
            units += 0.30
        elif char in "MW@%&QO":
            units += 0.82
        else:
            units += 0.56
    return units * font_size * (1.05 if bold else 1.0)


@dataclass(frozen=True)
class TextBox:
    label: str
    box: tuple[float, float, float, float]
    polygon: tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class ConnectorSegment:
    element_name: str
    start: Point
    end: Point
    stroke_width: float


class Report:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.reference_checked = False

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def print(self) -> None:
        print(self.path)
        for item in self.errors:
            print(f"  ERROR: {item}")
        for item in self.warnings:
            print(f"  WARN:  {item}")
        for item in self.notes:
            print(f"  INFO:  {item}")
        if not self.errors and not self.warnings:
            suffix = " and reference-image checks" if self.reference_checked else ""
            print(f"  OK: structural{suffix} passed; rendered-image review is still required")


def parse_viewbox(root: ET.Element, report: Report) -> tuple[float, float, float, float] | None:
    raw = root.attrib.get("viewBox")
    if not raw:
        report.error("root <svg> needs a viewBox")
        return None
    values = [number(part) for part in re.split(r"[\s,]+", raw.strip())]
    if len(values) != 4 or any(value is None for value in values):
        report.error(f"invalid viewBox: {raw!r}")
        return None
    x, y, width, height = (float(value) for value in values if value is not None)
    if width <= 0 or height <= 0:
        report.error("viewBox width and height must be positive")
        return None
    return x, y, width, height


def png_dimensions(path: Path) -> tuple[int, int] | None:
    """Read PNG dimensions without adding a Python imaging dependency."""
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


_SHARP_RUNTIME: tuple[str, dict[str, str]] | None | bool = None


def sharp_runtime() -> tuple[str, dict[str, str]] | None:
    """Find Node.js plus sharp, including the bundled Codex workspace runtime."""
    global _SHARP_RUNTIME
    if _SHARP_RUNTIME is False:
        return None
    if isinstance(_SHARP_RUNTIME, tuple):
        return _SHARP_RUNTIME

    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"
    node_candidates = [
        os.environ.get("SVG_CHECK_NODE"),
        shutil.which("node"),
        str(bundled / "node/bin/node"),
    ]
    module_candidates = [item for item in os.environ.get("NODE_PATH", "").split(os.pathsep) if item]
    bundled_modules = bundled / "node/node_modules"
    if bundled_modules.is_dir():
        module_candidates.append(str(bundled_modules))

    for candidate in dict.fromkeys(item for item in node_candidates if item):
        node = Path(candidate)
        if not node.is_file():
            continue
        env = os.environ.copy()
        if module_candidates:
            env["NODE_PATH"] = os.pathsep.join(dict.fromkeys(module_candidates))
        probe = subprocess.run(
            [str(node), "-e", "require('sharp')"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if probe.returncode == 0:
            _SHARP_RUNTIME = (str(node), env)
            return _SHARP_RUNTIME
    _SHARP_RUNTIME = False
    return None


SHARP_RENDER_SCRIPT = r"""
const fs = require('fs');
const sharp = require('sharp');
const [svg, reference, svgRaw, referenceRaw, widthText, heightText, svgPng, referencePng, diffPng] = process.argv.slice(1);
const width = Number(widthText), height = Number(heightText);
function backgroundColor(pixels) {
  // The outer 5% band tolerates a thin frame and antialiasing on the canvas edge.
  const bandX = Math.max(1, Math.ceil(width * 0.05));
  const bandY = Math.max(1, Math.ceil(height * 0.05));
  const buckets = new Map();
  let samples = 0, dominant;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (x >= bandX && x < width-bandX && y >= bandY && y < height-bandY) continue;
      const i = (y*width+x)*3;
      const key = ((pixels[i] >> 4) << 8) | ((pixels[i+1] >> 4) << 4) | (pixels[i+2] >> 4);
      const bucket = buckets.get(key) || [0, 0, 0, 0];
      bucket[0]++; bucket[1] += pixels[i]; bucket[2] += pixels[i+1]; bucket[3] += pixels[i+2];
      buckets.set(key, bucket);
      if (!dominant || bucket[0] > dominant[0]) dominant = bucket;
      samples++;
    }
  }
  // Preserve the traditional white baseline when the border has no stable background.
  return dominant && dominant[0] > samples/2
    ? dominant.slice(1).map(sum => Math.round(sum/dominant[0])) : [255, 255, 255];
}
function contrast(pixels, i, background) {
  // Ceiling division preserves the previous 255-luma mask on white backgrounds.
  return (77*Math.abs(pixels[i]-background[0]) + 150*Math.abs(pixels[i+1]-background[1])
    + 29*Math.abs(pixels[i+2]-background[2]) + 255) >> 8;
}
async function rgb(input, svgInput) {
  let pipeline = sharp(input)
    .resize(width, height, {fit: 'fill', kernel: 'lanczos3'})
    .flatten({background: '#ffffff'})
    .removeAlpha()
    .raw();
  return pipeline.toBuffer();
}
(async () => {
  const candidate = await rgb(svg, true);
  const etalon = await rgb(reference, false);
  const background = backgroundColor(etalon);
  process.stdout.write(JSON.stringify({background}));
  fs.writeFileSync(svgRaw, candidate);
  fs.writeFileSync(referenceRaw, etalon);
  if (svgPng !== '-') await sharp(candidate, {raw:{width,height,channels:3}}).png().toFile(svgPng);
  if (referencePng !== '-') await sharp(etalon, {raw:{width,height,channels:3}}).png().toFile(referencePng);
  if (diffPng !== '-') {
    const diff = Buffer.alloc(candidate.length, 255);
    for (let i = 0; i < candidate.length; i += 3) {
      const delta = contrast(etalon, i, background)-contrast(candidate, i, background);
      const colorError = Math.max(...[0,1,2].map(channel => Math.abs(candidate[i+channel]-etalon[i+channel])));
      const strength = Math.min(255, Math.max(Math.abs(delta), colorError)*4);
      if (delta > 0) { diff[i]=255; diff[i+1]=255-strength; diff[i+2]=255; }
      else if (delta < 0) { diff[i]=255-strength; diff[i+1]=255; diff[i+2]=255; }
      else if (strength) { diff[i]=diff[i+1]=diff[i+2]=255-Math.round(strength/2); }
    }
    await sharp(diff, {raw:{width,height,channels:3}}).png().toFile(diffPng);
  }
})().catch(error => { console.error(error.stack || String(error)); process.exit(1); });
"""


def foreground_contrast(pixels: bytes, background: Sequence[int]) -> bytearray:
    """Measure contrast from the reference canvas, including colored foregrounds."""
    red, green, blue = background
    return bytearray(
        (
            77 * abs(pixels[index] - red)
            + 150 * abs(pixels[index + 1] - green)
            + 29 * abs(pixels[index + 2] - blue)
            + 255
        ) >> 8
        for index in range(0, len(pixels), 3)
    )


def dilate_mask(mask: bytearray, width: int, height: int, radius: int) -> bytearray:
    if radius <= 0:
        return bytearray(mask)
    horizontal = bytearray(width * height)
    for y in range(height):
        row = y * width
        count = sum(mask[row : row + min(width, radius + 1)])
        horizontal[row] = count > 0
        for x in range(1, width):
            add = x + radius
            remove = x - radius - 1
            if add < width:
                count += mask[row + add]
            if remove >= 0:
                count -= mask[row + remove]
            horizontal[row + x] = count > 0
    output = bytearray(width * height)
    for x in range(width):
        count = sum(horizontal[y * width + x] for y in range(min(height, radius + 1)))
        output[x] = count > 0
        for y in range(1, height):
            add = y + radius
            remove = y - radius - 1
            if add < height:
                count += horizontal[add * width + x]
            if remove >= 0:
                count -= horizontal[remove * width + x]
            output[y * width + x] = count > 0
    return output


def content_bounds(mask: bytearray, width: int, height: int) -> tuple[float, float, float, float] | None:
    min_x, min_y = width, height
    max_x = max_y = -1
    for index, value in enumerate(mask):
        if not value:
            continue
        x, y = index % width, index // width
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x), max(max_y, y)
    if max_x < 0:
        return None
    return min_x / width, min_y / height, max_x / width, max_y / height


def visual_issue(report: Report, message: str, severe: bool) -> None:
    (report.error if severe else report.warn)(message)


def compare_reference_image(
    svg_path: Path,
    reference_path: Path,
    root: ET.Element,
    viewbox: tuple[float, float, float, float] | None,
    report: Report,
    options: CheckOptions,
) -> None:
    dimensions = png_dimensions(reference_path)
    if dimensions is None:
        report.error(f"reference image is not a readable PNG: {reference_path}")
        return
    reference_width, reference_height = dimensions
    report.note(f"reference image: {reference_path.name} ({reference_width}x{reference_height})")

    root_width, root_height = number(root.attrib.get("width")), number(root.attrib.get("height"))
    has_root_dimensions = root_width is not None and root_height is not None
    if viewbox is not None:
        _, _, svg_width, svg_height = viewbox
        aspect_error = abs(svg_width / svg_height - reference_width / reference_height) / (reference_width / reference_height)
        if aspect_error > 0.005:
            report.error(
                f"viewBox aspect ratio differs from reference by {aspect_error:.1%} "
                f"({svg_width:g}x{svg_height:g} vs {reference_width}x{reference_height})"
            )
        # viewBox values are user-space units, so absolute pixel comparison is only a fallback.
        if not has_root_dimensions and (
            abs(svg_width - reference_width) > 1 or abs(svg_height - reference_height) > 1
        ):
            report.warn(
                f"viewBox dimensions differ from reference ({svg_width:g}x{svg_height:g} vs "
                f"{reference_width}x{reference_height}); preserve the etalon canvas when recreating it"
            )
    if has_root_dimensions and (
        abs(root_width - reference_width) > 1 or abs(root_height - reference_height) > 1
    ):
        report.warn(
            f"root width/height differ from reference ({root_width:g}x{root_height:g} vs "
            f"{reference_width}x{reference_height})"
        )

    runtime = sharp_runtime()
    if runtime is None:
        report.error(
            "cannot render reference comparison: Node.js with sharp is unavailable; load the bundled "
            "workspace dependencies or set SVG_CHECK_NODE and NODE_PATH"
        )
        return
    node, env = runtime
    scale = min(1.0, options.compare_max_size / max(reference_width, reference_height))
    width = max(1, round(reference_width * scale))
    height = max(1, round(reference_height * scale))
    artifact_paths = ("-", "-", "-")
    if options.diff_dir is not None:
        options.diff_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths = (
            str(options.diff_dir / f"{svg_path.stem}.rendered.png"),
            str(options.diff_dir / f"{svg_path.stem}.reference.png"),
            str(options.diff_dir / f"{svg_path.stem}.difference.png"),
        )
    with tempfile.TemporaryDirectory(prefix="svg-check-") as temporary:
        temporary_path = Path(temporary)
        candidate_raw = temporary_path / "candidate.rgb"
        reference_raw = temporary_path / "reference.rgb"
        process = subprocess.run(
            [
                node,
                "-e",
                SHARP_RENDER_SCRIPT,
                str(svg_path.resolve()),
                str(reference_path.resolve()),
                str(candidate_raw),
                str(reference_raw),
                str(width),
                str(height),
                *artifact_paths,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            detail = " ".join(process.stderr.split())[-400:]
            report.error(f"reference renderer failed: {detail}")
            return
        try:
            background = json.loads(process.stdout)["background"]
            if len(background) != 3 or any(type(channel) is not int or not 0 <= channel <= 255 for channel in background):
                raise ValueError("invalid background color")
        except (ValueError, KeyError, TypeError):
            report.error("reference renderer returned invalid background-color metadata")
            return
        candidate = candidate_raw.read_bytes()
        reference = reference_raw.read_bytes()

    expected_bytes = width * height * 3
    if len(candidate) != expected_bytes or len(reference) != expected_bytes:
        report.error("reference renderer returned unexpected raw-image dimensions")
        return
    report.reference_checked = True
    candidate_contrast = foreground_contrast(candidate, background)
    reference_contrast = foreground_contrast(reference, background)
    absolute_error = 0
    for index in range(0, expected_bytes, 3):
        absolute_error += abs(candidate[index] - reference[index])
        absolute_error += abs(candidate[index + 1] - reference[index + 1])
        absolute_error += abs(candidate[index + 2] - reference[index + 2])
    mean_error = absolute_error / (expected_bytes * 255)
    candidate_mask = bytearray(1 if value >= options.ink_threshold else 0 for value in candidate_contrast)
    reference_mask = bytearray(1 if value >= options.ink_threshold else 0 for value in reference_contrast)
    candidate_ink, reference_ink = sum(candidate_mask), sum(reference_mask)
    candidate_dilated = dilate_mask(candidate_mask, width, height, options.pixel_tolerance)
    reference_dilated = dilate_mask(reference_mask, width, height, options.pixel_tolerance)
    recall = (
        sum(1 for index, value in enumerate(reference_mask) if value and candidate_dilated[index]) / reference_ink
        if reference_ink
        else 1.0
    )
    precision = (
        sum(1 for index, value in enumerate(candidate_mask) if value and reference_dilated[index]) / candidate_ink
        if candidate_ink
        else 1.0
    )
    ink_ratio_delta = abs(candidate_ink - reference_ink) / max(reference_ink, 1)
    candidate_bounds = content_bounds(candidate_mask, width, height)
    reference_bounds = content_bounds(reference_mask, width, height)
    bounds_drift = (
        max(abs(first - second) for first, second in zip(candidate_bounds, reference_bounds))
        if candidate_bounds is not None and reference_bounds is not None
        else 1.0 if candidate_bounds != reference_bounds else 0.0
    )
    report.note(
        f"visual comparison at {width}x{height} (background #{''.join(f'{channel:02x}' for channel in background)}): "
        f"mean error {mean_error:.3f}, "
        f"ink recall {recall:.3f}, ink precision {precision:.3f}, "
        f"ink delta {ink_ratio_delta:.1%}, bounds drift {bounds_drift:.1%}"
    )
    if options.diff_dir is not None:
        report.note(f"comparison artifacts: {options.diff_dir}")

    if recall < options.min_ink_recall:
        visual_issue(
            report,
            f"reference ink recall {recall:.3f} is below {options.min_ink_recall:.3f}; "
            "the SVG may be missing lines, arrowheads, text, or shapes",
            recall < options.min_ink_recall * 0.55,
        )
    if precision < options.min_ink_precision:
        visual_issue(
            report,
            f"reference ink precision {precision:.3f} is below {options.min_ink_precision:.3f}; "
            "the SVG may contain extra or displaced content",
            precision < options.min_ink_precision * 0.55,
        )
    if mean_error > options.max_mean_error:
        visual_issue(
            report,
            f"normalized mean pixel error {mean_error:.3f} exceeds {options.max_mean_error:.3f}",
            mean_error > max(0.25, options.max_mean_error * 3),
        )
    if bounds_drift > options.max_bounds_drift:
        visual_issue(
            report,
            f"content-bounds drift {bounds_drift:.1%} exceeds {options.max_bounds_drift:.1%}; "
            "check margins, clipping, and overall placement",
            bounds_drift > max(0.10, options.max_bounds_drift * 4),
        )
    if ink_ratio_delta > options.max_ink_ratio_delta:
        visual_issue(
            report,
            f"foreground-ink amount differs by {ink_ratio_delta:.1%}, above the "
            f"{options.max_ink_ratio_delta:.1%} allowance",
            ink_ratio_delta > max(0.90, options.max_ink_ratio_delta * 3),
        )


def collect_text_boxes(
    root: ET.Element,
    parents: dict[ET.Element, ET.Element],
    styles: dict[str, dict[str, str]],
    report: Report,
) -> list[TextBox]:
    boxes: list[TextBox] = []

    def text_coordinate(value: str | None, font_size: float) -> float | None:
        if value is None:
            return None
        raw = value.strip()
        # Lists and percentage/layout expressions need renderer metrics; do not
        # silently use only their first number as a single run's position.
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:px|em|ex)?", raw):
            return None
        parsed = number(raw)
        if parsed is None or not math.isfinite(parsed):
            return None
        if raw.endswith("em"):
            return parsed * font_size
        if raw.endswith("ex"):
            return parsed * font_size * 0.5
        return parsed

    def text_width(element: ET.Element, label: str) -> float:
        font_size = number(inherited_property(element, "font-size", parents, styles)) or 16.0
        font_weight = inherited_property(element, "font-weight", parents, styles) or "normal"
        return estimate_text_width(label, font_size, font_weight in {"bold", "600", "700", "800", "900"})

    def append_box(element: ET.Element, label: str, left: float, y: float, width: float) -> None:
        font_size = number(inherited_property(element, "font-size", parents, styles)) or 16.0
        local_polygon = (
            (left, y - 0.85 * font_size),
            (left + width, y - 0.85 * font_size),
            (left + width, y + 0.25 * font_size),
            (left, y + 0.25 * font_size),
        )
        matrix = cumulative_matrix(element, parents)
        polygon = tuple(apply_matrix(matrix, point) for point in local_polygon)
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        boxes.append(
            TextBox(
                label=label[:80],
                box=(min(xs), min(ys), max(xs), max(ys)),
                polygon=polygon,  # type: ignore[arg-type]
            )
        )

    def text_events(element: ET.Element) -> Iterable[tuple[ET.Element, str | None]]:
        # Descriptive content is not painted and must not advance the text cursor.
        if local_name(element.tag) in {"title", "desc", "metadata"}:
            return
        # None marks entry/positioning; a child's tail belongs to its parent.
        yield element, None
        if element.text:
            yield element, element.text
        for child in element:
            yield from text_events(child)
            if child.tail:
                yield element, child.tail

    unestimated_text = 0
    unestimated_tspans = 0
    for element in root.iter():
        if local_name(element.tag) != "text":
            continue
        if is_definition_element(element, parents):
            continue
        has_tspans = any(local_name(child.tag) == "tspan" for child in element.iter())
        current_x: float | None = 0.0
        current_y: float | None = 0.0
        # SVG anchors the entire chunk, including nested styles and relative
        # offsets. Absolute x/y starts a new chunk; each inline tspan does not.
        chunk: list[tuple[ET.Element, str, float, float, float]] = []
        chunk_start = 0.0
        chunk_end = 0.0
        chunk_anchor = "start"
        previous_space = False

        def flush_chunk() -> None:
            nonlocal chunk, current_x, previous_space
            if chunk:
                advance = chunk_end - chunk_start
                shift = advance / 2 if chunk_anchor == "middle" else advance if chunk_anchor == "end" else 0.0
                for run_element, label, x, y, width in chunk:
                    append_box(run_element, label, x - shift, y, width)
                # A y-only position continues from the anchored end of the last
                # chunk. Collapsed trailing whitespace is not painted.
                current_x = chunk_end - shift
                chunk = []
            previous_space = False

        for run_element, raw_text in text_events(element):
            font_size = number(inherited_property(run_element, "font-size", parents, styles)) or 16.0
            if raw_text is None:
                if "x" in run_element.attrib or "y" in run_element.attrib:
                    flush_chunk()
                if "x" in run_element.attrib:
                    current_x = text_coordinate(run_element.attrib["x"], font_size)
                if "y" in run_element.attrib:
                    current_y = text_coordinate(run_element.attrib["y"], font_size)
                for attribute in ("dx", "dy"):
                    if attribute not in run_element.attrib:
                        continue
                    delta = text_coordinate(run_element.attrib[attribute], font_size)
                    if attribute == "dx":
                        current_x = current_x + delta if current_x is not None and delta is not None else None
                    else:
                        current_y = current_y + delta if current_y is not None and delta is not None else None
                continue

            normalized = re.sub(r"\s+", " ", raw_text)
            if not chunk or previous_space:
                normalized = normalized.lstrip(" ")
            if not normalized:
                continue
            previous_space = normalized.endswith(" ")
            label = normalized.strip(" ")
            if current_x is None or current_y is None:
                if label:
                    if has_tspans:
                        unestimated_tspans += 1
                    else:
                        unestimated_text += 1
                continue
            if label:
                leading = normalized[:len(normalized) - len(normalized.lstrip(" "))]
                left = current_x + text_width(run_element, leading)
                width = text_width(run_element, label)
                if not chunk:
                    chunk_start = left
                    chunk_anchor = inherited_property(run_element, "text-anchor", parents, styles) or "start"
                chunk.append((run_element, label, left, current_y, width))
                chunk_end = left + width
            # Explicit x sets the beginning of a run, never its ending cursor.
            current_x += text_width(run_element, normalized)
        flush_chunk()
    if unestimated_text:
        report.warn(
            f"could not estimate bounds for {unestimated_text} single-line <text> element(s); "
            "inspect them in the render"
        )
    if unestimated_tspans:
        report.warn(f"could not estimate bounds for {unestimated_tspans} <tspan> line(s); inspect them in the render")
    return boxes


def polygon_axes(polygon: Sequence[Point]) -> Iterable[Point]:
    for index, point in enumerate(polygon):
        next_point = polygon[(index + 1) % len(polygon)]
        dx, dy = next_point[0] - point[0], next_point[1] - point[1]
        length = math.hypot(dx, dy)
        if length > 1e-9:
            yield -dy / length, dx / length


def polygon_overlap_depth(first: Sequence[Point], second: Sequence[Point]) -> float:
    minimum_overlap = math.inf
    for axis_x, axis_y in [*polygon_axes(first), *polygon_axes(second)]:
        first_projection = [x * axis_x + y * axis_y for x, y in first]
        second_projection = [x * axis_x + y * axis_y for x, y in second]
        overlap = min(max(first_projection), max(second_projection)) - max(
            min(first_projection), min(second_projection)
        )
        if overlap <= 0:
            return 0.0
        minimum_overlap = min(minimum_overlap, overlap)
    return 0.0 if math.isinf(minimum_overlap) else minimum_overlap


def boxes_overlap(first: TextBox, second: TextBox) -> bool:
    return polygon_overlap_depth(first.polygon, second.polygon) > 1.0


def interpolate_cubic(start: Point, control1: Point, control2: Point, end: Point, t: float) -> Point:
    inverse = 1.0 - t
    return (
        inverse**3 * start[0]
        + 3 * inverse**2 * t * control1[0]
        + 3 * inverse * t**2 * control2[0]
        + t**3 * end[0],
        inverse**3 * start[1]
        + 3 * inverse**2 * t * control1[1]
        + 3 * inverse * t**2 * control2[1]
        + t**3 * end[1],
    )


def interpolate_quadratic(start: Point, control: Point, end: Point, t: float) -> Point:
    inverse = 1.0 - t
    return (
        inverse**2 * start[0] + 2 * inverse * t * control[0] + t**2 * end[0],
        inverse**2 * start[1] + 2 * inverse * t * control[1] + t**2 * end[1],
    )


def arc_segments(
    start: Point,
    end: Point,
    radius_x: float,
    radius_y: float,
    rotation: float,
    large_arc: bool,
    sweep: bool,
    tolerance: float,
) -> list[tuple[Point, Point]]:
    """Flatten an SVG endpoint-parameterized ellipse, not its endpoint chord.

    Center conversion and radius correction follow SVG implementation notes:
    https://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes
    """
    if start == end:
        return []
    rx, ry = abs(radius_x), abs(radius_y)
    if rx == 0 or ry == 0:
        return [(start, end)]
    phi = math.radians(rotation % 360)
    cosine, sine = math.cos(phi), math.sin(phi)
    dx, dy = (start[0] - end[0]) / 2, (start[1] - end[1]) / 2
    xp, yp = cosine * dx + sine * dy, -sine * dx + cosine * dy
    normalized_x, normalized_y = xp / rx, yp / ry
    radius_scale = math.hypot(normalized_x, normalized_y)
    if radius_scale > 1:
        rx *= radius_scale
        ry *= radius_scale
        normalized_x, normalized_y = xp / rx, yp / ry
    squared_distance = normalized_x**2 + normalized_y**2
    if squared_distance == 0:
        return [(start, end)]
    coefficient = math.sqrt(max(0.0, (1 - squared_distance) / squared_distance))
    if large_arc == sweep:
        coefficient = -coefficient
    cxp, cyp = coefficient * rx * normalized_y, -coefficient * ry * normalized_x
    cx = cosine * cxp - sine * cyp + (start[0] + end[0]) / 2
    cy = sine * cxp + cosine * cyp + (start[1] + end[1]) / 2
    ux, uy = (xp - cxp) / rx, (yp - cyp) / ry
    vx, vy = (-xp - cxp) / rx, (-yp - cyp) / ry
    theta = math.atan2(uy, ux)
    delta = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    if sweep and delta < 0:
        delta += math.tau
    elif not sweep and delta > 0:
        delta -= math.tau

    # Bound chord sagitta using the largest ellipse radius. The caller adjusts
    # tolerance for transforms. A cap keeps extreme coordinates from exploding
    # the structural check; font metrics and geometry remain heuristic.
    max_angle = min(math.pi / 12, 4 * math.asin(math.sqrt(min(1.0, tolerance / (2 * max(rx, ry))))))
    steps = min(4096, max(1, math.ceil(abs(delta) / max(max_angle, 1e-9))))
    segments: list[tuple[Point, Point]] = []
    previous = start
    for step in range(1, steps + 1):
        angle = theta + delta * step / steps
        point = end if step == steps else (
            cx + cosine * rx * math.cos(angle) - sine * ry * math.sin(angle),
            cy + sine * rx * math.cos(angle) + cosine * ry * math.sin(angle),
        )
        segments.append((previous, point))
        previous = point
    return segments


def path_segments(raw: str, tolerance: float = 0.25) -> list[tuple[Point, Point]]:
    tokens = PATH_TOKEN_RE.findall(raw)
    segments: list[tuple[Point, Point]] = []
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    index = 0
    command: str | None = None
    current: Point = (0.0, 0.0)
    subpath_start: Point = current
    previous_command = ""
    previous_control: Point | None = None

    def absolute_pair(x: float, y: float, relative: bool, origin: Point) -> Point:
        return (x + origin[0], y + origin[1]) if relative else (x, y)

    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command.upper() == "Z":
                if current != subpath_start:
                    segments.append((current, subpath_start))
                current = subpath_start
                previous_command = "Z"
                previous_control = None
                command = None
                continue
        if command is None:
            break

        upper = command.upper()
        count = arity.get(upper)
        if count is None:
            break
        values: list[float] = []
        for argument in range(count):
            if index >= len(tokens) or tokens[index].isalpha():
                break
            token = tokens[index]
            if upper == "A" and argument in {3, 4}:
                # Arc flags can abut one another and the following coordinate:
                # A80 80 0 01180 100 means flags 0,1 and endpoint 180,100.
                if token[0] not in "01":
                    break
                values.append(float(token[0]))
                if len(token) > 1:
                    tokens[index] = token[1:]
                else:
                    index += 1
            else:
                try:
                    value = float(token)
                except ValueError:
                    break
                if not math.isfinite(value):
                    break
                values.append(value)
                index += 1
        if len(values) != count:
            break
        relative = command.islower()
        start = current

        if upper == "M":
            current = absolute_pair(values[0], values[1], relative, start)
            subpath_start = current
            command = "l" if relative else "L"
            previous_command = "M"
            previous_control = None
            continue
        if upper == "L":
            end = absolute_pair(values[0], values[1], relative, start)
            segments.append((start, end))
            current = end
            previous_control = None
        elif upper == "H":
            end = (values[0] + start[0] if relative else values[0], start[1])
            segments.append((start, end))
            current = end
            previous_control = None
        elif upper == "V":
            end = (start[0], values[0] + start[1] if relative else values[0])
            segments.append((start, end))
            current = end
            previous_control = None
        elif upper == "C":
            control1 = absolute_pair(values[0], values[1], relative, start)
            control2 = absolute_pair(values[2], values[3], relative, start)
            end = absolute_pair(values[4], values[5], relative, start)
            previous = start
            for step in range(1, 13):
                point = interpolate_cubic(start, control1, control2, end, step / 12)
                segments.append((previous, point))
                previous = point
            current = end
            previous_control = control2
        elif upper == "S":
            control1 = (
                (2 * start[0] - previous_control[0], 2 * start[1] - previous_control[1])
                if previous_command in {"C", "S"} and previous_control is not None
                else start
            )
            control2 = absolute_pair(values[0], values[1], relative, start)
            end = absolute_pair(values[2], values[3], relative, start)
            previous = start
            for step in range(1, 13):
                point = interpolate_cubic(start, control1, control2, end, step / 12)
                segments.append((previous, point))
                previous = point
            current = end
            previous_control = control2
        elif upper == "Q":
            control = absolute_pair(values[0], values[1], relative, start)
            end = absolute_pair(values[2], values[3], relative, start)
            previous = start
            for step in range(1, 13):
                point = interpolate_quadratic(start, control, end, step / 12)
                segments.append((previous, point))
                previous = point
            current = end
            previous_control = control
        elif upper == "T":
            control = (
                (2 * start[0] - previous_control[0], 2 * start[1] - previous_control[1])
                if previous_command in {"Q", "T"} and previous_control is not None
                else start
            )
            end = absolute_pair(values[0], values[1], relative, start)
            previous = start
            for step in range(1, 13):
                point = interpolate_quadratic(start, control, end, step / 12)
                segments.append((previous, point))
                previous = point
            current = end
            previous_control = control
        elif upper == "A":
            end = absolute_pair(values[5], values[6], relative, start)
            segments.extend(arc_segments(start, end, values[0], values[1], values[2], bool(values[3]), bool(values[4]), tolerance))
            current = end
            previous_control = None
        previous_command = upper
    return segments


def collect_connector_segments(
    root: ET.Element,
    parents: dict[ET.Element, ET.Element],
    styles: dict[str, dict[str, str]],
) -> list[ConnectorSegment]:
    connectors: list[ConnectorSegment] = []
    for element in root.iter():
        name = local_name(element.tag)
        if name not in {"line", "polyline", "path"} or is_definition_element(element, parents):
            continue
        marker_values = [
            inherited_property(element, property_name, parents, styles)
            for property_name in MARKER_PROPERTIES
        ]
        marker_connector = any(value and local_url_references(value) for value in marker_values)
        hint = " ".join(
            filter(
                None,
                (
                    element.attrib.get("id"),
                    element.attrib.get("class"),
                    element.attrib.get("data-role"),
                ),
            )
        )
        explicit_connector = element.attrib.get("data-connector", "").lower() in {"1", "true", "yes"}
        if not marker_connector and not explicit_connector and not CONNECTOR_HINT_RE.search(hint):
            continue

        matrix = cumulative_matrix(element, parents)
        # Frobenius norm bounds the largest stretch, including skew.
        stretch = math.sqrt(sum(value * value for value in matrix[:4]))
        raw_segments: list[tuple[Point, Point]] = []
        if name == "line":
            values = [number(element.attrib.get(attr)) for attr in ("x1", "y1", "x2", "y2")]
            if all(value is not None for value in values):
                x1, y1, x2, y2 = (float(value) for value in values if value is not None)
                raw_segments.append(((x1, y1), (x2, y2)))
        elif name == "polyline":
            values = [number(item) for item in re.split(r"[\s,]+", element.attrib.get("points", "").strip()) if item]
            points = [
                (float(values[index]), float(values[index + 1]))
                for index in range(0, len(values) - 1, 2)
                if values[index] is not None and values[index + 1] is not None
            ]
            raw_segments.extend(zip(points, points[1:]))
        else:
            raw_segments = path_segments(element.attrib.get("d", ""), 0.25 / max(stretch, 1.0))

        stroke_width = number(inherited_property(element, "stroke-width", parents, styles)) or 1.0
        identifier = element.attrib.get("id")
        if identifier:
            element_name = f"<{name}#{identifier}>"
        elif name == "path" and element.attrib.get("d"):
            path_excerpt = element.attrib["d"][:48]
            element_name = f"<path d={path_excerpt!r}>"
        else:
            element_name = f"<{name}>"
        for start, end in raw_segments:
            connectors.append(
                ConnectorSegment(
                    element_name=element_name,
                    start=apply_matrix(matrix, start),
                    end=apply_matrix(matrix, end),
                    stroke_width=stroke_width,
                )
            )
    return connectors


def point_in_convex_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    signs: list[float] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        cross = (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
        if abs(cross) > 1e-9:
            signs.append(cross)
    return not signs or all(value >= 0 for value in signs) or all(value <= 0 for value in signs)


def point_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    projection = max(0.0, min(1.0, projection))
    closest = start[0] + projection * dx, start[1] + projection * dy
    return math.hypot(point[0] - closest[0], point[1] - closest[1])


def segments_intersect(first_start: Point, first_end: Point, second_start: Point, second_end: Point) -> bool:
    def orientation(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(start: Point, end: Point, point: Point) -> bool:
        return (
            min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
            and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
        )

    first = orientation(first_start, first_end, second_start)
    second = orientation(first_start, first_end, second_end)
    third = orientation(second_start, second_end, first_start)
    fourth = orientation(second_start, second_end, first_end)
    if first * second < 0 and third * fourth < 0:
        return True
    if abs(first) <= 1e-9 and on_segment(first_start, first_end, second_start):
        return True
    if abs(second) <= 1e-9 and on_segment(first_start, first_end, second_end):
        return True
    if abs(third) <= 1e-9 and on_segment(second_start, second_end, first_start):
        return True
    if abs(fourth) <= 1e-9 and on_segment(second_start, second_end, first_end):
        return True
    return False


def segment_polygon_distance(start: Point, end: Point, polygon: Sequence[Point]) -> float:
    if point_in_convex_polygon(start, polygon) or point_in_convex_polygon(end, polygon):
        return 0.0
    edges = list(zip(polygon, [*polygon[1:], polygon[0]]))
    if any(segments_intersect(start, end, edge_start, edge_end) for edge_start, edge_end in edges):
        return 0.0
    distances = [point_segment_distance(start, edge_start, edge_end) for edge_start, edge_end in edges]
    distances.extend(point_segment_distance(end, edge_start, edge_end) for edge_start, edge_end in edges)
    distances.extend(point_segment_distance(point, start, end) for point in polygon)
    return min(distances, default=math.inf)


def check_text(
    root: ET.Element,
    viewbox: tuple[float, float, float, float] | None,
    report: Report,
) -> None:
    parents = {child: parent for parent in root.iter() for child in parent}
    styles = parse_styles(root)
    boxes = collect_text_boxes(root, parents, styles, report)
    connectors = collect_connector_segments(root, parents, styles)
    reported_pairs = 0
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            if boxes_overlap(first, second):
                report.warn(f"possible text overlap: {first.label!r} and {second.label!r}")
                reported_pairs += 1
                if reported_pairs >= 12:
                    report.warn("additional possible text overlaps omitted")
                    break
        if reported_pairs >= 12:
            break
    reported_connector_collisions = 0
    for text_box in boxes:
        reported_connectors: set[str] = set()
        for connector in connectors:
            if connector.element_name in reported_connectors:
                continue
            clearance = connector.stroke_width / 2 + 1.0
            if segment_polygon_distance(connector.start, connector.end, text_box.polygon) <= clearance:
                reported_connectors.add(connector.element_name)
                report.warn(
                    f"possible text/connector overlap: {text_box.label!r} with {connector.element_name}"
                )
                reported_connector_collisions += 1
                if reported_connector_collisions >= 12:
                    report.warn("additional possible text/connector overlaps omitted")
                    break
        if reported_connector_collisions >= 12:
            break
    if viewbox:
        vx, vy, width, height = viewbox
        right, bottom = vx + width, vy + height
        clipped = [
            item.label
            for item in boxes
            if item.box[0] < vx or item.box[1] < vy or item.box[2] > right or item.box[3] > bottom
        ]
        for label in clipped[:8]:
            report.warn(f"estimated text bounds leave the viewBox: {label!r}")
        if len(clipped) > 8:
            report.warn(f"{len(clipped) - 8} additional possible text clipping issue(s) omitted")


def check_ids_and_references(root: ET.Element, report: Report) -> None:
    ids: dict[str, ET.Element] = {}
    for element in root.iter():
        identifier = element.attrib.get("id")
        if not identifier:
            continue
        if identifier in ids:
            report.error(f"duplicate id #{identifier}")
        ids[identifier] = element

    references: set[str] = set()
    for element in root.iter():
        for key, value in element.attrib.items():
            references.update(local_url_references(value))
            if local_name(key) == "href" and value.startswith("#"):
                references.add(value[1:])
        if local_name(element.tag) == "style":
            references.update(local_url_references("".join(element.itertext())))
    for reference in sorted(references - ids.keys()):
        report.error(f"unresolved reference #{reference}")


def check_symbol_uses(root: ET.Element, report: Report) -> None:
    """Require portable sizing when <use> instantiates a <symbol>."""
    symbols = {
        element.attrib["id"]
        for element in root.iter()
        if local_name(element.tag) == "symbol" and element.attrib.get("id")
    }
    for element in root.iter():
        if local_name(element.tag) != "use":
            continue
        href = next(
            (
                value
                for key, value in element.attrib.items()
                if local_name(key) == "href" and value.startswith("#")
            ),
            None,
        )
        if not href or href[1:] not in symbols:
            continue
        missing = [attribute for attribute in ("width", "height") if attribute not in element.attrib]
        if missing:
            report.warn(
                f"<use> of symbol #{href[1:]} needs explicit {' and '.join(missing)} for portable rendering"
            )
        for attribute in ("width", "height"):
            value = number(element.attrib.get(attribute))
            if value is not None and value <= 0:
                report.error(f"<use> of symbol #{href[1:]} has non-positive {attribute}")


def check_markers(root: ET.Element, report: Report) -> None:
    referenced_markers: set[str] = set()
    markers: dict[str, ET.Element] = {}
    ids = {element.attrib["id"]: element for element in root.iter() if element.attrib.get("id")}
    for element in root.iter():
        if local_name(element.tag) == "marker" and element.attrib.get("id"):
            markers[element.attrib["id"]] = element
        declarations = list(element.attrib.items())
        declarations.extend(parse_style_attribute(element.attrib.get("style")).items())
        if local_name(element.tag) == "style":
            for _, body in stylesheet_rules("".join(element.itertext())):
                declarations.extend(parse_style_attribute(body).items())
        for key, value in declarations:
            if local_name(key).lower() in MARKER_PROPERTIES:
                referenced_markers.update(local_url_references(value))

    for marker_id in sorted(referenced_markers):
        marker = markers.get(marker_id)
        if marker is None:
            if marker_id in ids:
                report.error(f"marker reference #{marker_id} does not target a <marker> element")
            continue
        for attr in ("markerWidth", "markerHeight", "refX", "refY", "orient"):
            if attr not in marker.attrib:
                report.warn(f"marker #{marker_id} should declare {attr}")
        for attr in ("markerWidth", "markerHeight"):
            value = number(marker.attrib.get(attr))
            if value is not None and value <= 0:
                report.error(f"marker #{marker_id} has non-positive {attr}")
        if "viewBox" not in marker.attrib:
            report.warn(f"marker #{marker_id} should declare a viewBox to make clipping behavior explicit")
        if "markerUnits" not in marker.attrib:
            report.warn(f"marker #{marker_id} should declare markerUnits")

    for element in root.iter():
        if local_name(element.tag) != "line":
            continue
        x1, y1 = number(element.attrib.get("x1")), number(element.attrib.get("y1"))
        x2, y2 = number(element.attrib.get("x2")), number(element.attrib.get("y2"))
        if None not in (x1, y1, x2, y2) and math.isclose(x1, x2) and math.isclose(y1, y2):
            report.error("zero-length <line> cannot provide a reliable arrow direction")


def check_source_native(root: ET.Element, report: Report) -> bool:
    raster_images = [element for element in root.iter() if local_name(element.tag) == "image"]
    if raster_images:
        report.error(
            f"{len(raster_images)} embedded/external <image> element(s) found; recreate the content as "
            "editable SVG shapes instead of embedding the raster etalon"
        )
    foreign_objects = [element for element in root.iter() if local_name(element.tag) == "foreignObject"]
    if foreign_objects:
        report.warn(
            f"{len(foreign_objects)} <foreignObject> element(s) found; portable technical diagrams should "
            "use native SVG text and shapes"
        )
    scripts = [element for element in root.iter() if local_name(element.tag) == "script"]
    if scripts:
        report.error("scripts are not allowed in a self-contained diagram")
    return not raster_images and not scripts


def find_reference(path: Path, options: CheckOptions, report: Report) -> Path | None:
    if options.reference_mode == "off":
        return None
    if options.reference is not None:
        if not options.reference.is_file():
            report.error(f"reference image does not exist: {options.reference}")
            return None
        return options.reference
    directory = options.reference_dir or path.parent
    if directory.is_dir():
        for candidate in directory.iterdir():
            if candidate.is_file() and candidate.stem == path.stem and candidate.suffix.lower() == ".png":
                return candidate
    if options.reference_mode == "required":
        report.error(f"no same-stem PNG reference found for {path.name} in {directory}")
    return None


def check_file(path: Path, options: CheckOptions | None = None) -> Report:
    options = options or CheckOptions(reference_mode="off")
    report = Report(path)
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        report.error(f"cannot read UTF-8 SVG: {exc}")
        return report

    comments = [" ".join(item.split()) for item in COMMENT_RE.findall(source)]
    if not comments:
        report.error("add XML comments for logical sections and fragile geometry")
    elif len(comments) == 1:
        report.warn("only one XML comment found; make each logical section easy to locate")
    for comment in comments:
        if len(comment) < 4:
            report.warn(f"comment is too terse to help a quick fix: {comment!r}")

    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        report.error(f"invalid XML: {exc}")
        return report
    if local_name(root.tag) != "svg":
        report.error("document root must be <svg>")
        return report

    viewbox = parse_viewbox(root, report)
    child_names = {local_name(child.tag) for child in root}
    if "title" not in child_names:
        report.warn("add a direct-child <title> for accessibility")
    if "desc" not in child_names:
        report.warn("add a direct-child <desc> for accessibility")
    if root.attrib.get("role") != "img":
        report.warn("set role=\"img\" unless the embedding context provides semantics")
    if not root.attrib.get("aria-labelledby"):
        report.warn("connect <title>/<desc> with aria-labelledby")

    check_ids_and_references(root, report)
    check_symbol_uses(root, report)
    check_markers(root, report)
    safe_to_render = check_source_native(root, report)
    check_text(root, viewbox, report)
    reference = find_reference(path, options, report)
    if reference is not None:
        if safe_to_render:
            compare_reference_image(path, reference, root, viewbox, report, options)
        else:
            report.note("reference comparison skipped because the SVG contains prohibited active or raster content")
    return report


def iter_svg_paths(values: Iterable[str]) -> Iterable[Path]:
    for value in values:
        path = Path(value)
        if path.is_dir():
            yield from sorted(path.glob("*.svg"))
        else:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="SVG file(s) or directories containing SVG files")
    parser.add_argument("--strict", action="store_true", help="return failure when warnings are present")
    reference_group = parser.add_argument_group("reference-image comparison")
    reference_group.add_argument(
        "--reference-mode",
        choices=("auto", "required", "off"),
        default="auto",
        help="auto-discover same-stem PNGs (default), require them, or disable raster comparison",
    )
    reference_group.add_argument("--reference", type=Path, help="explicit PNG reference; valid with one SVG")
    reference_group.add_argument("--reference-dir", type=Path, help="directory containing same-stem PNG references")
    reference_group.add_argument("--diff-dir", type=Path, help="write normalized SVG, reference, and difference PNGs")
    reference_group.add_argument("--compare-max-size", type=int, default=1024, help="maximum comparison width/height")
    reference_group.add_argument("--pixel-tolerance", type=int, default=2, help="pixel radius allowed for ink matching")
    reference_group.add_argument("--ink-threshold", type=int, default=32, help="minimum contrast from the reference background counted as foreground ink")
    reference_group.add_argument("--min-ink-recall", type=float, default=0.88, help="minimum reference ink recovered")
    reference_group.add_argument("--min-ink-precision", type=float, default=0.88, help="minimum SVG ink matching the reference")
    reference_group.add_argument("--max-mean-error", type=float, default=0.08, help="maximum normalized mean pixel error")
    reference_group.add_argument("--max-bounds-drift", type=float, default=0.025, help="maximum normalized content-bounds drift")
    reference_group.add_argument("--max-ink-ratio-delta", type=float, default=0.30, help="maximum foreground-ink amount difference")
    args = parser.parse_args()

    paths = list(iter_svg_paths(args.paths))
    if not paths:
        parser.error("no SVG files found")
    if args.reference is not None and len(paths) != 1:
        parser.error("--reference requires exactly one SVG input")
    if args.reference_mode == "off" and (args.reference is not None or args.reference_dir is not None):
        parser.error("--reference-mode off cannot be combined with --reference or --reference-dir")
    if args.compare_max_size < 64:
        parser.error("--compare-max-size must be at least 64")
    if args.pixel_tolerance < 0 or args.pixel_tolerance > 12:
        parser.error("--pixel-tolerance must be between 0 and 12")
    if args.ink_threshold < 0 or args.ink_threshold > 255:
        parser.error("--ink-threshold must be between 0 and 255")
    for name in ("min_ink_recall", "min_ink_precision", "max_mean_error", "max_bounds_drift", "max_ink_ratio_delta"):
        value = getattr(args, name)
        if not 0 <= value <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    options = CheckOptions(
        reference_mode=args.reference_mode,
        reference=args.reference,
        reference_dir=args.reference_dir,
        diff_dir=args.diff_dir,
        compare_max_size=args.compare_max_size,
        pixel_tolerance=args.pixel_tolerance,
        ink_threshold=args.ink_threshold,
        min_ink_recall=args.min_ink_recall,
        min_ink_precision=args.min_ink_precision,
        max_mean_error=args.max_mean_error,
        max_bounds_drift=args.max_bounds_drift,
        max_ink_ratio_delta=args.max_ink_ratio_delta,
    )
    reports = [check_file(path, options) for path in paths]
    for report in reports:
        report.print()
    errors = sum(len(report.errors) for report in reports)
    warnings = sum(len(report.warnings) for report in reports)
    references = sum(report.reference_checked for report in reports)
    print(f"Checked {len(reports)} SVG file(s): {errors} error(s), {warnings} warning(s).")
    if references:
        print(f"Compared {references} SVG file(s) with PNG reference images.")
    else:
        print("No PNG reference images were compared.")
    print("A full-size rendered review remains mandatory for arrowhead clearance and semantic fidelity.")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
