import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("workspace appearance", () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.unstubAllGlobals();
  });

  it("switches the full document theme and restores the saved preference", async () => {
    localStorage.setItem("codeatlas.accessToken", "test-token");
    localStorage.setItem("codeatlas.user", JSON.stringify({ id: "u-1", email: "dev@example.com", display_name: "Dev" }));
    localStorage.setItem("codeatlas.theme", "dark");
    document.documentElement.dataset.theme = "dark";
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/api/auth/me")) return { ok: true, status: 200, json: async () => ({ id: "u-1", email: "dev@example.com", display_name: "Dev" }) };
      if (url.endsWith("/api/repositories")) return { ok: true, status: 200, json: async () => [] };
      throw new Error("Unexpected request: " + url);
    }));

    const first = render(<App />);
    const switchButton = await screen.findByRole("button", { name: "Switch to light appearance" });
    fireEvent.click(switchButton);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(localStorage.getItem("codeatlas.theme")).toBe("light");
    first.unmount();

    render(<App />);
    await screen.findByRole("button", { name: "Switch to dark appearance" });
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("keeps desktop navigation persistent and preserves the drawer across tablet and mobile resizes", async () => {
    localStorage.setItem("codeatlas.accessToken", "test-token");
    localStorage.setItem("codeatlas.user", JSON.stringify({ id: "u-1", email: "dev@example.com", display_name: "Dev" }));
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (url.endsWith("/api/auth/me")) return { ok: true, status: 200, json: async () => ({ id: "u-1", email: "dev@example.com", display_name: "Dev" }) };
      if (url.endsWith("/api/repositories")) return { ok: true, status: 200, json: async () => [] };
      if (url.endsWith("/api/jobs")) return { ok: true, status: 200, json: async () => [] };
      throw new Error("Unexpected request: " + url);
    }));

    for (const width of [1920, 1600, 1366, 1280]) {
      window.innerWidth = width;
      const view = render(<App />);
      expect(await screen.findByLabelText("CodeAtlas workspace navigation")).toBeInTheDocument();
      view.unmount();
    }

    window.innerWidth = 1920;
    const view = render(<App />);
    await screen.findByLabelText("CodeAtlas workspace navigation");
    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(screen.queryByLabelText("CodeAtlas workspace navigation")).not.toBeInTheDocument();
    window.innerWidth = 1600;
    fireEvent(window, new Event("resize"));
    expect(screen.queryByLabelText("CodeAtlas workspace navigation")).not.toBeInTheDocument();

    window.innerWidth = 1024;
    fireEvent(window, new Event("resize"));
    expect(screen.queryByLabelText("CodeAtlas workspace navigation")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(await screen.findByLabelText("CodeAtlas workspace navigation")).toBeInTheDocument();

    for (const width of [768, 390]) {
      window.innerWidth = width;
      fireEvent(window, new Event("resize"));
      expect(screen.getByLabelText("CodeAtlas workspace navigation")).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));
    await waitFor(() => expect(screen.queryByLabelText("CodeAtlas workspace navigation")).not.toBeInTheDocument());

    window.innerWidth = 1280;
    fireEvent(window, new Event("resize"));
    expect(await screen.findByLabelText("CodeAtlas workspace navigation")).toBeInTheDocument();
    view.unmount();
  });
});
