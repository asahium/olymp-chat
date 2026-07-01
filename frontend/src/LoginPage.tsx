import { FormEvent, useState } from "react";
import { login } from "./api";

export default function LoginPage({ onLoggedIn }: { onLoggedIn: (name: string) => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await login(code.trim());
      onLoggedIn(data.display_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="centered">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>AIOI Contest Chat</h1>
        <p className="muted">Enter your participant code to begin.</p>
        <input
          className="login-input"
          type="text"
          placeholder="e.g. ABCD-2345"
          value={code}
          autoFocus
          onChange={(e) => setCode(e.target.value)}
        />
        <button className="btn" type="submit" disabled={busy || !code.trim()}>
          {busy ? "Signing in…" : "Enter"}
        </button>
        {error && <div className="error">{error}</div>}
      </form>
    </div>
  );
}
