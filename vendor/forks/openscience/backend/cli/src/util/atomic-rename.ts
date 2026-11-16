import fs from "node:fs/promises"

export namespace AtomicRename {
  /** Windows sharing failures can outlive a reader's handle briefly. Retry the
   * atomic rename itself; never unlink the committed destination to make room. */
  export async function replace(
    source: string,
    destination: string,
    windows = process.platform === "win32",
  ): Promise<void> {
    const deadline = Date.now() + 2_000
    return attempt(10)

    async function attempt(delay: number): Promise<void> {
      return fs.rename(source, destination).catch(async (error: NodeJS.ErrnoException) => {
        if (!windows || !["EPERM", "EACCES", "EBUSY"].includes(error.code ?? "") || Date.now() >= deadline) {
          throw error
        }
        await Bun.sleep(Math.min(delay, Math.max(0, deadline - Date.now())))
        return attempt(Math.min(delay * 2, 100))
      })
    }
  }
}
