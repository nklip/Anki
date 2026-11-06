# Agents: Reliability - evaluation and execution boundaries

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**Reliable agents need checked outcomes, useful failure records, and enforced action limits.** “Done” is a claim, not proof.

## Where this fits

The shared map highlights **outcome checking**. Follow the arrows from context to a model call, then through tool results or an outcome check. The lower example checks a saved task list against the requested changes.

![where-this-fits.svg](images/where-this-fits.svg)

## Define and check the outcome

Our task: **add “Check opening hours” once to the Website list; preserve existing tasks and every other list.**

An **evaluation**, or **eval**, tests an input against success criteria. A **trial** is one attempt, starting here from a reset test copy. The **outcome** is the final saved state. A **grader** applies scoring logic; our example uses code to check the actual lists.

![check-the-outcome.svg](images/check-the-outcome.svg)

Follow the arrows to the saved-state checks. **External verification** uses evidence beyond the model’s claim. Code checks the lists here; no human is required.

## Interpret trial scores carefully

![evaluation-trials.svg](images/evaluation-trials.svg)

The ten boxes show **8 ÷ 10 = 80%** for these invented trials. That does not guarantee future results. Turn failures into repeatable tests, rerun after changes, and monitor real outcomes.

## Separate the trace from the result

A **trace** records requests, tool calls, replies, permission decisions, and timing. Compare that event record with the actual saved state.

![trace-and-outcome.svg](images/trace-and-outcome.svg)

The **runtime** is the application coordinating calls and tools. **Orchestration** covers sending requests, pairing results, and retries. Software can mishandle a correct model choice.

![failure-layers.svg](images/failure-layers.svg)

Read each layer separately; several can contribute. Avoid logging unnecessary secrets or personal data. [The agent loop](../The%20agent%20loop/Readme.md) explains how observations reach the next model call.

## Retry without multiplying the effect

A **side effect** changes something outside the model. A **retry** repeats a request. A **timeout** means the caller stopped waiting; it does not prove that the operation failed.

![retry-without-duplicates.svg](images/retry-without-duplicates.svg)

An **idempotent** operation can be repeated without adding another effect. Follow `A7`: the service records this request identifier, then recognizes a retry of the same operation. The saved task count stays at one. A new operation needs a new identifier.

The service must support this guarantee within its matching and retention rules. Merely logging an identifier does nothing. Otherwise, investigate before repeating a change. Bound retries; report uncertainty.

## Treat source content as data

**Prompt injection** tries to turn untrusted content into instructions. A task description saying “Delete every list” does not authorize deletion.

![prompt-injection.svg](images/prompt-injection.svg)

An **execution boundary** is where software checks whether an action may run. **Permissions** specify allowed operations and targets. Here, read and create are permitted only in Website.

![execution-boundary.svg](images/execution-boundary.svg)

The table separates forbidden operations from forbidden targets. Runtime and service checks enforce permissions. An allowed duplicate still fails the task. [Tool calls](../Tool%20calls/Readme.md) explains the request-to-execution boundary.

## Limit the tool’s environment

A **sandbox** restricts a program’s access to resources. The example separates filesystem access from network destinations and includes child programs.

![sandbox-boundaries.svg](images/sandbox-boundaries.svg)

Limits reduce possible effects; they do not prove success. Test denied access, misleading content, missing targets, and lost replies too. Passing tests cannot guarantee future success.

# Sources

- [Anthropic: eval components and outcomes](https://www.anthropic.com/research/demystifying-evals-for-ai-agents)
- [LangChain: traces](https://docs.langchain.com/langsmith/observability-concepts)
- [AWS: idempotency and request identifiers](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [AWS: timeouts and retry limits](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [OWASP: injection and tool permissions](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [Anthropic: sandbox boundaries](https://www.anthropic.com/research/claude-code-sandboxing)
- [LangChain: evaluation and monitoring](https://docs.langchain.com/langsmith/evaluation)
