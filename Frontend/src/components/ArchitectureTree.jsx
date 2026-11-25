import { useMemo, useState } from "react";

function makeTree(files, edges, entryPoints, repositoryName) {
  const root = { id: ".", name: repositoryName || "Repository", path: ".", kind: "directory", children: new Map(), files: [] };
  const dirs = new Map([[".", root]]); const fileNodes = new Map();
  for (const file of files || []) {
    root.files.push(file);
    const parts = file.path.split("/"); let parent = root; let path = "";
    for (const part of parts.slice(0, -1)) {
      path = path ? path + "/" + part : part;
      if (!parent.children.has(part)) { const node = { id: path, name: part, path, kind: "directory", children: new Map(), files: [] }; parent.children.set(part, node); dirs.set(path, node); }
      parent = parent.children.get(part); parent.files.push(file);
    }
    const name = parts.at(-1); const node = { id: file.path, name, path: file.path, kind: "file", file, files: [file], children: new Map() };
    parent.children.set(name + "\u0000file", node); fileNodes.set(file.path, node);
  }
  const verified = (edges || []).filter((edge) => edge.verified === true && fileNodes.has(edge.source) && fileNodes.has(edge.target));
  const incoming = new Map(); const outgoing = new Map(); const entries = new Set(entryPoints || []);
  const crossIn = new Map(); const crossOut = new Map();
  for (const edge of verified) {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, new Set()); outgoing.get(edge.source).add(edge.target);
    if (!incoming.has(edge.target)) incoming.set(edge.target, new Set()); incoming.get(edge.target).add(edge.source);
    for (const dir of dirs.values()) {
      if (dir.path !== "." && edge.source.startsWith(dir.path + "/") && !edge.target.startsWith(dir.path + "/")) { if (!crossOut.has(dir.path)) crossOut.set(dir.path, new Set()); crossOut.get(dir.path).add(edge.target); }
      if (dir.path !== "." && edge.target.startsWith(dir.path + "/") && !edge.source.startsWith(dir.path + "/")) { if (!crossIn.has(dir.path)) crossIn.set(dir.path, new Set()); crossIn.get(dir.path).add(edge.source); }
    }
  }
  const category = (path, isDirectory) => {
    const p = path.toLowerCase();
    if (/(^|\/)(__tests__|tests?|specs?)(\/|\.|$)|\.(test|spec)\.[^.]+$/.test(p)) return "Tests";
    if (/(^|\/)(examples?|samples?)(\/|\.|$)/.test(p)) return "Examples";
    if (/(^|\/)(config|configs|\.github|scripts|build)(\/|\.|$)|(^|\/)(vite|webpack|jest|eslint|babel|rollup)\.config\./.test(p)) return "Configuration & tooling";
    if (!isDirectory && entries.has(path)) return "Entry point";
    return isDirectory ? "Module" : "Other";
  };
  const annotate = (node) => {
    node.category = category(node.path, node.kind === "directory"); node.incoming = new Set(); node.outgoing = new Set();
    if (node.kind === "file") {
      node.incoming = incoming.get(node.path) || new Set(); node.outgoing = outgoing.get(node.path) || new Set();
      node.symbols = [["classes", "class"], ["functions", "function"], ["methods", "method"], ["exports", "export"]].flatMap(([key, type]) => (node.file.analysis?.[key] || []).map((item) => ({ ...item, type })));
    } else {
      node.incoming = crossIn.get(node.path) || new Set(); node.outgoing = crossOut.get(node.path) || new Set();
      node.symbols = node.files.flatMap((file) => [["classes", "class"], ["functions", "function"]].flatMap(([key, type]) => (file.analysis?.[key] || []).map((item) => ({ ...item, type, file: file.path })))).slice(0, 16);
    }
    node.children.forEach(annotate);
  };
  annotate(root);
  return { root, dirs, fileNodes, entries, verified, category };
}

export default function ArchitectureTree({ files, edges, entryPoints, repositoryName, onOpenFile }) {
  const model = useMemo(() => makeTree(files, edges, entryPoints, repositoryName), [files, edges, entryPoints, repositoryName]);
  const [expanded, setExpanded] = useState(() => { try { return new Set(JSON.parse(sessionStorage.getItem("codeatlas.architecture.expanded") || '["."]')); } catch { return new Set(["."]); } });
  const [selectedId, setSelectedId] = useState(() => sessionStorage.getItem("codeatlas.architecture.selected") || ".");
  const [query, setQuery] = useState(""); const [language, setLanguage] = useState(""); const [category, setCategory] = useState("");
  const all = useMemo(() => { const rows = []; const visit = (node) => { rows.push(node); node.children.forEach(visit); }; visit(model.root); return rows; }, [model]);
  const selected = all.find((node) => node.id === selectedId) || model.root;
  const languages = [...new Set((files || []).map((file) => file.language).filter(Boolean))].sort();
  const filtered = new Set(all.filter((node) => {
    const text = (node.path + " " + node.name + " " + (node.symbols || []).map((item) => item.name).join(" ")).toLowerCase();
    const hasLanguage = !language || (node.kind === "file" ? node.file.language === language : node.files.some((file) => file.language === language));
    const hasCategory = !category || node.category === category || (node.kind === "directory" && node.files.some((file) => model.category(file.path, false) === category));
    return (!query || text.includes(query.toLowerCase())) && hasLanguage && hasCategory;
  }).map((node) => node.id));
  const visible = new Set(filtered);
  for (const node of all) if (filtered.has(node.id)) {
    let parent = node.path.includes("/") ? node.path.slice(0, node.path.lastIndexOf("/")) : ".";
    while (parent !== node.path) { visible.add(parent); if (parent === ".") break; parent = parent.includes("/") ? parent.slice(0, parent.lastIndexOf("/")) : "."; }
  }
  const toggle = (id) => setExpanded((old) => { const next = new Set(old); if (next.has(id)) next.delete(id); else next.add(id); sessionStorage.setItem("codeatlas.architecture.expanded", JSON.stringify([...next])); return next; });
  const selectId = (id) => { setSelectedId(id); sessionStorage.setItem("codeatlas.architecture.selected", id); };
  const expandAll = () => { const next = new Set(all.filter((node) => node.kind === "directory").map((node) => node.id)); sessionStorage.setItem("codeatlas.architecture.expanded", JSON.stringify([...next])); setExpanded(next); };
  const collapseAll = () => { sessionStorage.setItem("codeatlas.architecture.expanded", '["."]'); setExpanded(new Set(["."])); };
  const getRelated = (direction) => {
    if (selected.kind === "file") return [...(direction === "incoming" ? selected.incoming : selected.outgoing)];
    const paths = new Set();
    for (const file of selected.files) for (const edge of model.verified) {
      if (direction === "incoming" && edge.target === file.path && !selected.files.some((item) => item.path === edge.source)) paths.add(edge.source);
      if (direction === "outgoing" && edge.source === file.path && !selected.files.some((item) => item.path === edge.target)) paths.add(edge.target);
    }
    return [...paths];
  };
  const render = (node, depth) => {
    const children = [...node.children.values()].filter((item) => visible.has(item.id)).sort((a, b) => Number(b.kind === "directory") - Number(a.kind === "directory") || a.name.localeCompare(b.name));
    return <div className="ca-arch-branch" key={node.id}>
      <div className={"ca-arch-row" + (selected.id === node.id ? " is-selected" : "")} style={{ "--tree-depth": depth }}>
        {node.kind === "directory" || node.symbols?.length ? <button className="ca-arch-toggle" aria-label={(expanded.has(node.kind === "file" ? "symbols:" + node.id : node.id) ? "Collapse " : "Expand ") + node.name} onClick={() => toggle(node.kind === "file" ? "symbols:" + node.id : node.id)}>{expanded.has(node.kind === "file" ? "symbols:" + node.id : node.id) ? "▾" : "▸"}</button> : <span className="ca-arch-toggle ca-arch-spacer" />}
        <button className="ca-arch-select" onClick={() => selectId(node.id)} onDoubleClick={() => node.kind === "file" && onOpenFile(node.path)}>
          <span className="ca-arch-icon">{node.kind === "directory" ? (expanded.has(node.id) ? "📂" : "📁") : "▤"}</span><span className="ca-arch-name">{node.name}</span>
          {node.kind === "file" && model.entries.has(node.path) && <span className="ca-entry-tag">ENTRY</span>}
          {node.kind === "directory" && !["Module", "Other"].includes(node.category) && <span className="ca-entry-tag">{node.category}</span>}
          {node.kind === "directory" && <span className="ca-arch-meta">{node.files.length} files · {node.incoming.size} in / {node.outgoing.size} out</span>}
          {node.kind === "file" && <span className="ca-arch-meta">{node.file.language || "Other"}</span>}
        </button>
      </div>
      {node.kind === "directory" && expanded.has(node.id) && <div className="ca-arch-children">{children.map((child) => render(child, depth + 1))}</div>}
      {node.kind === "file" && expanded.has("symbols:" + node.id) && <div className="ca-arch-symbols">{(node.symbols || []).map((symbol, index) => <button key={symbol.name + index} onClick={() => selectId(node.id)}>{symbol.type} · {symbol.name}</button>)}</div>}
    </div>;
  };
  const relatedNode = (path) => all.find((node) => node.path === path);
  const crumbs = selected.path === "." ? [model.root] : [model.root, ...selected.path.split("/").map((_, index, parts) => all.find((node) => node.path === parts.slice(0, index + 1).join("/"))).filter(Boolean)];
  const rootSummary = (files?.length || 0) + " analyzed files across " + Math.max(0, model.dirs.size - 1) + " directories. " + (languages.slice(0, 2).join(" and ") || "No supported languages") + " represented; " + model.entries.size + " likely entry points; " + model.verified.length + " verified local import relationships.";
  const majorAreas = [...model.root.children.values()].filter((node) => node.kind === "directory").map((node) => node.name).slice(0, 6);
  const entrySummary = [...model.entries].slice(0, 5).join(", ");
  const symbols = selected.symbols || [];
  return <section className="ca-high-architecture">
    <header><div><span>REPOSITORY ARCHITECTURE</span><small>Evidence-based view from parsed source and verified imports</small></div><span>{files.length} files · {model.dirs.size - 1} directories</span></header>
    <div className="ca-arch-overview"><strong>{repositoryName}</strong><p>{rootSummary}{majorAreas.length ? " Major areas: " + majorAreas.join(", ") + "." : ""}{entrySummary ? " Entry points: " + entrySummary + "." : ""}</p><small>Descriptions and categories are inferred from static evidence; they do not assert runtime behavior.</small></div>
    <div className="ca-arch-toolbar"><input type="search" aria-label="Search architecture tree" placeholder="Search files, directories, symbols" value={query} onChange={(event) => setQuery(event.target.value)} /><select aria-label="Filter by language" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="">All languages</option>{languages.map((item) => <option key={item}>{item}</option>)}</select><select aria-label="Filter by category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{["Entry point", "Tests", "Examples", "Configuration & tooling"].map((item) => <option key={item}>{item}</option>)}</select><button onClick={expandAll}>Expand all</button><button onClick={collapseAll}>Collapse all</button></div>
    <div className="ca-arch-breadcrumb">{crumbs.map((node, index) => <button key={node.id} onClick={() => selectId(node.id)}>{(index ? " / " : "") + node.name}</button>)}</div>
    <div className="ca-arch-explorer"><div className="ca-arch-tree" role="tree" aria-label="Repository architecture tree">{render(model.root, 0)}{visible.size <= 1 && query && <p className="ca-no-results">No matching files or modules.</p>}</div>
      <aside className="ca-arch-inspector"><p className="ca-kicker">{selected.kind === "directory" ? "MODULE INSPECTOR" : "FILE INSPECTOR"}</p><h3>{selected.path === "." ? repositoryName : selected.path}</h3><small>{selected.kind === "directory" ? selected.files.length + " files · " + [...selected.children.values()].filter((node) => node.kind === "directory").length + " child modules" : (selected.file.language || "Other") + " · " + (selected.file.size ?? selected.file.size_bytes ?? 0) + " bytes"}</small>
        {selected.kind === "directory" && <><h4>Structural description <span>inferred</span></h4><p>Contains {selected.files.length} files. {selected.incoming.size} verified external files import this module; it imports {selected.outgoing.size} verified external files.</p><h4>Primary languages</h4><p>{[...new Set(selected.files.map((file) => file.language).filter(Boolean))].join(", ") || "No parsed language"}</p></>}
        {symbols.length > 0 && <><h4>Important symbols</h4><ul className="ca-arch-symbol-list">{symbols.slice(0, 12).map((item, index) => <li key={item.name + index}><code>{item.name}</code><span>{item.type}{item.file ? " · " + item.file : ""}</span></li>)}</ul></>}
        {selected.kind === "file" && <><h4>Imports</h4>{(selected.file.analysis?.imports || []).slice(0, 24).map((item, index) => <p className="ca-arch-detail-line" key={item.name + index}><code>{item.name}</code><small>line {item.line}</small></p>)}<h4>Exports</h4>{(selected.file.analysis?.exports || []).slice(0, 24).map((item, index) => <p className="ca-arch-detail-line" key={item.name + index}><code>{item.name}</code></p>)}<button className="ca-button ca-button--secondary" onClick={() => onOpenFile(selected.path)}>Open in Code Explorer</button></>}
        <h4>Verified incoming dependencies</h4>{getRelated("incoming").slice(0, 30).map((path) => <button className="ca-arch-related" key={path} onClick={() => selectId(relatedNode(path)?.id || ".")}>{path}</button>)}{!getRelated("incoming").length && <p>None found.</p>}
        <h4>Verified outgoing dependencies</h4>{getRelated("outgoing").slice(0, 30).map((path) => <button className="ca-arch-related" key={path} onClick={() => selectId(relatedNode(path)?.id || ".")}>{path}</button>)}{!getRelated("outgoing").length && <p>None found.</p>}
      </aside>
    </div>
  </section>;
}

