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
from typing import Iterable, Sequence


URL_REF_RE = re.compile(r"url\(\s*#([^\s)]+)\s*\)")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
CSS_DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;]+)")
TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
PATH_TOKEN_RE = re.compile(r"[A-Za-z]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


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


Matrix = tuple[float, float, float, float, float, float]
Point = tuple[float, float]


IDENTITY_MATRIX: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


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
        if is_definition_element(element, parents):
            continue
        if any(local_name(child.tag) == "tspan" for child in element):
            complex_count += 1
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
    if complex_count:
        report.warn(f"{complex_count} text element(s) use <tspan>; inspect their line spacing in the render")
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


def path_segments(raw: str) -> list[tuple[Point, Point]]:
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
        if count is None or index + count > len(tokens) or any(item.isalpha() for item in tokens[index : index + count]):
            break
        values = [float(item) for item in tokens[index : index + count]]
        index += count
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
            segments.append((start, end))
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
            for property_name in ("marker-start", "marker-mid", "marker-end")
        ]
        if not any(value and URL_REF_RE.search(value) for value in marker_values):
            continue

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
            raw_segments = path_segments(element.attrib.get("d", ""))

        matrix = cumulative_matrix(element, parents)
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
        for connector in connectors:
            clearance = connector.stroke_width / 2 + 1.0
            if segment_polygon_distance(connector.start, connector.end, text_box.polygon) <= clearance:
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
            references.update(URL_REF_RE.findall(value))
            if local_name(key) == "href" and value.startswith("#"):
                references.add(value[1:])
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
    check_symbol_uses(root, report)
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
