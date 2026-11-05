# Training: Model, assistant, and agent - the system map

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**The model reads text and writes a response.**

**The assistant is the application you talk to.**

**An agent lets the model work in a loop: choose a step, see the result, choose again.**

Picture the model as a writer in a closed room. It sees only the pages passed in and can only answer in writing. Everything else happens outside. Below, we map the outside, follow one request through it, and see where information is kept.

## Three names, different roles

Here, **assistant** means the user-facing application. The terms overlap: an assistant can run an agent, and an agent can work without a chat window.

| Term | What it is | Example |
| --- | --- | --- |
| **Model** | A network of learned numbers, called **weights**, that turns input text into output text. | Writes an answer or a calculator request. |
| **Assistant** | The application you use. It connects the model to instructions, chat history, and tools. | A chat app that can use a calculator. |
| **Agent** | A system where the model picks each next step from earlier results, within limits the application sets. | A coding agent edits a file, runs tests, reads the failure, and picks the next fix. |

A **workflow** follows steps fixed in code, such as “search, then summarize.” An agent decides its steps as it goes. Both use models and tools; the difference is who picks the next step.

## What surrounds the model?

The **runtime** is the code that coordinates the work. Before each model call, it assembles the **context**, the pages passed into the room: everything the model sees this time, such as instructions, messages, tool descriptions, and results. Running the model on its context is **inference**.

A **tool** is a program the application can run, such as a calculator or a web search. A **tool call** is the model's written request to use one. The model cannot run the tool itself. The runtime decides whether to run it, runs it, and collects the result.

In the map, the outer box is the assistant. The dashed box groups the **agent**: the runtime, model, tools, and saved state working together in a loop. Your message enters through the interface. The runtime coordinates the calls, while the model chooses the next step. The purple arrow brings tool results back into context for the next model call. These are logical parts; they can run on different machines.

![assistant-system-map.svg](images/assistant-system-map.svg)

## A small example: who does the calculation?

Suppose you ask: **“What is 18 × 22? Use the calculator.”** Read the sequence diagram from top to bottom.

![calculator-message-flow.svg](images/calculator-message-flow.svg)

1. The runtime sends the model your question and a description of the calculator.
2. Instead of answering, the model replies with a tool call: `calculate(18, 22)`.
3. The runtime runs the calculator, which returns `396`.
4. The runtime calls the model again with `396` in the context, and the model writes the answer you see.

So the calculator does the arithmetic, the runtime runs it, and the model only asks for it. Nothing is retrained between the two calls: the same model just sees more text.

An agent repeats this loop as often as it needs, and it may switch tools, ask you a question, or finish. The runtime can also stop it at a limit, such as a maximum number of steps.

## Where does information live?

“The AI remembers” can mean three different places:

| Place | What it holds | Does it change while you chat? |
| --- | --- | --- |
| **Model weights** | Patterns learned in training. | No. Using the model does not change them. |
| **Context** | What the model sees on this call. | Yes. It grows with messages and tool results. Older parts may be trimmed or summarized. |
| **Saved state** | Chat history, notes, and files kept outside the model. | Yes, by code and tools. The model sees it only once it is copied into the context. |

If an assistant greets you by name next week, the model did not learn your name. The application saved it and put it back into the context. Better context, not new training, made the reply better.

## Check your understanding

A coding assistant says “the tests passed.” How do you know? **Look for the test tool's result.** The model's sentence is a claim. The test output is evidence, if it comes from this run and the answer reports it correctly.

In any AI application, find **the model, its context, the code that runs tools, and the stored state.** Then ask who picks the next step.

# Sources

- [Brown et al.: Language Models are Few-Shot Learners](https://arxiv.org/abs/2005.14165)
- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic: Tool use with Claude — client and server tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [OpenAI: Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents)
