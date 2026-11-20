# Complex mode (also called article mode)

Use complex mode, also called article mode, for comprehensive explanations, mechanisms with multiple stages, or explicit step-by-step teaching. Both names select the same requirements. For revisions, follow the shared mode-selection rule. Use `--mode complex` for explicit validation.

## Outcome

Create an article that starts with the core mental model and then expands into the details a beginner needs.

Requirements:

- Follow the shared order: title, one standalone upward navigation line without a list marker, then teaching content, separated by blank lines with no other intervening content. Omit `# Front` and `# Back`; end with `# Sources`. Do not generate HTML comments in article prose, including mode metadata comments. Fenced code examples and XML comments in separate SVG assets are unaffected.
- Articles have no default character limit. A requested limit applies to the Markdown between the back link and the final `# Sources` heading, including the contents list, headings, code, image references, and review questions and answers.
- Include at least **two** local SVGs or images with different teaching purposes, such as structure plus behavior, or before-state plus after-state.
- If the article teaches a step-by-step process, give each process step a heading and link that step's own local `.svg` from the sibling `images/` directory immediately below its heading.
- Begin the teaching content immediately after the navigation line with the direct answer and a short roadmap of the explanation. For a versioned feature, the first nonblank line after navigation must follow the shared bold feature-and-release rule and pass `--require-version-lead`.
- Introduce terminology and the static model before describing state changes or edge cases.
- Prefer this teaching order when it fits: core idea → vocabulary → structure → process → example → limitations or misconceptions → concise summary.

## Numbered sections and lists

After the introduction, add an ordered contents list with one link per numbered `##` teaching section. Number these headings consecutively from 1. Use each section title as the link text and its numbered heading's Markdown anchor as the target. Keep the opening title, nested `###` subsections, `## Check your understanding`, and `# Sources` outside the numbered outline.

Within a section, use a numbered list when the reader should follow stages, actions, or diagram elements in order. Start each list at 1. For example, the [fine-tuning article](../../../../ai/Training.%20Supervised%20fine-tuning/Readme.md) walks the reader through one diagram with three short bold labels, **Predict**, **Score**, and **Adjust**. Use paragraphs for a continuous explanation.

An article with two teaching sections has two contents entries.

```markdown
# How a queue works

<sub>[Back to System Design](../Readme.md#content)</sub>

A queue serves items in arrival order. Follow two tickets as they enter and leave.

1. [Where tickets enter](#1-where-tickets-enter)
2. [Which ticket leaves first](#2-which-ticket-leaves-first)

## 1. Where tickets enter

New tickets join the back. In the diagram, B arrives while A is waiting.

![queue-arrival.svg](images/queue-arrival.svg)

## 2. Which ticket leaves first

The next ticket leaves from the front. Once A leaves, B moves to the front.

![queue-departure.svg](images/queue-departure.svg)

## Check your understanding

1. A and B are waiting. Where does a new ticket C go?

   <details>
   <summary>Answer</summary>

   C joins the back, behind B.

   </details>

2. Once A leaves, which ticket will be served next, and why?

   <details>
   <summary>Answer</summary>

   B is next because it arrived before C and is now at the front.

   </details>

# Sources

- [Descriptive source title](https://example.com/source)
```

For a process article, each step should state:

1. The state before the step.
2. The trigger.
3. What changes.
4. The state after the step.
5. Why the step matters.

Choose step-heading levels from the article's hierarchy. A main-section step keeps its article number, for example `## 2. Step 1 — Read the value` after an overview. When a process belongs inside a broader `##` section, use `### Step 1 — Clear action`, `### Step 2 — Clear action`, and so on beneath it. Keep steps in the same sequence at the same level, including steps with bold labels.

Both forms require each step's own `.svg` reference. Main-section steps may have `###` detail subsections; named sub-items within any `###` subsection, including a nested step, may use `#### **Named sub-item**`, following the shared heading rule. A `Use case:` prefix is optional.

Keep closely related details together. Do not hide the main flow beneath tuning options, historical notes, or implementation trivia.

## Review questions

Place the unnumbered `## Check your understanding` section immediately before `# Sources` in every article. Omit it from numbered lists, including the contents. Write at least one distinct question for each preceding `##` teaching section, in section order. Ask about the idea or decision that section taught. Add more questions where a section teaches several important ideas. A subsection's material can be tested through its parent.

Number the questions from 1. Leave each prompt visible and nest a closed `<details>` block beneath it with the exact label `<summary>Answer</summary>`. Indent the block to the start of the question text and keep the blank lines shown in the queue example. Favor questions that ask the reader to apply the lesson, with a short answer explaining why. When revising a `Self-check` section, carry its questions and answers into the review and fill gaps in coverage.

During final review, match each teaching heading to a question that a reader could answer from that section. The validator checks section numbering, contents links, and the minimum number of review prompts. Several questions on the same section can pass a count while leaving another section untested.

For a request such as “under 5K,” “less than 10k,” or “under 15k chars,” pass the requested limit to the validator. Each `k` means 1,000 characters. “Under 10k” allows up to 9,999 teaching-body characters. Omit the option for an article without a requested limit.

```bash
python3 scripts/check_anki_card.py --mode complex --under-chars 10k path/to/card.md
```

The validator also confirms the minimum visual count and checks SVG presence in both main-section steps and `### Step …` subsections. It reports orphaned level-three steps and step headings at deeper levels, including when their labels are wrapped in `**` or `__`. A fenced image example or an image in a later step, peer section, or parent section does not satisfy a step's diagram requirement. Manually confirm that every step diagram actually explains that step and sits immediately under its heading.
