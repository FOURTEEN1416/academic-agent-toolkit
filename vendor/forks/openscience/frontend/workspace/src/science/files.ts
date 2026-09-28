import type { ArtifactKind } from "./renderers/registry"

export interface ScientificFile {
  kind: ArtifactKind
  data: unknown
  format: string
}

const protein: Record<string, string> = {
  pdb: "pdb",
  ent: "pdb",
  cif: "mmcif",
  mmcif: "mmcif",
  pdbqt: "pdbqt",
  gro: "gro",
}

const molecule: Record<string, string> = {
  xyz: "xyz",
  sdf: "sdf",
  mol: "mol",
  mol2: "mol2",
}

const fasta = new Set(["fa", "fasta", "faa", "fna", "ffn", "frn"])

export function detectScientificFile(extension: string, content: string): ScientificFile | undefined {
  if (!content.trim()) return

  const ext = extension.toLowerCase()
  const proteinFormat = protein[ext]
  if (proteinFormat) {
    return {
      kind: "protein-structure",
      data: { data: content, format: proteinFormat },
      format: proteinFormat,
    }
  }

  const moleculeFormat = molecule[ext]
  if (moleculeFormat) {
    return {
      kind: "chem-3d",
      data: { data: content, format: moleculeFormat },
      format: moleculeFormat,
    }
  }

  if (ext === "smi" || ext === "smiles") {
    const records = content
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#"))
    const smiles = records[0]?.split(/\s+/)[0]
    if (!smiles) return
    return {
      kind: "chem-2d",
      data: { smiles, records: records.length },
      format: "smiles",
    }
  }

  if (!fasta.has(ext)) return
  const records = content.split(/\r?\n/).reduce<{ id: string; seq: string }[]>((all, line) => {
    const value = line.trim()
    if (!value) return all
    if (value.startsWith(">")) {
      all.push({ id: value.slice(1).trim() || `sequence_${all.length + 1}`, seq: "" })
      return all
    }
    const record = all[all.length - 1]
    if (record) {
      record.seq += value.replace(/\s+/g, "")
      return all
    }
    all.push({ id: "sequence_1", seq: value.replace(/\s+/g, "") })
    return all
  }, [])
  const sequences = records.filter((record) => record.seq)
  const first = sequences[0]
  if (!first) return
  const aligned = sequences.length > 1 && sequences.every((record) => record.seq.length === first.seq.length)
  if (aligned) {
    return {
      kind: "msa",
      data: { sequences },
      format: "fasta",
    }
  }
  return {
    kind: "sequence",
    data: {
      id: first.id,
      sequence: first.seq,
      records: sequences.length,
    },
    format: "fasta",
  }
}
