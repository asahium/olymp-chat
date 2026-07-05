import { KeyboardEvent, useLayoutEffect, useRef, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

const MAX_HEIGHT = 220; // px; beyond this the textarea scrolls

export default function MessageInput({ onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea to fit its content (up to MAX_HEIGHT), so pasted
  // multi-line text is comfortable to read instead of a cramped 2 rows.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, MAX_HEIGHT) + "px";
  }, [text]);

  function submit() {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter inserts a newline.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="input-bar">
      <textarea
        ref={ref}
        className="input-box"
        placeholder="Type your message…  (Enter to send, Shift+Enter for newline)"
        value={text}
        rows={1}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button className="btn" onClick={submit} disabled={disabled || !text.trim()}>
        Send
      </button>
    </div>
  );
}
