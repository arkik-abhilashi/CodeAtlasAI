import { useMemo, useState } from "react";

function makeFileTree(files) {
  const root = { path: ".", name: "Repository", kind: "directory", children: new Map(), fileCount: 0 };
  for (const file of files || []) {
    root.fileCount += 1;
    const parts = file.path.split("/"); let parent = root; let path = "";
    for (const part of parts.slice(0, -1)) {
      path = path ? path + "/" + part : part;
      if (!parent.children.has(part)) parent.children.set(part, { path, name: part, kind: "directory", children: new Map(), fileCount: 0 });
      parent = parent.children.get(part); parent.fileCount += 1;
    }
    const name = parts.at(-1);
    parent.children.set(name + "\u0000file", { path: file.path, name, kind: "file", file, children: new Map(), fileCount: 1 });
  }
  return root;
}

export default function RepositoryFileTree({ files, selectedPath, onSelect }) {
  const root = useMemo(() => makeFileTree(files), [files]);
  const [expanded, setExpanded] = useState(() => new Set(["."]));
  const [query, setQuery] = useState("");
  const all = useMemo(() => { const nodes = []; const visit = (node) => { nodes.push(node); node.children.forEach(visit); }; visit(root); return nodes; }, [root]);
  const matching = useMemo(() => new Set(all.filter((node) => !query || node.path.toLowerCase().includes(query.toLowerCase())).map((node) => node.path)), [all, query]);
  const shown = new Set(matching);
  if (query) for (const node of all) if (matching.has(node.path)) {
    let parent = node.path.includes("/") ? node.path.slice(0, node.path.lastIndexOf("/")) : ".";
    while (parent && parent !== node.path) { shown.add(parent); if (parent === ".") break; parent = parent.includes("/") ? parent.slice(0, parent.lastIndexOf("/")) : "."; }
  }
  const toggle = (path) => setExpanded((previous) => { const next = new Set(previous); if (next.has(path)) next.delete(path); else next.add(path); return next; });
  const render = (node, depth) => {
    const children = [...node.children.values()].filter((child) => shown.has(child.path)).sort((a, b) => Number(b.kind === "directory") - Number(a.kind === "directory") || a.name.localeCompare(b.name));
    const isOpen = expanded.has(node.path) || Boolean(query);
    if (node.kind === "file") return <button type="button" key={node.path} className={`ca-tree-file${selectedPath === node.path ? " is-selected" : ""}`} style={{ "--depth": depth }} onClick={() => onSelect(node.path)} title={node.path}><span className="ca-file-tree-icon">{node.file.language === "Python" ? "Py" : node.file.language?.includes("TypeScript") ? "TS" : node.file.language?.includes("JavaScript") ? "JS" : "·"}</span><span className="ca-file-tree-name">{node.name}</span></button>;
    return <div className="ca-file-tree-branch" key={node.path}><div className="ca-file-tree-row" style={{ "--depth": depth }}><button type="button" className="ca-file-tree-toggle" aria-label={`${isOpen ? "Collapse" : "Expand"} ${node.name}`} onClick={() => toggle(node.path)}>{isOpen ? "▾" : "▸"}</button><button type="button" className="ca-file-tree-directory" onClick={() => toggle(node.path)} title={node.path}><span>📁</span><span>{node.name}</span><small>{node.fileCount}</small></button></div>{isOpen && <div className="ca-file-tree-children">{children.map((child) => render(child, depth + 1))}</div>}</div>;
  };
  return <div className="ca-file-tree-wrap"><input className="ca-file-tree-search" type="search" aria-label="Search files and directories" placeholder="Search files" value={query} onChange={(event) => setQuery(event.target.value)} /><div className="ca-file-tree" role="tree" aria-label="Repository file tree">{render(root, 0)}{query && matching.size === 0 && <p className="ca-no-results">No matching files or directories.</p>}</div></div>;
}
