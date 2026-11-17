# Preserve lesson formatting and normal Anki framing

## Establish the reference

Open the actual source in VS Code's Markdown preview. Inspect effective workspace/user `markdown.preview.*`, `markdown.styles`, the active theme, and enabled extensions that contribute Markdown rendering, styles, scripts, or math. Record the VS Code version and these rendering inputs in the local render fingerprint. Do not hardcode the author's current theme for future publications.

The reliable export is the **rendered preview DOM plus its effective styles and assets**. The installed extension's render command can also supply HTML: inside a VS Code extension host, open the source as a `TextDocument`, activate `vscode.markdown-language-features`, then call:

```javascript
const document = await vscode.workspace.openTextDocument(sourceUri);
await vscode.extensions.getExtension('vscode.markdown-language-features').activate();
const html = await vscode.commands.executeCommand('markdown.api.render', document);
```

This is an internal command: verify the installed implementation before relying on it. It returns body HTML, **not a complete styled export**. It is not a terminal command or a Node module. Pass the document, not just its text, so resource-specific settings and links retain context. Use a temporary extension-host utility if no existing export facility is available; do not permanently install an extension or change the workspace just to export.

For styles, inspect the live preview or the installed Markdown extension's `media/markdown.css`, `media/highlight.css`, effective `markdown.styles`, and extension-contributed `markdown.previewStyles`. Include applicable extension output such as math styles/fonts. Resolve `--vscode-*` and `--markdown-*` variables to the actual preview values, including font family, foreground/background, links, code, table borders, and syntax token colors. Use those values to preserve intentional formatting and code highlighting; adapt ordinary foreground/background colors to Anki's theme as described below. Record the preview's font sizes and line heights to preserve their relative proportions, then adapt them to Anki's inherited base. Do not copy the preview's fixed base size. Body HTML plus default browser styling is not sufficient.

If the current tooling cannot extract the reference, prepare the remaining publication work and report what is missing. Do not silently substitute a generic Markdown theme or claim a matching preview without inspection. A markdown-it renderer with highlighting can be used only when its options/extensions and resulting layout have been compared with the actual VS Code reference.

## Make a portable HTML fragment

Use a DOM parser and a CSS parser when transforming exports. Do not split HTML with regex or identify Markdown headings without accounting for fenced code and comments. Render the whole source before extracting sections so reference links and footnotes resolve. Keep IDs and associated footnote targets valid on each rendered side; copy necessary footnote definitions to a side when its content references them.

By default, take the Front from the source's first level-one (`#`) heading in both simple and article modes. Identify the real Markdown heading outside fenced code and HTML comments, and use its rendered text without the `#` marker or heading styling. Do not substitute the folder name. For example, `# Amazon CloudFront` produces Front `Amazon CloudFront`. An explicit user request for a different Front takes precedence. Structural labels such as `Front`, `Back`, and `Sources` are not topic titles; if the source lacks a topic heading, resolve a meaningful title before publishing.

Both current modes use the same source layout and field mapping:

| Source | Question field | Answer field |
| --- | --- | --- |
| Simple card | Standard text from the first level-one topic heading by default | Rendered teaching body after navigation, including Sources; no repeated title |
| Article | Standard text from the first level-one topic heading by default | Rendered teaching body after navigation, including Sources; no repeated title |

The Front uses Anki's ordinary text presentation: no exported heading element, heading rule, font-size/font-weight overrides, preview page wrapper, or preview padding. HTML-escape the question/title and let the existing template style it. Preserve essential question content such as symbols, code, or an image when plain text would lose meaning; this is not permission to import title/page styling. The template may show the Front once above its normal divider on the answer side. Keep that standard behavior; omit only the duplicate article title inside the Back field.

Remove standalone repository `Back to …` navigation and the opening title that supplied the Front. Current simple cards and articles have no Front/Back boundary headings. Retain later headings and the full answer content, including the topic's natural use in explanatory prose. Retarget any links to the removed title's anchor to the Back wrapper. Preserve meaningful heading anchors, lists, tables, inline HTML such as `<sub>`, code spans, highlighted fenced-code tokens, and diagrams. Do not turn an article into a screenshot or flatten tables/code to text. Preserve established destination field names on existing notes while applying the current Front-selection rule; a previously published question does not itself establish a user override.

### Legacy simple sources

For an older source with one complete, ordered `# Front` / `# Back` pair outside fenced code and comments, the teaching body is the content after `# Back`, including Sources. The default Anki Front still comes from the opening topic title; use the old question only when the user explicitly requests it. Render the full original source before extracting its answer so shared reference links and footnotes remain available. Prepare a temporary Markdown copy with the original title and navigation followed directly by the teaching body; retain any reference definitions needed by that body. Validate it in simple mode using the original source path as the base for navigation and media links, for example `validate_text(normalized_markdown, original_source_path, "simple")`. Do not silently treat incomplete, duplicated, or misordered boundaries as a valid legacy layout. Publication alone does not rewrite the source file.

### Scope the rendered answer

Wrap the Back in a uniquely named class, such as `.anki-publish-<sourceUUID>-back`, with its scoped styles. Include all answer styles on the Back itself, since a back template may omit FrontSide. Example shape:

```html
<style>
/* Actual rules come from the verified preview export. */
.anki-publish-example { font-size: inherit; color: inherit; background-color: transparent; text-align: left; margin: 0; padding: 0; width: auto; max-width: none; }
.anki-publish-example img { max-width: 100%; height: auto; }
.anki-publish-example pre { overflow-x: auto; }
</style>
<div class="anki-publish-example">…rendered content…</div>
```

Scope CSS with a parser, including comma-separated selectors and rules nested in media queries. Rebase `html`, `body`, and `:root` rules to the wrapper; namespace keyframes, font families, and IDs where necessary. Do not let selectors such as `body`, `.card`, `pre`, or `table` leak outside this note's wrapper. Inline computed styles are an alternative for static content, but inspect pseudo-elements, list markers, math, and responsive behavior that computed-style copying can lose.

### Inherit Anki's base text size

Inspect the destination note type's CSS and the actual answer container. Normal Anki size means that note's inherited size, not a universal constant. The publication wrapper and ordinary body text must inherit it. Do not export a fixed preview base such as 14px, replace it with a hardcoded 20px, use `rem` tied to the webview's root, or visually scale the card with zoom/transforms. A later note-type text-size change should flow through to the lesson automatically.

Audit descendants as well as the wrapper: computed-style exports commonly put the fixed size on every paragraph, list item, table cell, code element, and syntax-token span. Convert ordinary text to inherited size. Keep a relative heading hierarchy and intentional subscript/superscript proportions, ensuring nested emphasis or links inherit the heading rather than shrinking back to body size. Inline code and fenced-code text use the same base size by default; retain their monospace font and highlighting. Preserve SVG bytes and SVG-internal text sizes.

For a computed-style export, capture each element's **original** computed font size before changing anything. Normalize ordinary text and code to inherited size even if the preview made them smaller. Reserve differing ratios for intentional hierarchy such as headings and subscripts/superscripts: a size equal to its parent's becomes `inherit`; an intentional difference becomes `original child size / original parent size` in `em`. The outer wrapper always inherits Anki's base. Example: a 21px heading within a 14px preview becomes `1.5em`, and its 21px child span inherits rather than receiving another `1.5em`. Account for unstyled intermediary wrappers using their inherited original size. Avoid compounding ratios down nested elements.

Convert fixed computed line heights to unitless ratios using each element's original size (22.4px / 14px becomes `1.6`), or use a verified inherited/normal line height. Removing font-size alone while leaving a small fixed line-height can crowd or overlap larger text. Preserve deliberate zero line-height for subscripts/superscripts and inspect them. If a font shorthand or stylesheet rule still supplies a fixed size, adapt it with a CSS parser or remove it only after preserving its other intended properties.

Verify computed ordinary text sizes against the actual Anki base at a representative paragraph, list item, table cell, inline code, fenced code, and nested token. Also test a different temporary base in an isolated preview to establish inheritance without changing Anki's shared styling. Preserve heading proportions, readable line spacing, and working image/table/code overflow. Use a fixed base size only if the user explicitly requests it.

### Keep Anki's normal top and side spacing

The existing Anki template and reviewer styles own the outer card frame. Keep their question placement, `{{FrontSide}}`, answer divider, and left/right margins unchanged by default. Do not use field CSS targeting `body`, `.card`, `#qa`, `#answer`, or `.back-left` to hide the top section or zero the page margins. Do not insert marker-gated shell overrides for ordinary publication.

Remove only the **extra spacing imported from the Markdown preview**: its outer `html`/`body` padding, margins, centered page width, and maximum-width constraint. Set the Back's own publication wrapper to zero additional margin/padding and natural width; this lets the normal Anki margins remain visible. Keep meaningful inner spacing in lists, code blocks, tables, blockquotes, and diagrams, along with the lesson's existing typography and code colors. A request about the top or side spacing does not authorize stripping the article's inner formatting.

Inspect every affected template. For Basic, the expected result is the ordinary question at the top, the ordinary answer divider, then the article body without a second title, inset by Anki's normal side margins. Never hide all headings or shrink the card to conceal text. Apply a custom shell layout only when explicitly requested and separately assessed for every affected card, especially reverse cards; preserve shared templates.

Keep readable text selectable. Preserve code whitespace and tokens; use a usable horizontal scroll region for long code/tables. Preserve image aspect ratios. Resolve CSS variables rather than leaving dependencies on VS Code. Do not include editor selection decorations, scroll-sync placeholders, CSP banners, VS Code bridges/scripts, or editor-specific URLs. Remove executable source HTML and event handlers; pre-render math or Mermaid as portable HTML/SVG with required assets, then inspect the result. Do not add Anki-side JavaScript merely to render ordinary Markdown.

### Let text follow Anki's day/night colors

Ordinary HTML text must inherit Anki's foreground, and its outer wrapper must be transparent so Anki supplies the page background. Audit all descendants: remove fixed preview colors from paragraphs, headings, emphasis, lists, table cells, and other ordinary text containers, not just the wrapper. Remove fixed `text-decoration-color` and text-fill overrides so decorations follow `currentColor`. Let links use Anki's link styling or a verified theme-aware link variable with an inherited fallback. Do not replace the exported black/white palette with another fixed day/night palette.

Keep intentional code highlighting readable as a complete foreground/background pair. If retaining a preview's syntax-token colors, retain its matching backdrop too: a translucent light code background may need its original opaque, composited color to keep black punctuation or dark tokens legible over Anki's dark page. This also applies to tinted inline-code text. Alternatively use verified corresponding day/night code palettes. Preserve monospace fonts, whitespace, sizing, and syntax emphasis; do not flatten token colors indiscriminately.

This default adapts text and the backgrounds needed for readable text only. Preserve image/SVG bytes and colors, including diagram labels; do not apply inversion, filters, or broad recoloring selectors to media. Keep shared templates and Anki's global theme settings untouched. Verify ordinary text, links, inline code, and highlighted code in both modes using the installed app's theme classes/styles (Anki desktop uses `nightMode` on the card). A text-color-only refresh must transform the current stored fields, preserve text and non-color formatting, and avoid regenerating titles or overwriting later user edits.

If an existing template strips HTML with `{{text:Field}}`, runs incompatible transformations, or overrides the intended styles, report the template conflict; do not silently convert the note type or edit shared templates.

## Media and links

Resolve every asset relative to the original Markdown or stylesheet that referenced it. Include Markdown images, raw HTML `src`/`srcset`, CSS `url()` and `@import`, fonts, math assets, and dependencies inside SVGs. Keep the source images unchanged. If portability needs a converted derivative, create it as a publication artifact and visually compare it.

Store flattened Anki media names such as `anki-publish-<full-sha256>.svg`; use the actual returned filename from `storeMediaFile`, and verify with `retrieveMediaFile` and a byte hash. Reuse identical bytes without writing again. Never overwrite a basename that may be used by another note, and never delete old media during a refresh. Rewrite all references to the verified local filenames, including nested asset dependencies. CSS/font files referenced only by templates may need Anki's underscore naming convention; prefer field-contained CSS and document any template media explicitly.

No `file://`, `vscode-webview://`, absolute local paths, repository-relative media paths, or temporary preview URLs may remain in published content. Preserve external source links. Convert local document/navigation links to a verified repository web URL only when the remote URL and target revision/path are known; otherwise resolve the destination deliberately, without inventing a URL. Keep same-document anchors working. Remote teaching images must be localized when authorized and downloadable; otherwise report that the offline render is incomplete. Never silently drop an image.

## Visual acceptance

Inspect a local preview composed with the actual front/back templates and shared CSS, then Anki Browse → Preview after publishing. Confirm the Front is ordinary text, the template's top question and divider remain, and the Back field does not add a second article title. Check both horizontal edges at wide and narrow widths: Anki's normal margins remain, with no additional export gutters or page-width constraint, while inner code/table/list spacing remains. Confirm a different note using the same template is unaffected by the scoped rules. Compare the Back's lesson styling at similar widths with VS Code: headings, fonts, emphasis, tables, fenced-code highlighting, link targets, SVG/PNG legibility, and any math. In day and night previews, verify that ordinary text follows Anki, links remain readable, and code tokens contrast with their backdrop; images must keep their original colors. Check an article near the middle and end, not just its opening. Confirm no hidden overflow clips content and no image relies on the source checkout still being available.

Pixel identity across different webviews/operating systems is not assumed. Report concrete rendering differences and fix material ones before claiming the requested appearance. Re-read content and review-state snapshots after any fix.

## Primary references

- [VS Code Markdown preview and settings](https://code.visualstudio.com/docs/languages/markdown)
- [VS Code render command implementation](https://github.com/microsoft/vscode/blob/main/extensions/markdown-language-features/src/commands/renderDocument.ts)
- [VS Code Markdown preview renderer](https://github.com/microsoft/vscode/blob/main/extensions/markdown-language-features/src/preview/documentRenderer.ts)
- [Anki HTML and styling](https://docs.ankiweb.net/templates/styling.html)
- [Anki media](https://docs.ankiweb.net/media.html)
