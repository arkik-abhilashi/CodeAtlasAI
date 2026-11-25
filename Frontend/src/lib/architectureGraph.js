export const ROOT_FILES = "@root-files";
export const pathParent = (path) => path === "." ? null : path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : ".";

export function buildArchitectureScope(files, edges, scopePath = ".", entryPoints = []) {
  const descendants = (files || []).filter((file) => scopePath === "." || file.path.startsWith(scopePath + "/"));
  const childFor = (filePath) => {
    const rest = scopePath === "." ? filePath : filePath.slice(scopePath.length + 1);
    if (rest.includes("/")) return scopePath === "." ? rest.slice(0, rest.indexOf("/")) : scopePath + "/" + rest.slice(0, rest.indexOf("/"));
    return ROOT_FILES;
  };
  const moduleFiles = new Map();
  for (const file of descendants) {
    const child = childFor(file.path);
    if (!moduleFiles.has(child)) moduleFiles.set(child, []);
    moduleFiles.get(child).push(file);
  }
  const verifiedEdges = (edges || []).filter((edge) => edge.verified === true && edge.source && edge.target);
  const outgoing = new Map(); const incoming = new Map(); const relationships = new Map();
  for (const edge of verifiedEdges) {
    const sourceInside = scopePath === "." || edge.source.startsWith(scopePath + "/");
    const targetInside = scopePath === "." || edge.target.startsWith(scopePath + "/");
    if (sourceInside) {
      if (!outgoing.has(edge.source)) outgoing.set(edge.source, new Set());
      outgoing.get(edge.source).add(edge.target);
    }
    if (targetInside) {
      if (!incoming.has(edge.target)) incoming.set(edge.target, new Set());
      incoming.get(edge.target).add(edge.source);
    }
    if (!sourceInside || !targetInside) continue;
    const from = childFor(edge.source); const to = childFor(edge.target);
    if (from === to || !moduleFiles.has(from) || !moduleFiles.has(to)) continue;
    const key = from + "\u0000" + to;
    if (!relationships.has(key)) relationships.set(key, { source: from, target: to, count: 0, imports: [] });
    const relation = relationships.get(key); relation.count += 1; relation.imports.push(edge);
  }
  const entrySet = new Set(entryPoints || []);
  const nodes = [...moduleFiles].map(([id, members]) => {
    const directory = id === ROOT_FILES ? (scopePath === "." ? "." : scopePath) : id;
    const direct = members.filter((file) => id === ROOT_FILES ? (scopePath === "." ? !file.path.includes("/") : !file.path.slice(scopePath.length + 1).includes("/")) : true);
    const paths = new Set(members.map((file) => file.path));
    const incomingFiles = new Set(); const outgoingFiles = new Set();
    for (const edge of verifiedEdges) {
      if (paths.has(edge.target) && !paths.has(edge.source)) incomingFiles.add(edge.source);
      if (paths.has(edge.source) && !paths.has(edge.target)) outgoingFiles.add(edge.target);
    }
    const languages = new Map();
    for (const file of members) if (file.language) languages.set(file.language, (languages.get(file.language) || 0) + 1);
    const language = [...languages].sort((a, b) => b[1] - a[1])[0]?.[0] || "Mixed or non-source files";
    const children = new Set();
    for (const file of descendants) if (file.path.startsWith(directory === "." ? "\u0000" : directory + "/")) {
      const rest = file.path.slice(directory.length + (directory === "." ? 0 : 1));
      if (rest.includes("/")) children.add(rest.slice(0, rest.indexOf("/")));
    }
    const symbols = members.flatMap((file) => [
      ...(file.analysis?.classes || []).map((item) => ({ ...item, kind: "class", file: file.path })),
      ...(file.analysis?.functions || []).map((item) => ({ ...item, kind: "function", file: file.path })),
      ...(file.analysis?.methods || []).map((item) => ({ ...item, kind: "method", file: file.path })),
      ...(file.analysis?.exports || []).map((item) => ({ ...item, kind: "export", file: file.path })),
    ]).slice(0, 12);
    return {
      id, path: id === ROOT_FILES ? (scopePath === "." ? "(root files)" : scopePath + "/(root files)") : id,
      name: id === ROOT_FILES ? "Root-level files" : id.split("/").at(-1), kind: id === ROOT_FILES ? "root-files" : "module",
      files: members, fileCount: members.length, directFileCount: direct.length, language,
      incoming: incomingFiles, outgoing: outgoingFiles, childDirectories: [...children].sort(), symbols,
      entryPoints: members.filter((file) => entrySet.has(file.path)).map((file) => file.path),
    };
  });
  const relationList = [...relationships.values()];
  const rootFiles = descendants.filter((file) => childFor(file.path) === ROOT_FILES);
  const boundaryIncoming = new Set(); const boundaryOutgoing = new Set();
  const scopeFiles = new Set(descendants.map((file) => file.path));
  for (const edge of verifiedEdges) {
    if (scopeFiles.has(edge.target) && !scopeFiles.has(edge.source)) boundaryIncoming.add(edge.source);
    if (scopeFiles.has(edge.source) && !scopeFiles.has(edge.target)) boundaryOutgoing.add(edge.target);
  }
  return { scopePath, files: descendants, nodes: nodes.sort((a, b) => a.name.localeCompare(b.name)), edges: relationList, verifiedEdges, entries: entrySet, rootFiles, boundaryIncoming, boundaryOutgoing };
}

