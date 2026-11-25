import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import RepositoryWorkspace from "./RepositoryWorkspace";

function TestWorkspace() {
  const [activePage, setActivePage] = useState("repositories");
  return <><nav><button onClick={() => setActivePage("dashboard")}>Dashboard route</button><button onClick={() => setActivePage("repositories")}>Repositories route</button></nav><RepositoryWorkspace activePage={activePage} onNavigate={setActivePage} user={{ display_name: "Dev" }} onUserUpdated={vi.fn()} /></>;
}

function setupApi() {
  const calls = [];
  const store = { jobs: [], repositories: [] };
  vi.stubGlobal("fetch", vi.fn(async (url, options = {}) => {
    calls.push({ url, options });
    const path = new URL(url).pathname;
    if (path === "/api/repositories/upload" && options.method === "POST") {
      const repository = { id: "repo-1", name: "sample", source_type: "upload", status: "running", progress: 36 };
      const job = { id: "job-1", repository_id: "repo-1", status: "running", progress: 36, stage: "Parsing source files: 36/100", files_discovered: 150, files_processed: 36, files_skipped: 5, skip_reasons: { "unsupported file type": 5 } };
      store.repositories = [repository]; store.jobs = [job];
      return { ok: true, status: 202, json: async () => ({ job_id: job.id, repository_id: repository.id, status: "queued" }) };
    }
    if (path === "/api/repositories" && !options.method) return { ok: true, status: 200, json: async () => store.repositories };
    if (path === "/api/jobs" && !options.method) return { ok: true, status: 200, json: async () => store.jobs };
    if (path === "/api/workers/status" && !options.method) return { ok: true, status: 200, json: async () => ({ queue: "codeatlas-analysis", available: true, worker_count: 1, workers: [{ state: "idle" }], reason: null }) };
    if (path === "/api/jobs/job-1/cancel") {
      store.jobs = store.jobs.map((job) => ({ ...job, status: "cancelled", stage: "Analysis cancelled by user" }));
      return { ok: true, status: 200, json: async () => store.jobs[0] };
    }
    throw new Error(`Unexpected request: ${url}`);
  }));
  return { calls, store };
}

describe("RepositoryWorkspace persistent imports", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

  it("restores active import progress after navigating away and back", async () => {
    const { calls } = setupApi();
    render(<TestWorkspace />);
    const zip = new File(["zip-bytes"], "sample.zip", { type: "application/zip" });
    fireEvent.change(await screen.findByLabelText("Upload a ZIP"), { target: { files: [zip] } });
    fireEvent.submit(screen.getByRole("button", { name: "Upload & analyze" }).closest("form"));
    await screen.findByText("Parsing source files: 36/100");
    expect(screen.getAllByText("36%", { exact: true })).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Dashboard route" }));
    await waitFor(() => expect(screen.queryByLabelText("Upload a ZIP")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Repositories route" }));
    expect(await screen.findByText("Parsing source files: 36/100")).toBeInTheDocument();
    expect(calls.some((call) => call.url.endsWith("/api/jobs?limit=50"))).toBe(true);
  });

  it("reconstructs job progress after the workspace is remounted and keeps the GitHub URL", async () => {
    const { store } = setupApi();
    store.jobs = [{ id: "job-1", repository_id: "repo-1", status: "running", progress: 62, stage: "Resolving imports: 18/30", files_discovered: 150, files_processed: 150, files_skipped: 5, skip_reasons: {} }];
    store.repositories = [{ id: "repo-1", name: "sample", source_type: "github", source_url: "https://github.com/owner/repo", status: "running", progress: 62 }];
    localStorage.setItem("codeatlas.importUrl", "https://github.com/owner/repo");
    const first = render(<TestWorkspace />);
    expect(await screen.findByText("Resolving imports: 18/30")).toBeInTheDocument();
    first.unmount();
    render(<TestWorkspace />);
    expect(await screen.findByText("Resolving imports: 18/30")).toBeInTheDocument();
    expect(screen.getByLabelText("Public GitHub repository")).toHaveValue("https://github.com/owner/repo");
  });

  it("shows completed and failed jobs with their persisted terminal states", async () => {
    const { store } = setupApi();
    store.jobs = [
      { id: "done", repository_id: "repo-done", status: "completed", progress: 100, stage: "Analysis complete", files_discovered: 175, files_processed: 160, files_skipped: 15, skip_reasons: {} },
      { id: "bad", repository_id: "repo-bad", status: "failed", progress: 22, stage: "Import failed", error_message: "GitHub archive could not be downloaded", files_discovered: 0, files_processed: 0, files_skipped: 0, skip_reasons: {} },
    ];
    store.repositories = [{ id: "repo-done", name: "finished", status: "completed" }, { id: "repo-bad", name: "broken", status: "failed" }];
    render(<TestWorkspace />);
    expect(await screen.findByText("Analysis complete")).toBeInTheDocument();
    expect(screen.getByText("GitHub archive could not be downloaded")).toBeInTheDocument();
    expect(screen.getByText("160 processed · 15 skipped · 175 discovered")).toBeInTheDocument();
  });

  it("shows the idle worker as connected in the repository import panel", async () => {
    setupApi();
    render(<TestWorkspace />);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Analysis worker connected · 1 idle"));
  });
});
