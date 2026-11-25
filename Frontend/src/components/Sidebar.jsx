const items = [
  { icon: "◫", label: "Overview", id: "dashboard", href: "#dashboard" },
  { icon: "▤", label: "Repositories", id: "repositories", href: "#repositories" },
  { icon: "⌕", label: "Code explorer", id: "files", href: "#files" },
  { icon: "⌘", label: "Architecture", id: "architecture", href: "#architecture" },
  { icon: "◉", label: "Reports", id: "reports", href: "#reports" },
];

export default function Sidebar({ onNavigate, activePage = "dashboard" }) {
  return (
    <aside className="ca-app-sidebar" aria-label="CodeAtlas workspace navigation">
      <p className="ca-app-sidebar__label">WORKSPACE</p>
      <nav>
        {items.map((item) => (
          <a
            key={item.id}
            href={item.href}
            className={activePage === item.id ? "is-active" : ""}
            aria-current={activePage === item.id ? "page" : undefined}
            onClick={(event) => { event.preventDefault(); onNavigate?.(item.id); }}
          >
            <span aria-hidden="true">{item.icon}</span>{item.label}
          </a>
        ))}
      </nav>
      <div className="ca-app-sidebar__bottom">
        <p className="ca-app-sidebar__label">PREFERENCES</p>
        <a href="#settings" className={activePage === "settings" ? "is-active" : ""} aria-current={activePage === "settings" ? "page" : undefined} onClick={(event) => { event.preventDefault(); onNavigate?.("settings"); }}>
          <span aria-hidden="true">⚙</span>Settings
        </a>
        <div className="ca-sidebar-note">
          <span className="ca-status-dot" />
          <div><strong>Private workspace</strong><small>Your repositories stay yours</small></div>
        </div>
      </div>
    </aside>
  );
}
