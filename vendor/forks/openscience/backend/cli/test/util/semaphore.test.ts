import { expect, test } from "bun:test"
import { HierarchicalSemaphore, Semaphore } from "../../src/util/semaphore"

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

test("semaphore bounds concurrency and returns idempotent permits", async () => {
  const semaphore = new Semaphore(2)
  let running = 0
  let peak = 0

  await Promise.all(
    Array.from({ length: 6 }, async () => {
      const release = await semaphore.acquire()
      running++
      peak = Math.max(peak, running)
      await sleep(5)
      running--
      release()
      release()
    }),
  )

  expect(peak).toBe(2)
  const first = await semaphore.acquire()
  const second = await semaphore.acquire()
  first()
  second()
})

test("semaphore wakes live waiters in FIFO order", async () => {
  const semaphore = new Semaphore(1)
  const releaseRoot = await semaphore.acquire()
  const order: number[] = []

  const first = semaphore.acquire().then((release) => {
    order.push(1)
    release()
  })
  const second = semaphore.acquire().then((release) => {
    order.push(2)
    release()
  })

  releaseRoot()
  await Promise.all([first, second])
  expect(order).toEqual([1, 2])
})

test("aborting a queued waiter removes it without leaking a permit", async () => {
  const semaphore = new Semaphore(1)
  const releaseRoot = await semaphore.acquire()
  const controller = new AbortController()
  const queued = semaphore.acquire(controller.signal)

  controller.abort(new Error("cancelled"))
  await expect(queued).rejects.toThrow("cancelled")
  releaseRoot()

  const release = await semaphore.acquire()
  release()
})

test("nested compute sessions transfer one permit and serialize parallel siblings", async () => {
  const semaphore = new HierarchicalSemaphore(1)
  const releaseRoot = await semaphore.acquire("root")
  const releaseFirstChild = await semaphore.acquire("child-1", { parent: "root" })

  let secondChildStarted = false
  const secondChild = semaphore.acquire("child-2", { parent: "root" }).then((release) => {
    secondChildStarted = true
    return release
  })
  let outsiderStarted = false
  const outsider = semaphore.acquire("other-root").then((release) => {
    outsiderStarted = true
    return release
  })

  await sleep(1)
  expect(secondChildStarted).toBe(false)
  expect(outsiderStarted).toBe(false)

  releaseFirstChild()
  const releaseSecondChild = await secondChild
  expect(secondChildStarted).toBe(true)
  expect(outsiderStarted).toBe(false)

  releaseSecondChild()
  await sleep(1)
  expect(outsiderStarted).toBe(false)

  releaseRoot()
  const releaseOutsider = await outsider
  expect(outsiderStarted).toBe(true)
  releaseOutsider()
})

test("a grandchild restores its parent before an unrelated queued sibling", async () => {
  const semaphore = new HierarchicalSemaphore(1)
  const releaseRoot = await semaphore.acquire("root")
  const releaseChild = await semaphore.acquire("child", { parent: "root" })

  let siblingStarted = false
  const sibling = semaphore.acquire("sibling", { parent: "root" }).then((release) => {
    siblingStarted = true
    return release
  })
  const releaseGrandchild = await semaphore.acquire("grandchild", { parent: "child" })

  releaseGrandchild()
  await sleep(1)
  expect(siblingStarted).toBe(false)

  releaseChild()
  const releaseSibling = await sibling
  expect(siblingStarted).toBe(true)
  releaseSibling()
  releaseRoot()
})

test("aborting a queued nested sibling leaves the inherited permit usable", async () => {
  const semaphore = new HierarchicalSemaphore(1)
  const releaseRoot = await semaphore.acquire("root")
  const releaseChild = await semaphore.acquire("child", { parent: "root" })
  const controller = new AbortController()
  const queuedSibling = semaphore.acquire("cancelled-child", {
    parent: "root",
    signal: controller.signal,
  })

  controller.abort(new Error("nested cancelled"))
  await expect(queuedSibling).rejects.toThrow("nested cancelled")
  releaseChild()
  releaseRoot()

  const releaseNext = await semaphore.acquire("next-root")
  releaseNext()
})

test("closing a parent while its child is active releases after the child", async () => {
  const semaphore = new HierarchicalSemaphore(1)
  const releaseRoot = await semaphore.acquire("root")
  const releaseChild = await semaphore.acquire("child", { parent: "root" })
  releaseRoot()

  let nextStarted = false
  const next = semaphore.acquire("next").then((release) => {
    nextStarted = true
    return release
  })
  await sleep(1)
  expect(nextStarted).toBe(false)

  releaseChild()
  const releaseNext = await next
  expect(nextStarted).toBe(true)
  releaseNext()
})

test("semaphore floors its capacity at one", async () => {
  const semaphore = new Semaphore(0)
  const release = await semaphore.acquire()
  release()
})

test("semaphore rejects an already-aborted acquisition without consuming a permit", async () => {
  const semaphore = new Semaphore(1)
  const controller = new AbortController()
  controller.abort(new Error("already cancelled"))
  await expect(semaphore.acquire(controller.signal)).rejects.toThrow("already cancelled")
  const release = await semaphore.acquire()
  release()
})
