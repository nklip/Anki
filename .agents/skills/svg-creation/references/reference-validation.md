# PNG Etalon Validation

Use this workflow whenever a PNG, screenshot, or other raster etalon defines how the SVG should look. The automated comparison is a gate before manual review, not a replacement for it.

## Run the strict comparison

A same-stem PNG beside the SVG is discovered automatically:

```bash
python3 scripts/check_svg.py --strict images/example.svg
```

Point to a differently named etalon explicitly:

```bash
python3 scripts/check_svg.py --strict --reference images/original.png svg/example.svg
```

Require every SVG in a batch to have a same-stem reference:

```bash
python3 scripts/check_svg.py --strict --reference-mode required --reference-dir images svg/
```

The reference must be a readable PNG. The checker fails rather than silently skipping comparison when `--reference-mode required` is active or an explicit reference cannot be read.

## Diagnose a mismatch

Write comparison artifacts outside the final asset folder:

```bash
python3 scripts/check_svg.py --strict --diff-dir /tmp/example-svg-diff images/example.svg
```

Inspect all three generated files:

- `*.rendered.png` is the normalized SVG render.
- `*.reference.png` is the normalized PNG etalon.
- `*.difference.png` highlights missing reference ink in magenta and extra SVG ink in cyan. Pale areas indicate smaller antialiasing or color differences.

Start with the largest contiguous difference regions. Check missing arrowheads and shafts, endpoints crossing target boundaries, displaced text, wrong font size or weight, clipped content, canvas margins, fill and stroke colors, and layer order. Re-run the comparison after each coherent repair.

## Understand the gates

The default comparison evaluates several independent signals so one aggregate score cannot hide an important defect:

- **Ink recall** finds reference content absent from the SVG, especially missing lines, arrowheads, text, and shapes.
- **Ink precision** finds extra or displaced SVG content.
- **Mean pixel error** catches broad color, fill, antialiasing, and placement differences.
- **Ink amount delta** catches diagrams that are materially sparser or denser than the etalon.
- **Content-bounds drift** catches shifted edges, clipping, and incorrect outer margins.
- **Aspect ratio and canvas checks** catch stretched or incorrectly sized recreations before pixel scoring.

A small pixel-radius tolerance allows normal rasterization differences while retaining strict layout checks. Keep the defaults for ordinary work. Change a threshold only when the etalon has a documented renderer-specific difference, record why, and still inspect the difference image. Never raise tolerances simply to silence a failure.

The checker needs Node.js with `sharp` to render both images consistently. It automatically looks for the bundled Codex workspace runtime. If rendering is unavailable, load the workspace dependencies or set `SVG_CHECK_NODE` and `NODE_PATH`; do not treat a skipped comparison as a pass.

## Complete manual review

Comparison metrics cannot determine whether an arrow points to the correct semantic target or whether a tiny arrowhead crosses a boundary in a misleading way. Inspect the SVG and etalon side by side at full size, then inspect every connector endpoint at 8×–10× zoom. Reject a narrow shaft tail visible after a tapered nose, a gap before the target, or a nose that enters the target. When a shared marker has one bad join, review every use and every orientation rather than repairing only the reported example. Do not embed the etalon with `<image>`: the final file must remain editable, source-native SVG.
