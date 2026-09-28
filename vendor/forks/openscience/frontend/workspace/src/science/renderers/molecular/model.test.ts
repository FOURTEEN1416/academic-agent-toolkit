import { describe, expect, test } from "bun:test"
import path from "node:path"
import { analyzeMolecularSource, narrowMolecularSource } from "./model"

const fixtures = path.join(import.meta.dir, "../../../../e2e/science")

describe("molecular source analysis", () => {
  test("parses XYZ atom and element counts from the real viewer fixture", async () => {
    const text = await Bun.file(path.join(fixtures, "water.xyz")).text()
    expect(analyzeMolecularSource({ data: text, format: "xyz" }, "chem-3d")).toEqual({
      format: "xyz",
      source: "inline",
      atomCount: 3,
      moleculeCount: 1,
      elements: [
        { element: "H", count: 2 },
        { element: "O", count: 1 },
      ],
      warnings: [],
    })
  })

  test("parses PDB chains, residues, atoms, models, and elements", async () => {
    const text = await Bun.file(path.join(fixtures, "example.pdb")).text()
    expect(analyzeMolecularSource({ pdb: text }, "protein-structure")).toEqual({
      format: "pdb",
      source: "inline",
      atomCount: 4,
      chainCount: 1,
      residueCount: 1,
      modelCount: 1,
      elements: [
        { element: "C", count: 2 },
        { element: "N", count: 1 },
        { element: "O", count: 1 },
      ],
      warnings: [],
    })
  })

  test("parses SDF molecule, atom, bond, and element counts", async () => {
    const text = await Bun.file(path.join(fixtures, "ligand.sdf")).text()
    expect(analyzeMolecularSource({ sdf: text }, "chem-3d")).toEqual({
      format: "sdf",
      source: "inline",
      atomCount: 2,
      bondCount: 1,
      moleculeCount: 1,
      elements: [{ element: "C", count: 2 }],
      warnings: [],
    })
  })

  test("reports declared XYZ count mismatches and malformed coordinate rows", () => {
    expect(analyzeMolecularSource({ xyz: "3\nbad\nO 0 0 0\nH nope 0 1" }, "chem-3d")).toEqual({
      format: "xyz",
      source: "inline",
      atomCount: 1,
      moleculeCount: 1,
      elements: [{ element: "O", count: 1 }],
      warnings: ["XYZ declares 3 atoms but 1 valid coordinate row was parsed."],
    })
  })

  test("keeps remote source metadata honest without pretending it fetched scientific properties", () => {
    expect(analyzeMolecularSource({ url: "https://example.test/model.cif" }, "protein-structure")).toEqual({
      format: "mmcif",
      source: "remote",
      elements: [],
      warnings: ["Scientific properties are available after the remote structure is loaded."],
    })
  })

  test("normalizes supported source shapes for the Molstar renderer", () => {
    expect(narrowMolecularSource("1CBS", "protein-structure")).toEqual({
      url: "https://files.rcsb.org/download/1CBS.cif",
      format: "mmcif",
    })
    expect(narrowMolecularSource({ data: "3\nwater", format: "xyz" }, "chem-3d")).toEqual({
      raw: "3\nwater",
      format: "xyz",
    })
  })
})
