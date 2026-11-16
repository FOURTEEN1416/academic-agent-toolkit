import { describe, expect, test } from "bun:test"
import type { Message, Part, UserMessage } from "@synsci/sdk/v2"
import { noteLabel } from "./trace-rows"
import { isContinuationCarrier, turnOpener, wakeLabel } from "./session-turn-carrier"

const user = (id: string, internal?: UserMessage["internal"]): UserMessage => ({
  id,
  sessionID: "ses_c",
  role: "user",
  time: { created: 1 },
  agent: "research",
  model: { providerID: "test", modelID: "test" },
  internal,
})
const text = (messageID: string, value: string, synthetic?: boolean): Part => ({
  id: `prt_${messageID}`,
  sessionID: "ses_c",
  messageID,
  type: "text",
  text: value,
  synthetic,
})

describe("continuation carriers", () => {
  test("harness continuations, worker wake-ups and automatic compactions are carriers; typed requests, shell commands and manual compactions are not", () => {
    const typed = user("msg_typed", { type: "prompt", epoch: "msg_typed" })
    expect(isContinuationCarrier(typed, [text("msg_typed", "Fit the model.")])).toBe(false)
    const harness = user("msg_h", {
      type: "continuation",
      kind: "harness",
      text: "Diagnose the root cause.",
      epoch: "msg_typed",
      transaction: "msg_h",
    })
    expect(isContinuationCarrier(harness, [text("msg_h", "Diagnose the root cause.", true)])).toBe(true)
    const wake = user("msg_w", { type: "prompt", epoch: "msg_w" })
    expect(
      isContinuationCarrier(wake, [
        text("msg_w", '<task id="ses_child" state="completed">\n<task_result>done</task_result>\n</task>', true),
        text("msg_w", "", true),
      ]),
    ).toBe(true)
    const shell = user("msg_s")
    expect(isContinuationCarrier(shell, [text("msg_s", "The following tool was executed by the user", true)])).toBe(
      false,
    )
    // A compaction that fired by itself mid-turn is the runtime's bookkeeping:
    // the work after it is still the turn's. A /compact the user typed draws
    // its own boundary.
    const compaction = user("msg_k", { type: "compaction", auto: true, epoch: "msg_typed", transaction: "msg_k" })
    const marker: Part = { id: "prt_k", sessionID: "ses_c", messageID: "msg_k", type: "compaction", auto: true }
    expect(isContinuationCarrier(compaction, [marker])).toBe(true)
    const manual = user("msg_m", { type: "compaction", auto: false, epoch: "msg_m", transaction: "msg_m" })
    expect(isContinuationCarrier(manual, [{ ...marker, id: "prt_m", messageID: "msg_m", auto: false }])).toBe(false)
    expect(isContinuationCarrier(wake, [])).toBe(false)
    expect(isContinuationCarrier(wake, undefined)).toBe(false)
  })

  test("a compute job ending and a study update fold into the running turn and read as one line", () => {
    const opener = user("msg_1", { type: "prompt", epoch: "msg_1" })
    const job = user("msg_2", { type: "prompt", epoch: "msg_2" })
    const study = user("msg_3", { type: "prompt", epoch: "msg_3" })
    const legacy = user("msg_4", { type: "prompt", epoch: "msg_4" })
    const marked = (id: string, value: string, label: string): Part => ({
      id: `prt_${id}`,
      sessionID: "ses_c",
      messageID: id,
      type: "text",
      text: value,
      synthetic: true,
      metadata: { "openscience.wake": { source: "compute", label } },
    })
    const parts = (id: string): Part[] => {
      if (id === job.id)
        return [
          marked(id, "Compute job j1 (topo) ended with status succeeded. Read its logs.", "Compute job topo succeeded"),
        ]
      if (id === study.id)
        return [marked(id, 'Study update for "s":\n- 3 of 3 slots free.', "Study update: 3 of 3 slots free")]
      if (id === legacy.id)
        return [
          text(
            id,
            "Compute job 5c4a54d9-311 (cma_staged2) ended with status succeeded. Read its logs with compute_job logs.",
            true,
          ),
        ]
      return [text(id, "Optimise the valve.")]
    }
    const messages: Message[] = [opener, job, study, legacy]
    for (const index of [1, 2, 3]) expect(turnOpener(messages, index, parts)?.id).toBe("msg_1")
    expect(wakeLabel(parts(job.id)[0] as Extract<Part, { type: "text" }>)).toBe("Compute job topo succeeded")
    expect(wakeLabel(parts(legacy.id)[0] as Extract<Part, { type: "text" }>)).toBe("Compute job cma_staged2 succeeded")
    // The same words typed by a person are a request, not a report.
    const typed = user("msg_5", { type: "prompt", epoch: "msg_5" })
    expect(isContinuationCarrier(typed, [text("msg_5", "Compute job x (y) ended with status failed. Why?")])).toBe(
      false,
    )
  })

  test("a compaction carrier folds into the turn it interrupted, so the work after it is not orphaned", () => {
    const opener = user("msg_1", { type: "prompt", epoch: "msg_1" })
    const compaction = user("msg_5", { type: "compaction", auto: true, epoch: "msg_1", transaction: "msg_5" })
    const continuation = user("msg_7", {
      type: "continuation",
      kind: "compaction",
      text: "Continue the user's newest request",
      epoch: "msg_1",
      transaction: "msg_7",
    })
    const messages: Message[] = [opener, compaction, continuation]
    const parts = (id: string): Part[] => {
      if (id === compaction.id)
        return [{ id: "prt_5", sessionID: "ses_c", messageID: id, type: "compaction", auto: true }]
      if (id === continuation.id) return [text(id, "Continue the user's newest request", true)]
      return [text(id, "Train the model.")]
    }
    expect(turnOpener(messages, 1, parts)?.id).toBe("msg_1")
    expect(turnOpener(messages, 2, parts)?.id).toBe("msg_1")
  })

  test("a carrier belongs to the nearest earlier turn the user opened", () => {
    const opener = user("msg_1", { type: "prompt", epoch: "msg_1" })
    const wake = user("msg_3", { type: "prompt", epoch: "msg_3" })
    const messages: Message[] = [opener, wake]
    const parts = (id: string) =>
      id === wake.id ? [text(wake.id, '<task id="ses_x" state="completed"></task>', true)] : [text(id, "Go.")]
    expect(turnOpener(messages, 1, parts)?.id).toBe("msg_1")
    expect(turnOpener(messages, 0, parts)?.id).toBe("msg_1")
    expect(turnOpener([wake], 0, parts)).toBeUndefined()
  })
})

test("a harness note reads as one line: the worker's state, or the first sentence of a check", () => {
  expect(
    noteLabel(
      '<task id="ses_w" state="completed">\n<summary>The comparison is ready; one source could not be retrieved. Details follow.</summary>\n<task_result>...</task_result>\n</task>',
    ),
  ).toBe("Worker completed: The comparison is ready; one source could not be retrieved.")
  expect(noteLabel('<task id="ses_w" state="error"><summary></summary></task>')).toBe("Worker error")
  expect(
    noteLabel(
      "Before finishing, the deliverables checklist was checked mechanically. These named outputs are not ready:\n- results/x.csv: does not exist",
    ),
  ).toBe("Before finishing, the deliverables checklist was checked mechanically.")
  expect(
    noteLabel(
      '<system-reminder kind="status">\nTime reminder: 31m of the 1h time budget is used (half). Prioritize the remaining deliverables.\n</system-reminder>',
    ),
  ).toBe("Time reminder: 31m of the 1h time budget is used (half).")
})
