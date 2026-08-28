# SVG Creation Skill

This skill creates maintainable SVG diagrams and validates their structure, connector geometry, text placement, and visual fidelity against a PNG etalon when one is available.

## Requirements

Install these components on the machine that runs `scripts/check_svg.py`:

| Component | Required version | Used for |
| --- | --- | --- |
| Python | 3.10 or newer | All structural and geometry checks. The script uses only the Python standard library; no PyPI packages are required. |
| Node.js | 20.9 or newer | Rendering SVG and PNG files for strict etalon comparison. |
| `sharp` Node package | 0.35.x tested | Consistent SVG/PNG rendering, resizing, and difference images. It must be resolvable by Node.js. |
| Matching system fonts | The font families referenced by the SVG | Stable text size, wrapping, and pixel comparison. Many repository diagrams use `Arial, Helvetica, sans-serif`; install the exact font when strict fidelity matters. |
| SVG-capable viewer | Current browser or desktop SVG viewer | Mandatory full-size manual inspection after automated validation. |

Node.js and `sharp` are required whenever the checker discovers a same-stem PNG, receives `--reference`, or runs with `--reference-mode required`. A structural-only run with `--reference-mode off` needs only Python.

The tested `sharp` 0.35.4 package declares Node.js 20.9 or newer. Prebuilt `sharp` packages normally include the required image libraries. If the package must be compiled from source on an unsupported platform, install a C/C++ build toolchain and libvips 8.18.6 or newer as required by that `sharp` release.

On Linux, ensure font discovery works and install the fonts named by the SVG. `fontconfig` is commonly required for this. A fallback such as Liberation Sans may keep text readable but can still create strict comparison differences when the etalon used Arial.

## Install and verify

Install Python and a supported Node.js release using the operating system's package manager or the official installers. Then make `sharp` available from the directory where the checker runs, for example:

```bash
npm install --no-save --package-lock=false sharp@0.35.4
```

Verify the runtime before validating diagrams:

```bash
python3 --version
node --version
node -e "const sharp = require('sharp'); console.log(sharp.versions)"
python3 scripts/check_svg.py --help
```

If Node.js or its modules are installed in nonstandard locations, configure them explicitly:

```bash
export SVG_CHECK_NODE=/absolute/path/to/node
export NODE_PATH=/absolute/path/to/node_modules
```

The checker automatically detects the Node.js and `sharp` runtime bundled with Codex under `~/.cache/codex-runtimes/codex-primary-runtime/dependencies`. When that runtime is present and readable, a separate system installation is not required.

## Validate an SVG

Run the strict check from the skill directory. A same-stem PNG beside the SVG is compared automatically:

```bash
python3 scripts/check_svg.py --strict /path/to/example.svg
```

See [references/reference-validation.md](references/reference-validation.md) for explicit references, required-reference batches, difference images, and interpretation of comparison metrics.
