import { useState } from "react";
import { chat, ChatMessage } from "./api";
import MessageList from "./components/MessageList";
import MessageInput from "./components/MessageInput";

interface Props {
  displayName: string;
  onLogout: () => void;
}

export default function ChatPage({ displayName, onLogout }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function send(text: string) {
    setError("");
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setLoading(true);
    try {
      const result = await chat(next);
      setMessages([...next, { role: "assistant", content: result.message.content }]);
    } catch (err) {
      // Roll back the optimistic user message so it can be retried.
      setMessages(messages);
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setMessages([]);
    setError("");
  }

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div>
          <strong>AIOI Contest Chat</strong>
          <div className="model-note">Model: Gemma 3. Max answer length: 1000 output tokens.</div>
        </div>
        <div className="header-actions">
          <span className="muted">{displayName}</span>
          <button className="btn-ghost" onClick={newChat}>New chat</button>
          <button className="btn-ghost" onClick={onLogout}>Log out</button>
        </div>
      </header>

      <MessageList messages={messages} loading={loading} />

      {error && <div className="error chat-error">{error}</div>}

      <MessageInput onSend={send} disabled={loading} />
    </div>
  );
}
