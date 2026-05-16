# MCP Integration Guide 🔌

DimagX uses the **Model Context Protocol (MCP)** to provide your coding agent with instant project memory. This guide explains how to connect your agent and use the available tools.

## Supported Agents

DimagX is compatible with any agent that supports the MCP standard, including:
- **Claude Code** (CLI)
- **Cursor** (IDE)
- **Windsurf** (IDE)
- **Supermaven**
- **Cline** / **Roo Code**

## Configuration

### 1. Locate your config file
The location varies depending on your tool:
- **Claude Code**: `~/.claude/mcp.json`
- **Cursor**: Settings → Features → MCP
- **Windsurf**: `~/.codeium/windsurf/mcp_config.json`

### 2. Add DimagX Server
Add the following entry to your `mcpServers` object:

```json
{
  "mcpServers": {
    "dimagx": {
      "command": "dimagx-mcp"
    }
  }
}
```

*Note: Ensure `dimagx` is installed in your path (`pip install -e .`).*

---

## Tool Reference

Once connected, your agent can call these tools. You don't need to call them manually—the agent will decide when they are needed.

### `get_context()`
- **Purpose**: Get a full snapshot of the project.
- **Returns**: Active features, recent decisions, PRD summaries, and the latest prompts.
- **Best for**: Starting a new session.

### `query_memory(question)`
- **Purpose**: Semantic search across the entire project memory.
- **Returns**: Top relevant nodes (Files, PRDs, Decisions, etc.) using vector embeddings.
- **Best for**: "How do I handle X?", "What was the decision on Y?"

### `log_prompt(text, summary, outcome)`
- **Purpose**: Save the result of a task to the memory graph.
- **Best for**: Ensuring future sessions remember what was just accomplished.

### `add_decision(title, context, choice, reason)`
- **Purpose**: Log an architectural decision.
- **Best for**: Documenting *why* a specific approach was taken.

### `get_features(status?)` / `get_files(feature?)`
- **Purpose**: Structured navigation of the project.
- **Best for**: Identifying exactly which files belong to a specific feature.

---

## Best Practices for Agents

To get the most out of DimagX, you can give your agent a custom instruction:

> "You have access to DimagX, my project's persistent memory graph. Always call `get_context()` at the start of our session to see what I'm working on and what decisions have been made. Use `query_memory()` before asking me to explain how a feature works."
