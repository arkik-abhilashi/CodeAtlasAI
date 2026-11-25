import { useEffect, useMemo, useRef, useState } from "react";

const symbolGroups = [
  ["classes", "Class"],
  ["types", "Type"],
  ["functions", "Function"],
  ["methods", "Method"],
  ["exports", "Export"],
];

export default function QuickOpen({ files, onOpenFile, onOpenModule }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef(null);
  const modules = useMemo(() => [...new Set(files.flatMap((file) => {
    const parts = file.path.split("/");
    return parts.slice(0, -1).map((_, index) => parts.slice(0, index + 1).join("/"));
  }))].sort(), [files]);
  const results = useMemo(() => {
    const entries = [
      ...modules.map((path) => ({ kind: "Module", label: path, path, search: path })),
      ...files.map((file) => ({ kind: "File", label: file.path, path: file.path, search: file.path })),
      ...files.flatMap((file) => symbolGroups.flatMap(([key, kind]) => (file.analysis?.[key] || []).map((symbol) => ({
        kind, label: symbol.name, path: file.path, line: symbol.line, search: `${symbol.name} ${file.path} ${kind}`,
      })))),
    ];
    const term = query.trim().toLowerCase();
    return entries.filter((entry) => !term || entry.search.toLowerCase().includes(term)).slice(0, 60);
  }, [files, modules, query]);
  const close = () => { setOpen(false); setQuery(""); setActiveIndex(0); };
  const choose = (item) => {
    if (!item) return;
    if (item.kind === "Module") onOpenModule(item.path);
    else onOpenFile(item.path);
    close();
  };

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen(true); }
      if (event.key === "Escape" && open) close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);
  useEffect(() => { if (open) window.setTimeout(() => inputRef.current?.focus(), 0); }, [open]);
  return <>
    <button type="button" className="ca-button ca-button--secondary ca-quick-open-trigger" onClick={() => setOpen(true)}>Quick open <kbd>Ctrl K</kbd></button>
    {open && <div className="ca-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}>
      <section className="ca-quick-open" role="dialog" aria-modal="true" aria-label="Quick open">
        <input ref={inputRef} type="search" value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }} onKeyDown={(event) => {
          if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((index) => Math.min(index + 1, results.length - 1)); }
          if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((index) => Math.max(index - 1, 0)); }
          if (event.key === "Enter") { event.preventDefault(); choose(results[activeIndex]); }
        }} placeholder="Find files, modules, classes, or functions" aria-label="Quick open search" />
        <div className="ca-quick-open__results">{results.length ? results.map((item, index) => <button key={`${item.kind}-${item.path}-${item.label}-${item.line || ""}`} type="button" className={index === activeIndex ? "is-active" : ""} onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(item)}><span>{item.kind}</span><strong>{item.label}</strong><small>{item.kind === "Module" ? "Architecture module" : `${item.path}${item.line ? ` · line ${item.line}` : ""}`}</small></button>) : <p>No matching repository items.</p>}</div>
      </section>
    </div>}
  </>;
}
