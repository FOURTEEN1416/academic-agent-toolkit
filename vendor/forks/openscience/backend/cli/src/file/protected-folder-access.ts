import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"

export type ProtectedFolderAccess = {
  blocked: boolean
  reason?: "permission_denied"
}

function code(error: unknown) {
  if (!error || typeof error !== "object" || !("code" in error)) return
  return typeof error.code === "string" ? error.code : undefined
}

export function isProtectedFolderDenied(error: unknown) {
  const value = code(error)
  return value === "EACCES" || value === "EPERM"
}

export async function probeProtectedFolderAccess(
  input: {
    platform?: NodeJS.Platform
    home?: string
  } = {},
): Promise<ProtectedFolderAccess> {
  if ((input.platform ?? process.platform) !== "darwin") return { blocked: false }
  const desktop = path.join(input.home ?? os.homedir(), "Desktop")
  const result = await fs.readdir(desktop).catch((error: unknown) => error)
  if (Array.isArray(result)) return { blocked: false }
  if (isProtectedFolderDenied(result)) return { blocked: true, reason: "permission_denied" }
  return { blocked: false }
}
