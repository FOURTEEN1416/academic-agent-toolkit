/**
 * A restart the person asked for while turns were running. The running turns
 * are aborted with this reason; the processor leaves each turn unfinished (no
 * error, no completion time), which is the shape of a turn the process died
 * under, so the next process continues it through resumeInterrupted. The
 * pending tool calls are closed with the reason, so the transcript says why
 * they stopped rather than showing a generic abort.
 */
export namespace SessionRestart {
  export class Interruption extends Error {
    constructor() {
      super("Paused to install an update; OpenScience continues this turn after the restart.")
      this.name = "RestartInterruption"
    }
  }

  export function interruption(value: unknown): Interruption | undefined {
    return value instanceof Interruption ? value : undefined
  }
}
