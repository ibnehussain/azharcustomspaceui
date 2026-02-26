# Learnings: Building a Custom UI for GitHub Copilot Spaces via MCP

---

## 1. GitHub Copilot Spaces Has No Public REST API

- There is no documented `GET /copilot/spaces` REST endpoint on the GitHub API
- All direct REST attempts returned `404`
- The only supported way to access Copilot Spaces programmatically is through the **official GitHub Remote MCP Server**

---

## 2. The Correct GitHub Remote MCP Server URL

- The base URL `https://api.githubcopilot.com/mcp/` works for general tools but does **not** expose the `copilot_spaces` toolset by default
- Each toolset has a **dedicated URL**: `https://api.githubcopilot.com/mcp/x/{toolset}`
- The correct URL for Copilot Spaces is: `https://api.githubcopilot.com/mcp/x/copilot_spaces`
- Using the wrong URL caused tool calls to fail silently or return no results

---

## 3. MCP Streamable HTTP GET Stream Returns 405

- GitHub's MCP server does **not** support the SSE GET stream (`GET /mcp/x/...` → `405 Method Not Allowed`)
- The MCP Python SDK (`streamablehttp_client`) tries to open a GET SSE stream for server-push events
- This triggers a 1-second reconnect timer which fires during `async with` context cleanup → raises `ExceptionGroup`
- The tool result is **already received** before the cleanup fires (via POST → 200 OK)
- Fix: capture the result in a sentinel variable **inside** the context, then return it from the outer except block if the ExceptionGroup fires after data was received

---

## 4. MCP Response Content Type: `EmbeddedResource`, Not `TextContent`

- The GitHub MCP server returns tool results as `EmbeddedResource` content items, not plain `TextContent`
- Each item has: `item.resource.uri`, `item.resource.mimeType`, `item.resource.text`
- Accessing `content[0].text` directly returns `None` — must check `content[0].resource.text`
- Standard MCP servers use `TextContent` with a `.text` attribute; both must be handled

---

## 5. `get_copilot_space` Returns Multiple Content Items

- `result.content` is a **list**, not a single item
- The first item (`content[0]`) has URI `space://{owner}/{id}/contents/name` — just the space name
- Remaining items have URI `space://{owner}/{id}/files/{path}` — the actual file contents
- Reading only `content[0]` (as originally coded) means all file content is silently discarded
- Fix: iterate all `result.content` items and classify by URI pattern

---

## 6. Space Field Name Is `owner_login`, Not `owner`

- The `list_copilot_spaces` tool returns `{"name": "...", "owner_login": "..."}` per space
- Assuming the field is `owner` results in an empty string and a broken `space_ref` like `/testspace`
- Always inspect the raw MCP response structure before assuming field names

---

## 7. The Copilot Chat Completions API Rejects PATs

- `POST https://api.githubcopilot.com/chat/completions` with a GitHub PAT returns `400 Bad Request`
- Error message: `"Personal Access Tokens are not supported for this endpoint"`
- This endpoint requires a **short-lived Copilot session token**, not a PAT
- The token exchange endpoint (`/copilot_internal/v2/token`) also returned `404` for this PAT type
- Fix: use the **GitHub Models API** (`https://models.inference.ai.azure.com/chat/completions`) which **does** accept GitHub PATs directly and is fully OpenAI-compatible

---

## 8. Custom Uploaded Knowledge Files Are Not Returned by MCP

- Files uploaded via the GitHub.com Copilot Spaces UI ("Add knowledge → Upload file") are **not** returned by the `get_copilot_space` MCP tool
- `get_copilot_space` only returns files from a **GitHub repository linked to the space**
- GitHub.com's own Copilot chat reads uploaded files through an internal API not exposed via MCP
- Fix: link a GitHub repository to the space, push knowledge files there; MCP will return those files

---

## 9. FastAPI Path Parameters Can Contain Slashes With `{owner}/{name}`

- Space references follow the `owner/name` pattern (e.g. `ibnehussain/testspace`)
- Using a single `{space_id}` path parameter breaks because FastAPI/Starlette treats `/` as a path separator
- Fix: split into two separate path parameters — `{owner}` and `{name}` — in every route

---

## 10. The MCP Python SDK Needs the Full `async with` Context Pattern

- `streamablehttp_client` must be used as an async context manager yielding `(read, write, _)`
- `ClientSession` must then wrap `(read, write)` and `await session.initialize()` must be called before any tool calls
- Skipping `initialize()` causes the session to send tool calls without a valid session ID, resulting in silent failures

---

## 11. `git rev-parse --show-toplevel` Before Pushing to a New Repo

- The project directory was a **subdirectory** of an existing git repo (`c:/co-pilot`)
- Running `git add` and `git push` would have pushed unrelated parent-repo files to the new public repo
- Fix: run `git init` inside the subdirectory to create a fresh, isolated repo before setting the new remote

---

## 12. PowerShell Treats git stderr as Errors

- Git writes progress and remote info to `stderr`, which PowerShell flags as `NativeCommandError`
- Exit code 1 is returned even when the push succeeds (`* [new branch] main -> main`)
- Always verify push success with `git log --oneline` and `git remote -v` rather than trusting the exit code alone

---

## 13. Inject Space Context Into System Prompt for Grounded Answers

- Without injecting file content, the model answers from general knowledge and says "I don't have access to your files"
- The right pattern: call `get_copilot_space` at the start of each new conversation, build a system message containing all file contents, then send that as the first message in the conversation history
- Context should be fetched **once per conversation** and cached — not on every message — to avoid repeated MCP round trips

---

## 14. Debug Sensitive Data Before Pushing

- `.env` containing the `GITHUB_TOKEN` was present in the project directory
- It was already listed in `.gitignore`, so it was never staged
- Always run `git status --short | Select-String "\.env"` before the first push to confirm no secrets are included
- Provide a `.env.example` with placeholder values so contributors know what to configure
