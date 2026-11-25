import { useEffect, useRef, useState } from "react";

export default function AccountMenu({ user, onLogout, onSettings }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const initial = user?.display_name?.trim()?.charAt(0)?.toUpperCase() || "U";

  useEffect(() => {
    function handlePointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false);
    }
    function handleKeyDown(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div className="ca-account-menu" ref={rootRef}>
      <button
        type="button"
        className="ca-account-menu__trigger"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <span className="ca-account-avatar">{initial}</span>
        <span className="ca-account-menu__label">Account</span>
        <span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div className="ca-account-menu__panel" role="menu">
          <div className="ca-account-menu__profile">
            <span className="ca-account-avatar">{initial}</span>
            <div><strong>{user?.display_name || "Your workspace"}</strong><small>{user?.email || "CodeAtlas AI"}</small></div>
          </div>
          <button role="menuitem" type="button" onClick={() => { onSettings?.(); setOpen(false); }}>Settings</button>
          <button role="menuitem" type="button" onClick={() => { onLogout?.(); setOpen(false); }}>Sign out</button>
        </div>
      )}
    </div>
  );
}
