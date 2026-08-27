import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { initialState } from "../state/environment";
import type { MaterialsResponse } from "../types";
import MaterialPalette from "./MaterialPalette";

const materialsResp: MaterialsResponse = {
  materials: {
    grass: { label: "Grass / lawn", group: "Vegetation", colour: "#8bc34a", canopy: 0, impervious: 0, albedo: 0.25 },
    tree_dense: {
      label: "Tree canopy (dense)",
      group: "Vegetation",
      colour: "#1b5e20",
      canopy: 1,
      impervious: 0,
      albedo: 0.18,
      warning: null,
    },
    light_paving: {
      label: "Light / reflective paving",
      group: "Paving",
      colour: "#e0e0e0",
      canopy: 0,
      impervious: 1,
      albedo: 0.4,
      warning: "Cools air slightly but raises radiant heat on pedestrians.",
    },
  },
  palette: {
    Vegetation: [
      { key: "grass", label: "Grass / lawn", colour: "#8bc34a" },
      { key: "tree_dense", label: "Tree canopy (dense)", colour: "#1b5e20" },
    ],
    Paving: [{ key: "light_paving", label: "Light / reflective paving", colour: "#e0e0e0" }],
  },
  default_material: "grass",
  cell_m: 40,
  coefficients: {} as MaterialsResponse["coefficients"],
};

describe("MaterialPalette", () => {
  it("selecting a material dispatches SET_MATERIAL", () => {
    const dispatch = vi.fn();
    render(<MaterialPalette materialsResp={materialsResp} state={initialState("grass")} dispatch={dispatch} />);
    fireEvent.click(screen.getByText("Tree canopy (dense)"));
    expect(dispatch).toHaveBeenCalledWith({ type: "SET_MATERIAL", material: "tree_dense" });
  });

  it("shows the selected material's warning", () => {
    const state = { ...initialState("grass"), material: "light_paving" };
    render(<MaterialPalette materialsResp={materialsResp} state={state} dispatch={vi.fn()} />);
    expect(screen.getByText(/raises radiant heat/)).toBeInTheDocument();
  });

  it("hides the warning while the erase tool is active", () => {
    const state = { ...initialState("grass"), material: "light_paving", tool: "erase" as const };
    render(<MaterialPalette materialsResp={materialsResp} state={state} dispatch={vi.fn()} />);
    expect(screen.queryByText(/raises radiant heat/)).not.toBeInTheDocument();
  });
});
