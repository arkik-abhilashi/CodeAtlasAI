import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuthScreen from "./AuthScreen";

describe("AuthScreen", () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("submits login and returns the authenticated session", async () => {
    const onAuthenticated = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ access_token: "token", user: { id: "u1", email: "dev@example.com", display_name: "Dev" } }) }));
    render(<AuthScreen onAuthenticated={onAuthenticated} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "dev@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(expect.objectContaining({ access_token: "token" })));
    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/api/auth/login", expect.objectContaining({ method: "POST" }));
  });

  it("shows API errors without losing the form", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: "Email or password is incorrect" }) }));
    render(<AuthScreen onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "dev@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect");
  });
});
