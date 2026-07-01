import { useEffect, useState } from "react";
import { clearToken, getToken, me } from "./api";
import LoginPage from "./LoginPage";
import ChatPage from "./ChatPage";

export default function App() {
  const [authed, setAuthed] = useState<boolean>(false);
  const [displayName, setDisplayName] = useState<string>("");
  const [checking, setChecking] = useState<boolean>(true);

  // Validate any stored token on load.
  useEffect(() => {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    me()
      .then((info) => {
        setDisplayName(info.display_name);
        setAuthed(true);
      })
      .catch(() => {
        clearToken();
      })
      .finally(() => setChecking(false));
  }, []);

  function handleLoggedIn(name: string) {
    setDisplayName(name);
    setAuthed(true);
  }

  function handleLogout() {
    clearToken();
    setAuthed(false);
    setDisplayName("");
  }

  if (checking) {
    return <div className="centered">Loading…</div>;
  }

  return authed ? (
    <ChatPage displayName={displayName} onLogout={handleLogout} />
  ) : (
    <LoginPage onLoggedIn={handleLoggedIn} />
  );
}
