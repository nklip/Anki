---
name: svg-creation
description: Create or edit source-native, novice-friendly diagrams in the relevant existing svg/ or images/ asset directory when precise layout, compact composition, readable text, reliable arrows, accessible metadata, repair-friendly XML comments, and strict comparison with a supplied PNG etalon matter. Use for standalone .svg illustrations and technical diagrams, not raster artwork or established code-generated icon systems.
---

# SVG Creation

Create maintainable SVG source and verify the rendered image, not only the XML.

Before running the validator outside the bundled Codex environment, install the operating-system and Node dependencies listed in [README.md](README.md#requirements).

## Prepare

- Resolve the output folder before creating directories. If the current working directory itself is named `svg` or `images`, use it directly. If the user names an existing SVG or a PNG etalon, place the SVG in that file's containing `svg/` or `images/` directory unless the user requests another location. Otherwise, find the domain-relevant existing directory named `svg` or `images` at or below the current directory.
- Treat `svg/` and `images/` as equivalent asset-directory boundaries. Never create an asset directory inside one that is already selected: in particular, do not create `svg/svg/`, `svg/images/`, `images/svg/`, or `images/images/`. Keep a recreated SVG beside its PNG etalon when practical so same-stem validation works automatically.
- If several candidate asset directories exist, infer the intended one from the referenced source, named topic, repository convention, or surrounding task. Ask only when those signals do not identify one safely. If none exists, create `<topic>/svg/` or `<topic>/images/` only when the topic and local repository convention make the choice clear.
- Inspect a few SVGs in the selected folder before choosing dimensions, typography, colors, or arrow conventions. Read [references/svg-folder-style.md](references/svg-folder-style.md) when matching or establishing its visual system.
- Establish a positive `viewBox`, a visible reading order, and a compact layout grid before placing detailed content. Reserve margins for titles, legends, labels, and arrowheads without creating a dominant unused region.

## Author maintainable SVG

- Use a self-contained `<svg>` with a matching `viewBox`, `<title>`, `<desc>`, `role="img"`, and `aria-labelledby` unless the target system imposes a different contract.
- Add concise XML comments before `<defs>` and every logical section. Comments should identify the section or explain non-obvious geometry, layer order, arrow endpoint, or repair constraint. Do not narrate every primitive.
- Give reusable definitions and important repair targets stable, descriptive IDs. Keep styles and shared definitions near the top.
- Keep the artwork source-native. Do not embed or link the PNG etalon with `<image>` to make a comparison pass.
- Give every `<use>` that instantiates a `<symbol>` explicit positive `width` and `height`; renderer defaults can otherwise expand the symbol across the viewport.
- Choose paint order deliberately. Keep text above all crossing geometry. Place each arrow shaft above or below non-text shapes according to the relationship it must show, then keep its arrowhead unobscured and separate from surrounding objects.
- Keep text as real `<text>`. SVG does not wrap text automatically: use explicit `<tspan x="..." dy="...">` lines, consistent line height, and adequate box padding. Avoid `foreignObject` for diagrams that need portable rendering.
- Escape XML-sensitive text and keep every final label inside the `viewBox`.

## Make the diagram teach

- Assume the viewer is learning the subject for the first time. The rendered diagram must be understandable without surrounding prose or access to its XML comments.
- State the lesson in the title or subtitle, make the starting point and reading direction obvious, and visibly connect each transformation, relationship, or sequence to its outcome.
- Explain domain terms, abbreviations, symbols, color meanings, or branch rules that a new learner cannot safely infer. Prefer short labels and a clear before/rule/after structure over dense explanatory paragraphs.
- Use empty space only to separate groups, establish hierarchy, or clarify routing. A large blank center, oversized panel, or loose canvas is a defect when it carries no meaning. Reflow the content, shorten routes, resize panels, or tighten the `viewBox`; do not add decorative filler merely to occupy space.
- Preserve one primary lesson per diagram. Supporting notes should resolve likely beginner questions rather than compete with the main flow.

## Prevent text collisions

- Size containers from the longest rendered line, including bold text and fallback fonts. Do not estimate from character count alone when exact placement matters.
- Use explicit `text-anchor` and consistent baselines. For multi-line labels, keep all lines centered or aligned to the same deliberate x-coordinate.
- Leave visible separation between text and borders, arrow shafts, arrowheads, neighboring labels, and the canvas edge. No part of an arrow may cross, touch, underline, cover, or otherwise overlap text in any form, including titles, labels, captions, legends, and text inside nodes.
- Recheck layout after any wording, font-size, font-family, or viewBox change.

## Build reliable arrows

- For precise box-to-box diagrams, prefer a separate shaft and triangular head. End the shaft at or slightly inside the triangle base so there is neither a gap nor a visible line protruding through the tip. Add a comment when the endpoint is intentionally hidden beneath the head.
- Mark a separately drawn shaft with `data-connector="true"` or a descriptive ID/class containing `arrow`, `connector`, `flow`, or `shaft`. The checker uses these hints to validate manual arrows that do not carry an SVG marker themselves.
- The shaft or path portion of an arrow may cross or overlap non-text objects when that overlap is necessary to communicate a relation, sequence, or order. Make the overlap visibly intentional through routing, contrast, dash pattern, or a concise XML comment. It must never overlap text.
- Apart from the controlled join with its own shaft, an arrowhead must not overlap any object. Its tip may meet a target boundary, but it must not enter the target shape, collide with another connector, or cover any text.
- For curved or reusable arrows, use a `<marker>` with a unique ID, positive viewport dimensions, explicit `viewBox`, `refX`, `refY`, `orient="auto"` or `auto-start-reverse`, and deliberate `markerUnits`. Ensure every `url(#...)` reference resolves.
- Account for stroke width and the head's forward extent when choosing the path endpoint. A path may continue across a non-text object when the intended relationship calls for it, while the head remains clear at its final destination.
- Never rely on a zero-length connector for orientation. Inspect heads at horizontal, vertical, and diagonal angles and near every canvas edge.

## Validate the final SVG

1. Run `python3 scripts/check_svg.py --strict path/to/file.svg`. When a same-stem PNG is beside the SVG, the checker automatically renders and compares them. Treat every mismatch warning as actionable.
2. If the etalon has another name or location, pass `--reference path/to/etalon.png`. For a reference-backed batch, use `--reference-mode required` and optionally `--reference-dir path/to/pngs` so a missing etalon fails validation.
3. On any visual mismatch, rerun with `--diff-dir path/to/temporary-output`, inspect the normalized render, reference, and difference PNGs, then repair the SVG. Read [references/reference-validation.md](references/reference-validation.md) whenever an etalon is supplied or the comparison reports a mismatch. Do not loosen thresholds merely to obtain a pass.
4. Render the SVG at its real aspect ratio in a browser or a capable SVG renderer. If the inspection tool cannot read SVG directly, render to PNG first and inspect that PNG. Do not trust a square or visibly cropped thumbnail.
5. Inspect the full image and zoom into every dense region. Confirm:
   - no text touches or overlaps other text, borders, arrow shafts, arrowheads, or canvas edges;
   - any arrow shaft crossing or overlapping a non-text object is intentional, readable, and necessary to show relation or order;
   - every arrowhead is present, aligned, unclipped, pointed in the intended direction, joined cleanly to its shaft, and free from overlap with other objects;
   - connector routing and layer order remain understandable;
   - no large unused region dominates the composition unless that space has an explicit grouping or sequencing purpose;
   - a first-time learner can identify the subject, starting point, reading order, rule or relationship, and outcome without external explanation;
   - comments make the section or fragile geometry easy to locate for a quick fix.
6. After any correction, rerun the strict check and render again. Do not deliver based on source inspection alone or on aggregate comparison metrics.

The checker estimates transformed single-line and explicit `<tspan>` text bounds, checks marker-ended and labeled manual connector paths, rejects embedded raster artwork, and compares a supplied PNG at normalized dimensions. Treat `possible text/connector overlap`, ink-recall, ink-precision, pixel-error, ink-delta, and content-bounds warnings as actionable. Exact font metrics, arrowhead-to-boundary clearance, and semantic correctness still require full-size rendered inspection.
