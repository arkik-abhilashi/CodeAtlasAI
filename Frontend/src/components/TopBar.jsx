import AccountMenu from "./AccountMenu";

export default function TopBar({ onMenuClick, onNavigate, user, onLogout, onSettings, theme, onToggleTheme }) {
  const nextTheme = theme === "dark" ? "light" : "dark";
  return (
    <header className="ca-topbar">
      <div className="ca-topbar__brand">
        <button type="button" className="ca-topbar__menu" onClick={onMenuClick} aria-label="Toggle sidebar" title="Toggle sidebar"><span /><span /><span /></button>
        <a className="ca-wordmark" href="#dashboard" aria-label="CodeAtlas overview" onClick={(event) => { event.preventDefault(); onNavigate("dashboard"); }}>CODE<span>ATLAS</span></a>
      </div>
      <div className="ca-topbar__right">
        <span className="ca-topbar__context"><i aria-hidden="true" /> Personal workspace</span>
        <button type="button" className="ca-theme-toggle" onClick={onToggleTheme} aria-label={"Switch to " + nextTheme + " appearance"} title={"Switch to " + nextTheme + " appearance"}>
          <span aria-hidden="true">{theme === "dark" ? "☼" : "◐"}</span><span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>
        <AccountMenu user={user} onLogout={onLogout} onSettings={onSettings} />
      </div>
    </header>
  );
}
