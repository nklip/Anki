# Artificial Intelligence
<sub>[Back to Anki Flashcards](../README.md)</sub>

Anki-ready cards on model training, transformer internals, inference, retrieval, and agent runtimes, each with its own teaching diagrams.

Every card lives in its own folder as `Readme.md`, with its diagrams in a sibling `images/` directory.

## Content

### Training

 * [Training. Model, assistant, and agent](./Training.%20Model%2C%20assistant%2C%20and%20agent/Readme.md) - the model, application runtime, tools, context, and saved state
 * [Training. Training vs. Inference](./Training.%20Training%20vs.%20Inference/Readme.md) - weight updates, forward passes, gradients, and a one-weight example
 * [Training. Pretraining](./Training.%20Pretraining/Readme.md) - text-derived targets, prediction loss, useful patterns, and training data
 * [Training. Supervised fine-tuning](./Training.%20Supervised%20fine-tuning/Readme.md) - demonstrations, assistant-only scoring, chat formatting, and tool-use training
 * [Training. Preference tuning](./Training.%20Preference%20tuning/Readme.md) - preference pairs, reward models, direct updates, and the limits of preference scores
 * [Training. Reasoning training and distillation](./Training.%20Reasoning%20training%20and%20distillation/Readme.md) - verifiable rewards, teacher-to-student training, and inference-time computation

### Internals

 * [Internals. Tokens and tokenization](./Internals.%20Tokens%20and%20tokenization/Readme.md) - token IDs, vocabulary, BPE merges, bytes, and token counts
 * [Internals. The transformer forward pass](./Internals.%20The%20transformer%20forward%20pass/Readme.md) - embedding lookup, transformer blocks, residual updates, and next-token scores
 * [Internals. Embeddings and position information](./Internals.%20Embeddings%20and%20position%20information/Readme.md) - token and contextual vectors, retrieval embeddings, added position vectors, and RoPE
 * [Internals. Attention](./Internals.%20Attention/Readme.md) - query-key scores, scaling, causal masks, softmax, value mixtures, and parallel heads
 * [Internals. The residual stream and normalization](./Internals.%20The%20residual%20stream%20and%20normalization/Readme.md) - additive updates, pre-norm branches, LayerNorm, and RMSNorm
 * [Internals. MLPs and mixture of experts](./Internals.%20MLPs%20and%20mixture%20of%20experts/Readme.md) - expansion, ReLU, gated MLPs, expert routing, and active versus total parameters
 * [Internals. Features and the linear representation hypothesis](./Internals.%20Features%20and%20the%20linear%20representation%20hypothesis/Readme.md) - features, neurons, directions, projections, linear probes, and limits of the evidence
 * [Internals. Superposition and mechanistic interpretability](./Internals.%20Superposition%20and%20mechanistic%20interpretability/Readme.md) - overlapping features, interference, sparse autoencoders, and causal tests of circuits

### Inference

 * [Inference. What happens when a model answers](./Inference.%20What%20happens%20when%20a%20model%20answers/Readme.md) - one request as a token loop with fixed weights, four scopes from one token to the application, and the questions an inference engineer asks
 * [Inference. From logits to text with decoding and sampling](./Inference.%20From%20logits%20to%20text%20with%20decoding%20and%20sampling/Readme.md) - softmax, greedy decoding, temperature, top-k, top-p, stopping, and reproducibility
 * [Inference. Prefill and KV cache](./Inference.%20Prefill%20and%20KV%20cache/Readme.md) - prompt processing, cached keys and values, token-by-token reuse, cache growth, and latency
 * [Inference. Prompt caching across requests](./Inference.%20Prompt%20caching%20across%20requests/Readme.md) - shared prefixes, cache hits and misses, stable prompt layout, boundaries, and provider rules
 * [Inference. In-context learning, context windows, and memory](./Inference.%20In-context%20learning%2C%20context%20windows%2C%20and%20memory/Readme.md) - learning from examples, token budgets, saved history, external memory, retrieval, and compaction

### Agents

 * [Agents. Tool calls](./Agents.%20Tool%20calls/Readme.md) - tool definitions, arguments, execution checks, matching results, and the MCP integration boundary
 * [Agents. Loop - act, observe, continue, stop](./Agents.%20Loop%20-%20act%2C%20observe%2C%20continue%2C%20stop/Readme.md) - feedback, changing task state, verification, retries, budgets, and fixed workflows
 * [Agents. Thinking levels](./Agents.%20Thinking%20levels/Readme.md) - reasoning effort, adaptive computation, reasoning tokens, cost, latency, and provider controls
 * [Agents. Context engineering for long-running agents](./Agents.%20Context%20engineering%20for%20long-running%20agents/Readme.md) - next-call inputs, retrieved evidence, compaction, saved notes, subagent handoffs, and reusable prefixes
 * [Agents. Reliability - evaluation and execution boundaries](./Agents.%20Reliability%20-%20evaluation%20and%20execution%20boundaries/Readme.md) - outcome checks, traces, failure layers, safe retries, prompt injection, and enforced permissions
 * [Agents. A complete agent request, explained at every level](./Agents.%20A%20complete%20agent%20request%2C%20explained%20at%20every%20level/Readme.md) - a Python repair through context, tokens, transformer computation, tool execution, test feedback, and a checked answer

### Supporting reading

 * [AI Guardrails](./AI%20Guardrails/Readme.md) - input screening, tool authorization, and output checks, with a refund workflow from KodeKloud
 * [Codex commands](./Codex%20commands/Readme.md) - ten built-in slash commands for software engineering, learning, and writing
 * [Cosine Similarity](./Cosine%20similarity/Readme.md) - the geometry behind similarity scores and its role in retrieval
 * [LLM Failure Modes](./LLM%20Failure%20Modes/Readme.md) - hallucination, error propagation, sycophancy, instruction drift, and knowledge conflict
 * [Markov table](./Markov%20table/Readme.md) - transition probabilities, n-gram models, and a worked text generator
 * [Prompt-writing guidelines](./Prompt-writing%20guidelines/Readme.md) - what makes a prompt specific, testable, and stable
 * [RAG pipeline](./RAG%20pipeline/Readme.md) - components and numbered walkthroughs of RAG and agentic RAG

## AI agents learning plan

**Series scope: 25 article-mode cards**, studied in the order below. All 25 articles are available. The other existing cards above are supporting reading and are not included in this count.

**For every article, prioritize clarity and simplicity.** Define unfamiliar terms before using them, keep one main lesson per article, and use small examples and diagrams that each explain one idea. Include technical detail only when it helps the learner understand the lesson.

Each article should have one central question, a small worked example, and the two complementary local teaching visuals required by article mode.

Use a decoder-only transformer as the teaching baseline. Label model-specific architecture and training choices explicitly. Treat training stages as recipe components whose order and use vary, and distinguish interpretability hypotheses from established architecture. Recheck provider-specific caching and reasoning controls when drafting those articles.

### 1. System overview and training — 6 articles

| # | Proposed article | Central question and scope |
| --- | --- | --- |
| 1 | **[Training. Model, assistant, and agent](./Training.%20Model%2C%20assistant%2C%20and%20agent/Readme.md)** | What surrounds the model? Map learned parameters, inference, messages, the runtime that coordinates actions, tools, external state, and the user interface. Preview one request across these boundaries. |
| 2 | **[Training. Training vs. Inference](./Training.%20Training%20vs.%20Inference/Readme.md)** | What changes when a model learns versus when it answers? Explain parameters, activations, a forward pass, loss, backpropagation, and an optimizer update. Contrast ordinary inference with weight updates. |
| 3 | **[Training. Pretraining](./Training.%20Pretraining/Readme.md)** | How does a prediction objective produce useful capabilities? Cover training targets, data mixture and quality, generalization, memorization, and continued pretraining. Distinguish the objective from the capabilities it can support. |
| 4 | **[Training. Supervised fine-tuning](./Training.%20Supervised%20fine-tuning/Readme.md)** | What do examples of desired behavior change? Cover supervised fine-tuning (SFT), instruction-response and tool-use demonstrations, chat formatting, and changes to behavior and capabilities. |
| 5 | **[Training. Preference tuning](./Training.%20Preference%20tuning/Readme.md)** | How do preferences influence answers? Compare reinforcement learning from human feedback (RLHF), a learned reward model, and direct preference optimization (DPO). Separate preference scores from factual correctness. |
| 6 | **[Training. Reasoning training and distillation](./Training.%20Reasoning%20training%20and%20distillation/Readme.md)** | How are reasoning behaviors encouraged and transferred? Cover reinforcement learning (RL) with verifiable rewards, reasoning trajectories, distillation, and the limitations of the training signal. Compare training changes with spending more compute at inference. |

### 2. Inside the transformer — 8 articles

| # | Proposed article | Central question and scope |
| --- | --- | --- |
| 7 | **[Internals. Tokens and tokenization](./Internals.%20Tokens%20and%20tokenization/Readme.md)** | How does text become token IDs? Cover byte-pair encoding (BPE), bytes and subwords, vocabulary, special tokens, and consequences for spelling, languages, context length, and token counts. |
| 8 | **[Internals. The transformer forward pass](./Internals.%20The%20transformer%20forward%20pass/Readme.md)** | How do token IDs become scores for the next token? Trace embeddings, repeated transformer blocks, final normalization, and the output projection. Define vectors and matrix transformations before using them. |
| 9 | **[Internals. Embeddings and position information](./Internals.%20Embeddings%20and%20position%20information/Readme.md)** | How are token identity and token order represented? Compare embedding-table lookup, contextual representations, and retrieval embeddings. Introduce positional encoding and rotary position embeddings (RoPE) at a conceptual level. |
| 10 | **[Internals. Attention](./Internals.%20Attention/Readme.md)** | How can one token position use information from other positions? Work through query-key scores, scaling, the causal mask, softmax, weighted values, and multiple attention heads. |
| 11 | **[Internals. The residual stream and normalization](./Internals.%20The%20residual%20stream%20and%20normalization/Readme.md)** | How do transformer components share and update information? Follow the per-token residual vector, additive updates, and normalization. Contrast LayerNorm and root mean square normalization (RMSNorm) without a full derivation. |
| 12 | **[Internals. MLPs and mixture of experts](./Internals.%20MLPs%20and%20mixture%20of%20experts/Readme.md)** | What computation happens between attention layers? Explain the multilayer perceptron (MLP), expansion, nonlinear activation, gating, and projection back. Introduce mixture of experts (MoE) as a routed variant, including active versus total parameters. |
| 13 | **[Internals. Features and the linear representation hypothesis](./Internals.%20Features%20and%20the%20linear%20representation%20hypothesis/Readme.md)** | What might a direction in an activation space represent? Define features, neurons, directions, projections, and linear probes. Explain the hypothesis, its supporting evidence, and the limits of interpreting a successful probe. |
| 14 | **[Internals. Superposition and mechanistic interpretability](./Internals.%20Superposition%20and%20mechanistic%20interpretability/Readme.md)** | How can representations contain more features than dimensions? Cover overlapping directions, interference, polysemantic neurons, and sparse autoencoders. Distinguish descriptive correlations from evidence obtained by interventions. |

### 3. Inference and context — 5 articles

| # | Proposed article | Central question and scope |
| --- | --- | --- |
| 15 | **[Inference. What happens when a model answers](./Inference.%20What%20happens%20when%20a%20model%20answers/Readme.md)** | What is inference, and how do the next four articles connect? Define inference for a language model as a token loop with fixed weights. Map four scopes: one token, one reply, many requests, and the application. Introduce inference engineering and its speed, cost, and reliability questions. |
| 16 | **[Inference. From logits to text with decoding and sampling](./Inference.%20From%20logits%20to%20text%20with%20decoding%20and%20sampling/Readme.md)** | How is the next token selected? Explain logits, probabilities, greedy decoding, temperature, top-k, and top-p sampling with a tiny numerical example. Include stopping conditions and the limits of reproducibility. |
| 17 | **[Inference. Prefill and KV cache](./Inference.%20Prefill%20and%20KV%20cache/Readme.md)** | What work happens before and during generation? Compare processing the prompt with generating subsequent tokens. Explain cached attention keys and values (KV), cache growth, time to first token, and per-token latency. |
| 18 | **[Inference. Prompt caching across requests](./Inference.%20Prompt%20caching%20across%20requests/Readme.md)** | When can a later request reuse earlier computation? Explain shared prefixes, cache hits and misses, stable prompt layout, and provider-specific eligibility and retention. Compare prompt caching with caching a finished response. |
| 19 | **[Inference. In-context learning, context windows, and memory](./Inference.%20In-context%20learning%2C%20context%20windows%2C%20and%20memory/Readme.md)** | How can behavior adapt without updating weights? Separate examples in the prompt, the active context window, saved conversation state, external memory, and retrieval-augmented generation (RAG). Explain where each kind of information lives. |

### 4. Agents — 6 articles

| # | Proposed article | Central question and scope |
| --- | --- | --- |
| 20 | **[Agents. Tool calls](./Agents.%20Tool%20calls/Readme.md)** | Who actually executes a requested action? Trace a tool definition, generated arguments, validation, runtime execution, a matching result, and the next model call. Place Model Context Protocol (MCP) at the integration boundary. |
| 21 | **[Agents. Loop - act, observe, continue, stop](./Agents.%20Loop%20-%20act%2C%20observe%2C%20continue%2C%20stop/Readme.md)** | How does a sequence of model calls accomplish a task? Cover tool results, state transitions, retries, budgets, and stopping criteria. Compare fixed workflows with model-directed action selection. |
| 22 | **[Agents. Thinking levels](./Agents.%20Thinking%20levels/Readme.md)** | What does a reasoning-effort control change? Cover reasoning tokens, adaptive compute, latency and cost, and provider-specific effort settings. Separate effort from model size, temperature, answer verbosity, and a guaranteed correctness level. |
| 23 | **[Agents. Context engineering for long-running agents](./Agents.%20Context%20engineering%20for%20long-running%20agents/Readme.md)** | What should the next model call see? Cover instructions, tool descriptions, retrieved evidence, compaction, saved notes, and subagent handoffs. Trace the effects on information loss and reusable prompt prefixes. |
| 24 | **[Agents. Reliability - evaluation and execution boundaries](./Agents.%20Reliability%20-%20evaluation%20and%20execution%20boundaries/Readme.md)** | How do you tell whether the whole system works? Separate model, tool, and orchestration failures. Cover outcome-based evaluations, traces, external verification, retry side effects, prompt injection, and enforced tool permissions. |
| 25 | **[Agents. A complete agent request, explained at every level](./Agents.%20A%20complete%20agent%20request%2C%20explained%20at%20every%20level/Readme.md)** | Can you connect the whole stack? Follow a small coding task through context assembly, tokenization, transformer computation, sampling, a tool call, test feedback, another iteration, and a checked answer. Identify what training shaped and what changes during the run. |

### Reuse the existing cards

- Read [Cosine Similarity](./Cosine%20similarity/Readme.md) alongside [Internals. Embeddings and position information](./Internals.%20Embeddings%20and%20position%20information/Readme.md) and [Internals. Features and the linear representation hypothesis](./Internals.%20Features%20and%20the%20linear%20representation%20hypothesis/Readme.md) for vector geometry.
- Read [Markov table](./Markov%20table/Readme.md) alongside [Training. Pretraining](./Training.%20Pretraining/Readme.md) and [Inference. From logits to text with decoding and sampling](./Inference.%20From%20logits%20to%20text%20with%20decoding%20and%20sampling/Readme.md) for a small probability-based text generator.
- Read [RAG pipeline](./RAG%20pipeline/Readme.md) alongside [Inference. In-context learning, context windows, and memory](./Inference.%20In-context%20learning%2C%20context%20windows%2C%20and%20memory/Readme.md) and [Agents. Context engineering for long-running agents](./Agents.%20Context%20engineering%20for%20long-running%20agents/Readme.md) for the retrieval details.
- Read [Prompt-writing guidelines](./Prompt-writing%20guidelines/Readme.md) alongside [Agents. Context engineering for long-running agents](./Agents.%20Context%20engineering%20for%20long-running%20agents/Readme.md) for prompt construction.
- Read [LLM Failure Modes](./LLM%20Failure%20Modes/Readme.md) alongside [Agents. Reliability - evaluation and execution boundaries](./Agents.%20Reliability%20-%20evaluation%20and%20execution%20boundaries/Readme.md) for model-level failure patterns.
- Use [Codex commands](./Codex%20commands/Readme.md) as an optional product-specific companion to the agent articles.

### Completion check

After the sequence, explain one agent run at three levels: **training history**, **token-by-token model computation**, and **runtime actions and state**. Predict what changes when you alter the training data, prompt, sampling settings, reasoning effort, cache reuse, or tool implementation. Use [Agents. A complete agent request, explained at every level](./Agents.%20A%20complete%20agent%20request%2C%20explained%20at%20every%20level/Readme.md) to test these connections.

## Curriculum sources

- Training and post-training: [InstructGPT](https://arxiv.org/abs/2203.02155), [Direct Preference Optimization](https://arxiv.org/abs/2305.18290), and [DeepSeek-R1](https://arxiv.org/abs/2501.12948).
- A concrete architecture and training recipe: [Qwen3 Technical Report](https://arxiv.org/html/2505.09388v1). Use it as an example, not as the specification for every model.
- Transformer components and the residual stream: [A Mathematical Framework for Transformer Circuits](https://transformer-circuits.pub/2021/framework/index.html).
- Representation and interpretation: [The Linear Representation Hypothesis](https://arxiv.org/abs/2311.03658) and [Toy Models of Superposition](https://transformer-circuits.pub/2022/toy_model/index.html).
- Tokenization and inference: Hugging Face documentation on [tokenization algorithms](https://huggingface.co/docs/transformers/en/tokenizer_summary), [generation strategies](https://huggingface.co/docs/transformers/en/generation_strategies), and [KV caching](https://huggingface.co/docs/transformers/main/en/cache_explanation).
- Current OpenAI API behavior: [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching), [function calling](https://developers.openai.com/api/docs/guides/function-calling), and [reasoning effort](https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort).
- Agent structure and context: Anthropic's [Building effective agents](https://www.anthropic.com/research/building-effective-agents) and [Effective context engineering for AI agents](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents).
- Tool integration: [Model Context Protocol architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture).
