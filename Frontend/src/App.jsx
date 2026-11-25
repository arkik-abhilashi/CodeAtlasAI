import React, { useEffect, useState } from "react";
import AuthScreen from "./components/AuthScreen";
import TopBar from "./components/TopBar";
import Sidebar from "./components/Sidebar";
import RepositoryWorkspace from "./components/RepositoryWorkspace";
import { api, clearSession, getAccessToken, getCachedUser, saveSession } from "./lib/api";
import "./styles/index.css";
import "./styles/codeatlas.css";
import "./styles/workspace.css";
import "./styles/redesign.css";

const PAGES = new Set(["dashboard", "repositories", "files", "architecture", "reports", "settings"]);
const PAGE_TITLES = {
  dashboard: "Overview",
  repositories: "Repositories",
  files: "Code explorer",
  architecture: "Architecture",
  reports: "Analysis reports",
  settings: "Settings",
};

class PageErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error("CodeAtlas page crashed", error, info); }
  componentDidUpdate(previous) { if (previous.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }); }
  render() {
    if (this.state.error) return <section className="ca-repo-empty" role="alert"><h2>This page hit an error</h2><p>{this.state.error.message || "An unexpected error occurred."}</p><button className="ca-button ca-button--primary" onClick={() => this.setState({ error: null })}>Try again</button></section>;
    return this.props.children;
  }
}

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 1200);
  const [token, setToken] = useState(getAccessToken());
  const [user, setUser] = useState(getCachedUser());
  const [authReady, setAuthReady] = useState(!getAccessToken());
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || systemTheme());
  const [activePage, setActivePage] = useState(() => {
    const page = window.location.hash.slice(1);
    return PAGES.has(page) ? page : "dashboard";
  });

  useEffect(() => {
    const syncHash = () => { const page = window.location.hash.slice(1); setActivePage(PAGES.has(page) ? page : "dashboard"); };
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  useEffect(() => {
    let wasDesktop = window.innerWidth >= 1200;
    const updateSidebarForViewport = () => {
      const isDesktop = window.innerWidth >= 1200;
      if (isDesktop !== wasDesktop) setSidebarOpen(isDesktop);
      wasDesktop = isDesktop;
    };
    window.addEventListener("resize", updateSidebarForViewport);
    return () => window.removeEventListener("resize", updateSidebarForViewport);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem("codeatlas.theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    api("/api/auth/me").then((currentUser) => {
      if (active) {
        setUser(currentUser);
        localStorage.setItem("codeatlas.user", JSON.stringify(currentUser));
      }
    }).catch(() => {
      if (active) { clearSession(); sessionStorage.removeItem("codeatlas.selectedRepository"); setToken(null); setUser(null); }
    }).finally(() => { if (active) setAuthReady(true); });
    const handleUnauthorized = () => { clearSession(); sessionStorage.removeItem("codeatlas.selectedRepository"); setToken(null); setUser(null); };
    window.addEventListener("codeatlas:unauthorized", handleUnauthorized);
    return () => { active = false; window.removeEventListener("codeatlas:unauthorized", handleUnauthorized); };
  }, [token]);

  function authenticated(session) {
    saveSession(session.access_token, session.user);
    setToken(session.access_token);
    setUser(session.user);
    setAuthReady(true);
  }

  async function signOut() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* Clear the local session if the API is unavailable. */ }
    clearSession();
    sessionStorage.removeItem("codeatlas.selectedRepository");
    setToken(null);
    setUser(null);
  }

  function navigate(page) {
    if (!PAGES.has(page)) return;
    setActivePage(page);
    window.history.replaceState(null, "", "#" + page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (!authReady) return <main className="ca-auth-screen"><p className="ca-auth-loading">Restoring your workspace…</p></main>;
  if (!token || !user) return <AuthScreen onAuthenticated={authenticated} />;

  const toggleTheme = () => setTheme((current) => current === "dark" ? "light" : "dark");
  return (
    <div className="ca-site ca-app-shell ca-workspace-mode" id="home">
      <TopBar
        onMenuClick={() => setSidebarOpen((open) => !open)}
        onNavigate={navigate}
        user={user}
        onLogout={signOut}
        onSettings={() => navigate("settings")}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
      <div className={`ca-app-layout${sidebarOpen ? "" : " ca-app-layout--sidebar-closed"}`}>
        {sidebarOpen && window.innerWidth < 1200 && <button className="ca-sidebar-backdrop" type="button" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
        {sidebarOpen && <Sidebar activePage={activePage} onNavigate={(page) => {
          navigate(page);
          if (window.innerWidth < 1200) setSidebarOpen(false);
        }} />}
        <main className="ca-app-main ca-workspace-main" id="workspace-home">
          <div className="ca-workspace-welcome">
            <div>
              <p className="ca-kicker">CODEATLAS WORKSPACE</p>
              <h1>{PAGE_TITLES[activePage]}</h1>
              <p>{activePage === "dashboard" ? "Good to see you, " + user.display_name.split(" ")[0] + ". Your codebase insights are ready when you are." : "Understand the structure, connections, and health of your repositories."}</p>
            </div>
          </div>
          <PageErrorBoundary resetKey={activePage}><RepositoryWorkspace
            activePage={activePage}
            onNavigate={navigate}
            user={user}
            theme={theme}
            onToggleTheme={toggleTheme}
            onUserUpdated={(nextUser) => { setUser(nextUser); localStorage.setItem("codeatlas.user", JSON.stringify(nextUser)); }}
          /></PageErrorBoundary>
        </main>
      </div>
    </div>
  );
}
