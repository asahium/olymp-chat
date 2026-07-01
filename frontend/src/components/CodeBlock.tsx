import { useState } from "react";
import { copyText } from "../clipboard";

interface Props {
  code: string;
  lang?: string;
}

// A fenced code block with a language label and a copy button that works
// over plain HTTP (see clipboard.ts).
export default function CodeBlock({ code, lang }: Props) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    const ok = await copyText(code);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <div className="code-block">
      <div className="code-block-head">
        <span className="code-lang">{lang || "code"}</span>
        <button className="code-copy" onClick={onCopy} type="button">
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="code-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}
