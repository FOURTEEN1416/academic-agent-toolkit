export type BinaryScienceFormat = "bam" | "cram" | "h5ad" | "loom"

export interface BinaryInspection {
  format: BinaryScienceFormat
  name: string
  size: number
  modified: number
  signature: boolean
  index?: string
  tool: {
    name: string
    available: boolean
    detail?: string
  }
  details: Record<string, unknown>
}

export interface EmbeddingPoint {
  x: number
  y: number
  label?: string
}

export interface Embedding {
  name: string
  label?: string
  total: number
  points: EmbeddingPoint[]
}

const formats = new Set<BinaryScienceFormat>(["bam", "cram", "h5ad", "loom"])

export function detectBinaryScienceFormat(extension: string): BinaryScienceFormat | undefined {
  const value = extension.toLowerCase() as BinaryScienceFormat
  return formats.has(value) ? value : undefined
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ["KB", "MB", "GB", "TB"]
  const order = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)) - 1)
  const value = bytes / 1024 ** (order + 1)
  return `${Math.round(value * 10) / 10} ${units[order]}`
}

export function normalizeInspection(value: unknown): BinaryInspection {
  const data = object(value)
  const tool = object(data.tool)
  const candidate = typeof data.format === "string" ? detectBinaryScienceFormat(data.format) : undefined
  return {
    format: candidate ?? "bam",
    name: typeof data.name === "string" ? data.name : "",
    size: typeof data.size === "number" ? data.size : 0,
    modified: typeof data.modified === "number" ? data.modified : 0,
    signature: data.signature === true,
    index: typeof data.index === "string" ? data.index : undefined,
    tool: {
      name: typeof tool.name === "string" ? tool.name : "local inspector",
      available: tool.available === true,
      detail: typeof tool.detail === "string" ? tool.detail : undefined,
    },
    details: object(data.details),
  }
}

export function objects(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
}

export function strings(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string")
}

export function numbers(value: unknown): number[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is number => typeof item === "number")
}

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {}
  return value as Record<string, unknown>
}

export function embedding(value: unknown): Embedding | undefined {
  const data = object(value)
  const points = objects(data.points)
    .map((point) => ({
      x: typeof point.x === "number" ? point.x : Number.NaN,
      y: typeof point.y === "number" ? point.y : Number.NaN,
      label: typeof point.label === "string" ? point.label : undefined,
    }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y))
  if (!points.length) return
  return {
    name: typeof data.name === "string" ? data.name : "embedding",
    label: typeof data.label === "string" ? data.label : undefined,
    total: typeof data.total === "number" ? data.total : points.length,
    points,
  }
}
