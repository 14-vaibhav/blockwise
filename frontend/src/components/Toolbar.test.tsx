import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initialState } from "../state/environment";
import Toolbar from "./Toolbar";

describe("Toolbar", () => {
  it("disables undo/redo when history is empty", () => {
    render(<Toolbar state={initialState("grass")} dispatch={vi.fn()} onApply={vi.fn()} applying={false} />);
    expect(screen.getByText("↶ Undo")).toBeDisabled();
    expect(screen.getByText("↷ Redo")).toBeDisabled();
  });

  it("enables undo once history has an entry, and clicking it dispatches UNDO", () => {
    const dispatch = vi.fn();
    const state = { ...initialState("grass"), history: { past: [[{ r: 0, c: 0, from: "grass", to: "water" }]], future: [] } };
    render(<Toolbar state={state} dispatch={dispatch} onApply={vi.fn()} applying={false} />);
    const undo = screen.getByText("↶ Undo");
    expect(undo).not.toBeDisabled();
    fireEvent.click(undo);
    expect(dispatch).toHaveBeenCalledWith({ type: "UNDO" });
  });

  it("switching tools dispatches SET_TOOL", () => {
    const dispatch = vi.fn();
    render(<Toolbar state={initialState("grass")} dispatch={dispatch} onApply={vi.fn()} applying={false} />);
    fireEvent.click(screen.getByText("Erase"));
    expect(dispatch).toHaveBeenCalledWith({ type: "SET_TOOL", tool: "erase" });
  });

  it("shows a busy label on the Apply button while applying", () => {
    render(<Toolbar state={initialState("grass")} dispatch={vi.fn()} onApply={vi.fn()} applying={true} />);
    expect(screen.getByText("Simulating…")).toBeDisabled();
  });
});
