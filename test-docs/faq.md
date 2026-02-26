# FAQ

## What is this space?

This is a test Copilot Space used to validate context-aware AI responses via the custom MCP UI.

## What questions can I ask?

- "Summarise the architecture of this project"
- "How does authentication work here?"
- "What endpoints does the API expose?"
- "What model is used for chat?"
- "How do I run this locally?"

## What is MCP?

MCP (Model Context Protocol) is an open protocol that lets AI models interact with external tools and data sources in a structured way. This project uses the GitHub Remote MCP Server to access Copilot Spaces.

## How is conversation history kept?

The API bridge stores conversation history in memory (per session). Each conversation gets a `conversationId` that is passed back and forth between the UI and the server.

## What happens if I refresh the page?

A new conversation starts. Previous history is not persisted — it lives only in server memory for the duration of the process.

## How do I add more spaces?

Create a new Copilot Space at [github.com/copilot/spaces](https://github.com/copilot/spaces). It will automatically appear in the sidebar next time you load the UI.
