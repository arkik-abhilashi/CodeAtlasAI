import { useState } from "react";
import { api } from "../lib/api";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const session = await api(`/api/auth/${mode}`, { method: "POST", body: mode === "register" ? { email, password, display_name: displayName } : { email, password } });
      onAuthenticated(session);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <main className="ca-auth-screen">
    <div className="ca-grid-bg" aria-hidden="true" /><div className="ca-glow ca-glow--amber" aria-hidden="true" /><div className="ca-glow ca-glow--violet" aria-hidden="true" />
    <a className="ca-wordmark ca-auth-brand" href="#home">CODEATLAS <span>AI</span></a>
    <section className="ca-auth-card"><div className="ca-auth-copy"><p className="ca-kicker">YOUR CODE. CLEARER.</p><h1>{mode === "login" ? <>Welcome <span className="ca-gradient-text">back.</span></> : <>Create your <span className="ca-gradient-text">workspace.</span></>}</h1><p>Map dependencies, explore architecture, and make sense of your repositories.</p></div>
      <form onSubmit={submit} className="ca-auth-form">
        {mode === "register" && <label>Display name<input autoComplete="name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} required maxLength={120} /></label>}
        <label>Email address<input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required maxLength={320} /></label>
        <label>Password<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={mode === "register" ? 10 : 1} maxLength={128} />{mode === "register" && <small>Use at least 10 characters.</small>}</label>
        {error && <p className="ca-import-error" role="alert">{error}</p>}
        <button className="ca-button ca-button--primary" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <p className="ca-auth-switch">{mode === "login" ? "New to CodeAtlas?" : "Already have an account?"} <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>{mode === "login" ? "Create an account" : "Sign in"}</button></p>
    </section>
    <p className="ca-auth-footnote">Your repositories are private to your account.</p>
  </main>;
}
