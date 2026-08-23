#!/usr/bin/env python3
"""Structural and heuristic checks for maintainable SVG diagrams."""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


URL_REF_RE = re.compile(r"url\(\s*#([^\s)]+)\s*\)")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
CSS_DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+)")


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


def parse_style_attribute(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    return {key.strip(): item.strip() for key, item in CSS_DECL_RE.findall(value)}


def parse_styles(root: ET.Element) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    for element in root.iter():
        if local_name(element.tag) != "style" or not element.text:
            continue
        for selectors, body in CSS_RULE_RE.findall(element.text):
            declarations = {key.strip(): value.strip() for key, value in CSS_DECL_RE.findall(body)}
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
        if property_name in current.attrib:
            return current.attrib[property_name]
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
        current = parents.get(current)
    return None


def has_transform(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    current: ET.Element | None = element
    while current is not None:
        if current.attrib.get("transform"):
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


class Report:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def print(self) -> None:
        print(self.path)
        for item in self.errors:
            print(f"  ERROR: {item}")
        for item in self.warnings:
            print(f"  WARN:  {item}")
        if not self.errors and not self.warnings:
            print("  OK: structural checks passed; rendered-image review is still required")


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


def collect_text_boxes(
    root: ET.Element,
    parents: dict[ET.Element, ET.Element],
    styles: dict[str, dict[str, str]],
    report: Report,
) -> list[TextBox]:
    boxes: list[TextBox] = []
    complex_count = 0
    for element in root.iter():
        if local_name(element.tag) != "text":
            continue
        if any(local_name(child.tag) == "tspan" for child in element):
            complex_count += 1
            continue
        if has_transform(element, parents):
            continue
        label = " ".join("".join(element.itertext()).split())
        x = number(element.attrib.get("x"))
        y = number(element.attrib.get("y"))
        if not label or x is None or y is None:
            continue
        font_size = number(inherited_property(element, "font-size", parents, styles)) or 16.0
        font_weight = inherited_property(element, "font-weight", parents, styles) or "normal"
        width = estimate_text_width(label, font_size, font_weight in {"bold", "600", "700", "800", "900"})
        anchor = inherited_property(element, "text-anchor", parents, styles) or "start"
        if anchor == "middle":
            left = x - width / 2
        elif anchor == "end":
            left = x - width
        else:
            left = x
        boxes.append(TextBox(label=label[:80], box=(left, y - 0.85 * font_size, left + width, y + 0.25 * font_size)))
    if complex_count:
        report.warn(f"{complex_count} text element(s) use <tspan>; inspect their line spacing in the render")
    return boxes


def boxes_overlap(first: TextBox, second: TextBox) -> bool:
    ax1, ay1, ax2, ay2 = first.box
    bx1, by1, bx2, by2 = second.box
    overlap_x = min(ax2, bx2) - max(ax1, bx1)
    overlap_y = min(ay2, by2) - max(ay1, by1)
    if overlap_x <= 0 or overlap_y <= 0:
        return False
    smaller_width = max(1.0, min(ax2 - ax1, bx2 - bx1))
    smaller_height = max(1.0, min(ay2 - ay1, by2 - by1))
    return overlap_x / smaller_width > 0.20 and overlap_y / smaller_height > 0.30


def check_text(
    root: ET.Element,
    viewbox: tuple[float, float, float, float] | None,
    report: Report,
) -> None:
    parents = {child: parent for parent in root.iter() for child in parent}
    styles = parse_styles(root)
    boxes = collect_text_boxes(root, parents, styles, report)
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
            references.update(URL_REF_RE.findall(value))
            if local_name(key) == "href" and value.startswith("#"):
                references.add(value[1:])
    for reference in sorted(references - ids.keys()):
        report.error(f"unresolved reference #{reference}")


def check_markers(root: ET.Element, report: Report) -> None:
    referenced_markers: set[str] = set()
    markers: dict[str, ET.Element] = {}
    for element in root.iter():
        if local_name(element.tag) == "marker" and element.attrib.get("id"):
            markers[element.attrib["id"]] = element
        for key, value in element.attrib.items():
            if local_name(key) in {"marker-start", "marker-mid", "marker-end"}:
                referenced_markers.update(URL_REF_RE.findall(value))

    for marker_id in sorted(referenced_markers):
        marker = markers.get(marker_id)
        if marker is None:
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


def check_file(path: Path) -> Report:
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
    check_markers(root, report)
    check_text(root, viewbox, report)
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
    args = parser.parse_args()

    reports = [check_file(path) for path in iter_svg_paths(args.paths)]
    if not reports:
        parser.error("no SVG files found")
    for report in reports:
        report.print()
    errors = sum(len(report.errors) for report in reports)
    warnings = sum(len(report.warnings) for report in reports)
    print(f"Checked {len(reports)} SVG file(s): {errors} error(s), {warnings} warning(s).")
    print("A browser or rendered-PNG visual review is mandatory for arrow/text overlap and arrowhead clearance.")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
