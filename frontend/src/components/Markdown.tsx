import { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CodeBlock from "./CodeBlock";

// Flatten arbitrary react-markdown children into a plain string (for code text).
function childrenToString(children: ReactNode): string {
  if (children == null) return "";
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenToString).join("");
  if (typeof children === "object" && "props" in (children as any)) {
    return childrenToString((children as any).props.children);
  }
  return "";
}

// XSS-safe markdown: react-markdown builds React nodes and does NOT render raw
// HTML (no rehype-raw) and sanitizes URLs by default. Fenced code becomes a
// CodeBlock with a copy button; inline code stays inline.
export default function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Unwrap <pre> so our CodeBlock isn't nested inside a <pre>.
        pre: ({ children }) => <>{children}</>,
        code({ className, children }) {
          const text = childrenToString(children);
          const isBlock = /language-/.test(className || "") || text.includes("\n");
          if (!isBlock) {
            return <code className="inline-code">{children}</code>;
          }
          const lang = (className || "").replace("language-", "").trim();
          return <CodeBlock code={text.replace(/\n$/, "")} lang={lang} />;
        },
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
