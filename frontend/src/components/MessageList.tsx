import { useEffect, useRef, useState } from "react";
import { ChatMessage } from "../api";
import Markdown from "./Markdown";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  // Edit a user message and re-run the model from that point (drops everything
  // after it). Crucial for iterating on a prompt without starting over.
  onEditUser?: (index: number, newText: string) => void;
}

// Renders message content as PLAIN TEXT (user) or sanitized Markdown (assistant).
export default function MessageList({ messages, loading, onEditUser }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function startEdit(i: number, content: string) {
    setEditingIndex(i);
    setDraft(content);
  }

  function saveEdit(i: number) {
    const text = draft.trim();
    if (!text) return;
    setEditingIndex(null);
    onEditUser?.(i, text);
  }

  return (
    <div className="messages">
      {messages.length === 0 && !loading && (
        <div className="empty muted">Ask a question to get started.</div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`msg msg-${m.role}`}>
          <div className="msg-role">
            {m.role === "user" ? "You" : "Assistant"}
            {m.role === "user" && onEditUser && editingIndex !== i && !loading && (
              <button className="edit-btn" onClick={() => startEdit(i, m.content)}>
                edit
              </button>
            )}
          </div>
          {editingIndex === i ? (
            <div className="msg-edit">
              <textarea
                className="edit-area"
                value={draft}
                rows={3}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
              />
              <div className="edit-actions">
                <button className="btn" onClick={() => saveEdit(i)} disabled={!draft.trim()}>
                  Save & regenerate
                </button>
                <button className="btn-ghost" onClick={() => setEditingIndex(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="msg-content">
              {m.role === "assistant" ? <Markdown content={m.content} /> : m.content}
            </div>
          )}
        </div>
      ))}
      {loading && (
        <div className="msg msg-assistant">
          <div className="msg-role">Assistant</div>
          <div className="msg-content typing">…thinking</div>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
