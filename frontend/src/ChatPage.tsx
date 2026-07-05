import { useEffect, useState } from "react";
import { changeCode, chat, Chat, ChatMessage, getChats, saveChats } from "./api";
import { MAX_CHATS, newChatId } from "./storage";
import MessageList from "./components/MessageList";
import MessageInput from "./components/MessageInput";

interface Props {
  displayName: string;
  onLogout: () => void;
}

function emptyChat(): Chat {
  return { id: newChatId(), messages: [], updatedAt: Date.now() };
}

function chatTitle(c: Chat): string {
  const firstUser = c.messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const t = firstUser.content.trim().replace(/\s+/g, " ");
  return t.length > 26 ? t.slice(0, 26) + "…" : t;
}

export default function ChatPage({ displayName, onLogout }: Props) {
  const [chats, setChats] = useState<Chat[]>(() => [emptyChat()]);
  const [activeId, setActiveId] = useState<string>(() => chats[0].id);
  const [hydrated, setHydrated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Change-code panel state.
  const [showCode, setShowCode] = useState(false);
  const [newCode, setNewCode] = useState("");
  const [codeMsg, setCodeMsg] = useState("");

  // Pull recent chats from the server on login (works from any device).
  useEffect(() => {
    let cancelled = false;
    getChats()
      .then((server) => {
        if (cancelled) return;
        if (server.length) {
          setChats(server);
          setActiveId(server[0].id);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setHydrated(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist to the server after hydration, on every change.
  useEffect(() => {
    if (!hydrated) return;
    saveChats(chats).catch(() => {});
  }, [chats, hydrated]);

  const active = chats.find((c) => c.id === activeId) ?? chats[0];
  const messages = active.messages;

  function updateActive(newMessages: ChatMessage[]) {
    setChats((prev) =>
      prev
        .map((c) =>
          c.id === active.id ? { ...c, messages: newMessages, updatedAt: Date.now() } : c,
        )
        .sort((a, b) => b.updatedAt - a.updatedAt),
    );
  }

  async function send(text: string) {
    setError("");
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    updateActive(next);
    setLoading(true);
    try {
      const result = await chat(next);
      updateActive([...next, { role: "assistant", content: result.message.content }]);
    } catch (err) {
      updateActive(messages); // roll back the optimistic user message
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setError("");
    if (active.messages.length === 0) return; // don't stack empty chats
    const fresh = emptyChat();
    setChats((prev) => [fresh, ...prev].slice(0, MAX_CHATS));
    setActiveId(fresh.id);
  }

  async function submitCode() {
    setCodeMsg("");
    try {
      await changeCode(newCode.trim());
      setCodeMsg("Code updated. Use it next time you log in.");
      setNewCode("");
    } catch (err) {
      setCodeMsg(err instanceof Error ? err.message : "Could not change code.");
    }
  }

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div>
          <strong>AI Chat</strong>
          <div className="model-note">Model: Gemma 3. Max answer length: 1000 output tokens.</div>
        </div>
        <div className="header-actions">
          <span className="muted">{displayName}</span>
          <button className="btn-ghost" onClick={newChat}>New chat</button>
          <button className="btn-ghost" onClick={() => setShowCode((v) => !v)}>Change code</button>
          <button className="btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </header>

      {showCode && (
        <div className="code-panel">
          <span className="muted">Set your own private code (others won't be able to log in):</span>
          <input
            className="login-input code-input"
            type="text"
            placeholder="new code"
            value={newCode}
            onChange={(e) => setNewCode(e.target.value)}
          />
          <button className="btn" onClick={submitCode} disabled={newCode.trim().length < 4}>
            Save
          </button>
          {codeMsg && <span className="muted">{codeMsg}</span>}
        </div>
      )}

      {chats.length > 1 && (
        <div className="chat-tabs">
          <span className="muted tabs-label">Recent:</span>
          {chats.map((c) => (
            <button
              key={c.id}
              className={`chat-tab ${c.id === active.id ? "active" : ""}`}
              onClick={() => setActiveId(c.id)}
              title={chatTitle(c)}
            >
              {chatTitle(c)}
            </button>
          ))}
        </div>
      )}

      <MessageList messages={messages} loading={loading} />

      {error && <div className="error chat-error">{error}</div>}

      <MessageInput onSend={send} disabled={loading} />
    </div>
  );
}
