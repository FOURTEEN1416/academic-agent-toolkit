import fs from "fs/promises"
import path from "path"
import crypto from "crypto"

export namespace SecretFile {
  const WAIT = 5_000

  export async function key(filepath: string, size = 32, start = Date.now()): Promise<Buffer> {
    await fs.mkdir(path.dirname(filepath), { recursive: true })
    const handle = await fs.open(filepath, "wx", 0o600).catch((error: NodeJS.ErrnoException) => {
      if (error.code === "EEXIST") return undefined
      throw error
    })

    if (handle) {
      const value = crypto.randomBytes(size)
      await handle.writeFile(value).catch(async (error) => {
        await handle.close().catch(() => undefined)
        await fs.unlink(filepath).catch(() => undefined)
        throw error
      })
      await handle.sync().catch(async (error) => {
        await handle.close().catch(() => undefined)
        await fs.unlink(filepath).catch(() => undefined)
        throw error
      })
      await handle.close()
      await fs.chmod(filepath, 0o600)
      return value
    }

    const value = await Bun.file(filepath)
      .arrayBuffer()
      .then((data) => Buffer.from(data))
      .catch(() => undefined)
    if (value?.byteLength === size) {
      await fs.chmod(filepath, 0o600)
      return value
    }
    const stat = await fs.stat(filepath).catch(() => undefined)
    if (stat && Date.now() - stat.mtimeMs < WAIT && Date.now() - start < WAIT) {
      await Bun.sleep(15)
      return key(filepath, size, start)
    }
    throw new Error(`${filepath} is not a valid ${size}-byte OpenScience secret key; refusing to replace it`)
  }
}
