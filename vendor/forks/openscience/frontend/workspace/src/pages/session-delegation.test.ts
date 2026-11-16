import { expect, test } from "bun:test"
import type { Message, Part } from "@synsci/sdk/v2"
import { delegatedAssignment } from "./session-delegation"

test("a reused worker header follows its latest invocation without changing its historical title", () => {
  const child = { id: "child", parentID: "parent", title: "Old study (@explore subagent)" }
  const message = { id: "message", sessionID: "parent", role: "assistant" } as Message
  const task = (id: string, phase: string, description: string, childID = "child"): Part => ({
    id,
    sessionID: "parent",
    messageID: "message",
    type: "tool",
    tool: "task",
    callID: id,
    state: {
      status: "running",
      input: { subagent_type: phase, description },
      metadata: { sessionId: childID },
      time: { start: 1 },
    },
  })
  const parts = {
    message: [
      task("part_1", "explore", "Old study"),
      task("part_3", "execute", "Other worker", "other"),
      task("part_2", "execute", "Implement graders"),
    ],
  }
  expect(delegatedAssignment(child, [message], parts)).toEqual({ phase: "execute", description: "Implement graders" })
  expect(child.title).toBe("Old study (@explore subagent)")
  expect(delegatedAssignment(child, [], parts)).toBeUndefined()
  expect(delegatedAssignment({ id: "root" }, [message], parts)).toBeUndefined()
})
