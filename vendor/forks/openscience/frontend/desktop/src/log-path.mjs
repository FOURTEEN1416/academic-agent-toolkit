import { existsSync, renameSync } from "node:fs"
import path from "node:path"

/** How many earlier runs' logs stay beside the current one. */
export const KEPT_RUNS = 5

/**
 * Move earlier runs' logs aside before a new run writes `output`: the run before this one becomes
 * `<name>.prev.log`, older ones `<name>.prev.2.log` and on to `KEPT_RUNS`, and the oldest is dropped. One kept
 * run was not enough: an update relaunch rotated away the log of a failure a few hours old.
 *
 * @param {string} output
 * @param {number} [kept]
 */
export function rotateLogs(output, kept = KEPT_RUNS) {
  const base = output.replace(/\.log$/, "")
  const name = (index) => (index === 1 ? `${base}.prev.log` : `${base}.prev.${index}.log`)
  for (let index = kept; index >= 1; index--) {
    const source = index === 1 ? output : name(index - 1)
    if (!existsSync(source)) continue
    try {
      renameSync(source, name(index))
    } catch {
      /* rotation is best effort; a fresh log still starts */
    }
  }
}

/**
 * The directory the shell's logs belong in, or undefined to keep Electron's default.
 *
 * On macOS that default is `~/Library/Logs/<app name>`: it follows the app's name, not its `userData`. A shell
 * run from source, or any launch given `--user-data-dir`, carries the installed app's name, so it would rotate
 * and overwrite the log a person attaches to a bug report. Such a launch keeps its logs with the rest of its
 * data; an installed app started normally keeps the platform's location.
 *
 * @param {{ packaged: boolean, relocated: boolean, userData: string }} shell
 * @returns {string | undefined}
 */
export function logsDirectory(shell) {
  if (shell.packaged && !shell.relocated) return
  return path.join(shell.userData, "logs")
}
