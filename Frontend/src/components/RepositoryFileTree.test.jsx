import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import RepositoryFileTree from "./RepositoryFileTree";

const files = [
  { path: "src/algorithms/cryptography/caesarCipher.js", language: "JavaScript" },
  { path: "src/algorithms/cryptography/README.md", language: null },
  { path: "test/caesar.test.js", language: "JavaScript" },
  { path: "package.json", language: null },
];

describe("RepositoryFileTree", () => {
  it("renders directories collapsed and reveals nested files via search", () => {
    render(<RepositoryFileTree files={files} selectedPath="" onSelect={vi.fn()} />);
    expect(screen.getByText("package.json")).toBeInTheDocument();
    expect(screen.queryByText("caesarCipher.js")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search files and directories" }), { target: { value: "caesarCipher" } });
    expect(screen.getByText("caesarCipher.js")).toBeInTheDocument();
    expect(screen.getByText("cryptography")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search files and directories" }), { target: { value: "no-file-match" } });
    expect(screen.getByText("No matching files or directories.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search files and directories" }), { target: { value: "" } });
    expect(screen.queryByText("caesarCipher.js")).not.toBeInTheDocument();
  });

  it("loads the chosen file path", () => {
    const onSelect = vi.fn();
    render(<RepositoryFileTree files={files} selectedPath="" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "Expand test" }));
    fireEvent.click(screen.getByText("caesar.test.js"));
    expect(onSelect).toHaveBeenCalledWith("test/caesar.test.js");
  });
});
