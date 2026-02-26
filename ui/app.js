/**
 * Copilot Spaces Chat — Frontend Application
 *
 * Connects to the FastAPI bridge which proxies requests to
 * GitHub Copilot Spaces API via MCP tools.
 * Conversation history is kept in-memory on the client side.
 */

const API_BASE = window.location.origin + "/api";

// ─── Application State ───────────────────────────────────────

const state = {
    spaces: [],
    selectedSpace: null,
    selectedSpaceName: "",
    conversationId: null,       // Server-side conversation ID
    messages: [],               // In-memory chat messages
    loading: false,
};

// ─── DOM Elements ────────────────────────────────────────────

const $spaceSelect = document.getElementById("space-select");
const $refreshSpacesBtn = document.getElementById("refresh-spaces-btn");
const $newChatBtn = document.getElementById("new-chat-btn");
const $messages = document.getElementById("messages");
const $messageInput = document.getElementById("message-input");
const $sendBtn = document.getElementById("send-btn");
const $chatTitle = document.getElementById("chat-title");
const $spaceBadge = document.getElementById("space-badge");

// ─── API Calls ───────────────────────────────────────────────

async function fetchSpaces() {
    try {
        const res = await fetch(`${API_BASE}/spaces`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        state.spaces = await res.json();
        renderSpaceSelect();
    } catch (err) {
        console.error("Failed to fetch spaces:", err);
        $spaceSelect.innerHTML =
            '<option value="">Failed to load spaces — check GITHUB_TOKEN</option>';
    }
}

async function sendMessage(prompt) {
    if (!state.selectedSpace || !prompt.trim()) return;

    state.loading = true;
    updateInputState();

    // Add user message to local state and UI
    state.messages.push({ role: "user", content: prompt });
    addMessageToUI("user", prompt);
    showTypingIndicator();

    try {
        const res = await fetch(
            `${API_BASE}/spaces/${state.selectedSpace}/query`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt: prompt.trim(),
                    conversationId: state.conversationId,
                }),
            }
        );

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${res.status}`);
        }

        const data = await res.json();

        // Track server conversation ID for multi-turn context
        state.conversationId = data.conversationId;

        // Add assistant message
        state.messages.push({ role: "assistant", content: data.response });
        removeTypingIndicator();
        addMessageToUI("assistant", data.response);
    } catch (err) {
        removeTypingIndicator();
        showError(err.message);
        console.error("Send message error:", err);
    } finally {
        state.loading = false;
        updateInputState();
    }
}

// ─── Rendering ───────────────────────────────────────────────

function renderSpaceSelect() {
    if (state.spaces.length === 0) {
        $spaceSelect.innerHTML = '<option value="">No spaces found</option>';
        return;
    }

    let html = '<option value="">Select a Copilot Space...</option>';
    state.spaces.forEach((space) => {
        // Prefer the normalised 'owner/name' ref from the server, fall back to id/name
        const id = space.space_ref || space.id || space.name || space;
        const name = space.name || space.title || id;
        html += `<option value="${escapeHtml(String(id))}">${escapeHtml(String(name))}</option>`;
    });
    $spaceSelect.innerHTML = html;

    if (state.selectedSpace) {
        $spaceSelect.value = state.selectedSpace;
    }
}

function addMessageToUI(role, content) {
    // Remove welcome message if present
    const welcome = $messages.querySelector(".welcome-message");
    if (welcome) welcome.remove();

    const div = document.createElement("div");
    div.innerHTML = createMessageHTML(role, content);
    $messages.appendChild(div.firstElementChild);
    scrollToBottom();
}

function createMessageHTML(role, content, timestamp = null) {
    const time = timestamp
        ? new Date(timestamp).toLocaleTimeString()
        : new Date().toLocaleTimeString();
    const label = role === "user" ? "You" : "Copilot Space";

    return `
        <div class="message ${role}">
            <div class="msg-header">${label}</div>
            <div class="msg-content">${escapeHtml(content)}</div>
            <div class="msg-time">${time}</div>
        </div>`;
}

function showTypingIndicator() {
    const div = document.createElement("div");
    div.className = "typing-indicator";
    div.id = "typing-indicator";
    div.innerHTML = `
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>`;
    $messages.appendChild(div);
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById("typing-indicator");
    if (el) el.remove();
}

function showError(message) {
    const div = document.createElement("div");
    div.className = "error-banner";
    div.textContent = `${message}`;
    $messages.appendChild(div);
    scrollToBottom();

    // Auto-remove after 8 seconds
    setTimeout(() => div.remove(), 8000);
}

function showWelcome() {
    $messages.innerHTML = `
        <div class="welcome-message">
            <div class="welcome-icon">🤖</div>
            <h2>Welcome to Copilot Spaces Chat</h2>
            <p>Select a Copilot Space from the sidebar and start a conversation.</p>
            <div class="feature-cards">
                <div class="feature-card">
                    <span class="feature-icon">💬</span>
                    <div>
                        <strong>Chat with Spaces</strong>
                        <p>Send prompts to any GitHub Copilot Space</p>
                    </div>
                </div>
                <div class="feature-card">
                    <span class="feature-icon">📚</span>
                    <div>
                        <strong>Conversation Context</strong>
                        <p>Multi-turn conversations with full history</p>
                    </div>
                </div>
                <div class="feature-card">
                    <span class="feature-icon">🔌</span>
                    <div>
                        <strong>MCP Powered</strong>
                        <p>Built on Model Context Protocol</p>
                    </div>
                </div>
            </div>
        </div>`;
}

function updateChatHeader() {
    if (state.selectedSpace) {
        const space = state.spaces.find(
            (s) => (s.space_ref || s.id || s.name || s) === state.selectedSpace
        );
        const name = space?.name || space?.title || state.selectedSpace;
        $chatTitle.textContent = `Chat with ${name}`;
        $spaceBadge.textContent = name;
        $spaceBadge.classList.remove("hidden");
    } else {
        $chatTitle.textContent = "Select a Copilot Space to start chatting";
        $spaceBadge.classList.add("hidden");
    }
}

function updateInputState() {
    const canSend = state.selectedSpace && !state.loading;
    $messageInput.disabled = !canSend;
    $sendBtn.disabled = !canSend;

    if (!state.selectedSpace) {
        $messageInput.placeholder = "Select a Copilot Space first...";
    } else if (state.loading) {
        $messageInput.placeholder = "Waiting for response...";
    } else {
        $messageInput.placeholder =
            "Type your message... (Enter to send, Shift+Enter for new line)";
    }
}

function startNewChat() {
    state.conversationId = null;
    state.messages = [];
    showWelcome();
    updateChatHeader();
    $messageInput.focus();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        $messages.scrollTop = $messages.scrollHeight;
    });
}

// ─── Helpers ─────────────────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ─── Event Handlers ──────────────────────────────────────────

$spaceSelect.addEventListener("change", (e) => {
    state.selectedSpace = e.target.value;
    const opt = e.target.selectedOptions[0];
    state.selectedSpaceName = opt ? opt.textContent : "";

    // Reset conversation when switching spaces
    startNewChat();
    updateInputState();
});

$refreshSpacesBtn.addEventListener("click", () => {
    $spaceSelect.innerHTML = '<option value="">Loading...</option>';
    fetchSpaces();
});

$newChatBtn.addEventListener("click", () => {
    startNewChat();
});

$sendBtn.addEventListener("click", () => {
    const text = $messageInput.value.trim();
    if (text) {
        $messageInput.value = "";
        $messageInput.style.height = "auto";
        sendMessage(text);
    }
});

$messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const text = $messageInput.value.trim();
        if (text && !state.loading && state.selectedSpace) {
            $messageInput.value = "";
            $messageInput.style.height = "auto";
            sendMessage(text);
        }
    }
});

// Auto-resize textarea
$messageInput.addEventListener("input", () => {
    $messageInput.style.height = "auto";
    $messageInput.style.height =
        Math.min($messageInput.scrollHeight, 150) + "px";
});

// ─── Initialize ──────────────────────────────────────────────

(async function init() {
    await fetchSpaces();
    updateInputState();
})();
