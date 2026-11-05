# Agents: Tool calls from model output to execution

<sub>[Back to Artificial Intelligence](../Readme.md#content)</sub>

**A tool call is the model's request for another program to do something. The surrounding software checks the request, runs the tool, and brings the result back.** Follow one file lookup to see how a generated request becomes an action.

## Where this fits

[In-context learning, context windows, and memory](../In-context%20learning%20and%20memory/Readme.md) explained that a file helps only after its contents enter the model's context. A **tool** provides a way to get them. The **runtime** is the application code that coordinates model calls and tool execution.

## The tool calling flow

* Tool calling is a multi-step conversation between your application and a model via the OpenAI API.
* An **API** is a way for programs to communicate.
* “Developer” in the diagram means your application. The diagram uses a weather example.

The flow has five high-level steps:

![tool-calling-flow.svg](images/tool-calling-flow.svg)

1. Make a request to the model with tools it could call.
2. Receive a tool call from the model.
3. Execute code on the application side with input from the tool call.
4. Make a second request to the model with the tool output.
5. Receive a final response from the model (or more tool calls).

## Where MCP fits

**Model Context Protocol (MCP)** is a shared set of communication rules for connecting applications to tools and other context sources.

![mcp-integration.svg](images/mcp-integration.svg)

The application contains an **MCP client**, the component that talks to an **MCP server**, a program exposing tools. The client can ask which tools exist, send a call, and receive its result. The server runs locally or remotely and provides access to the underlying files or services.

MCP standardizes this connection. The application still supplies tool information to the model and manages the exchange. Tools can also be connected directly, without MCP, as in the file lookup above.

# Sources

- [OpenAI: function-calling sequence (diagram reference)](https://developers.openai.com/api/docs/guides/function-calling)
- [Claude: tool use and where tools run](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Claude: tool definitions and input schemas](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Claude: matching results and handling errors](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [MCP: architecture and participants](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP: tool discovery, calls, and access checks](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
