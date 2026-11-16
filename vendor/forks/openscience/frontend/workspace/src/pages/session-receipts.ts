import type { ComputeJobDetails } from "@synsci/ui/context/data"
import type { ProjectRequest } from "@/utils/openscience-fetch"

export function sessionReceipts(request: ProjectRequest) {
  const pending = new Map<string, Promise<string | undefined>>()
  const resolve = (sessionID: string, path: string) => {
    const key = JSON.stringify([sessionID, path])
    const prior = pending.get(key)
    if (prior) return prior
    const next = request("/file/resolve", { cache: "no-store" }, { sessionID, path })
      .then(async (response) => {
        if (!response.ok) throw new Error("File receipts could not be checked")
        const value: unknown = await response.json()
        return value && typeof value === "object" && "path" in value && typeof value.path === "string"
          ? value.path
          : undefined
      })
      .finally(() => pending.delete(key))
    pending.set(key, next)
    return next
  }
  return {
    async files(sessionID: string, paths: readonly string[]) {
      const found: string[] = []
      // Keep large historical turns from flooding the local server.
      for (let i = 0; i < paths.length; i += 8) {
        for (const path of await Promise.all(paths.slice(i, i + 8).map((path) => resolve(sessionID, path)))) {
          if (path) found.push(path)
        }
      }
      return found
    },
    async job(id: string): Promise<ComputeJobDetails | undefined> {
      const response = await request("/settings/compute/jobs", { cache: "no-store" })
      if (!response.ok) throw new Error("Current compute jobs could not be read")
      const jobs: ComputeJobDetails[] = await response.json()
      return jobs.find((job) => job.id === id)
    },
  }
}
