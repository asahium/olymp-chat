import { useEffect, useRef } from "react";
import { ChatMessage } from "../api";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
}

// Renders message content as PLAIN TEXT only (no HTML/Markdown rendering) to
// avoid any XSS from model output.
export default function MessageList({ messages, loading }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="messages">
      {messages.length === 0 && !loading && (
        <div className="empty muted">Ask a question to get started.</div>
      )}
      {messages.map((m, i) => (
        <div key={i} className={`msg msg-${m.role}`}>
          <div className="msg-role">{m.role === "user" ? "You" : "Assistant"}</div>
          <div className="msg-content">{m.content}</div>
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
