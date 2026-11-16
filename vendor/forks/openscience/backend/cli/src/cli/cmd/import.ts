import type { Argv } from "yargs"
import { Session } from "../../session"
import { cmd } from "./cmd"
import { bootstrap } from "../bootstrap"
import { Storage } from "../../storage/storage"
import { Instance } from "../../project/instance"
import { EOL } from "os"

export type SessionExport = {
  info: Session.Info
  messages: Array<{
    info: any
    parts: any[]
  }>
}

/** Read an exported session file, saying which of the two failures it was.
 * A single `json().catch(() => {})` reported a malformed file as missing, and
 * the second copy of the same check below was unreachable. */
export async function readExport(
  file: string,
): Promise<{ ok: true; data: SessionExport } | { ok: false; message: string }> {
  if (!(await Bun.file(file).exists())) return { ok: false, message: `File not found: ${file}` }
  let data: unknown
  try {
    data = await Bun.file(file).json()
  } catch (error) {
    return {
      ok: false,
      message: `Failed to read session data from ${file}: ${error instanceof Error ? error.message : String(error)}`,
    }
  }
  if (typeof data !== "object" || data === null || !("info" in data) || !("messages" in data)) {
    return { ok: false, message: `Failed to read session data from ${file}: expected an object with info and messages` }
  }
  return { ok: true, data: data as SessionExport }
}

export const ImportCommand = cmd({
  command: "import <file>",
  describe: "import session data from JSON file",
  builder: (yargs: Argv) => {
    return yargs.positional("file", {
      describe: "path to JSON file",
      type: "string",
      demandOption: true,
    })
  },
  handler: async (args) => {
    await bootstrap(process.cwd(), async () => {
      const read = await readExport(args.file)
      if (!read.ok) {
        // A failure here is the whole result of the command, so it must not
        // exit 0 and read as a success in a script.
        process.stderr.write(read.message)
        process.stderr.write(EOL)
        process.exitCode = 1
        return
      }
      const exportData = read.data

      await Storage.write(["session", Instance.project.id, exportData.info.id], exportData.info)

      for (const msg of exportData.messages) {
        await Storage.write(["message", exportData.info.id, msg.info.id], msg.info)

        for (const part of msg.parts) {
          await Storage.write(["part", msg.info.id, part.id], part)
        }
      }

      process.stdout.write(`Imported session: ${exportData.info.id}`)
      process.stdout.write(EOL)
    })
  },
})
