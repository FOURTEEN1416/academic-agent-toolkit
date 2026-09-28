export type SemaphoreRelease = () => void

type Waiter = {
  resolve: (release: SemaphoreRelease) => void
  reject: (reason?: unknown) => void
  signal?: AbortSignal
  onAbort?: () => void
}

/** A FIFO counting semaphore with abort-aware, idempotent permits. */
export class Semaphore {
  private available: number
  private readonly max: number
  private readonly waiters: Waiter[] = []

  constructor(max: number) {
    this.max = Math.max(1, Math.floor(Number.isFinite(max) ? max : 1))
    this.available = this.max
  }

  async acquire(signal?: AbortSignal): Promise<SemaphoreRelease> {
    if (signal?.aborted) throw signal.reason ?? new Error("aborted while waiting for a slot")
    if (this.available > 0) {
      this.available--
      return this.permit()
    }

    return new Promise<SemaphoreRelease>((resolve, reject) => {
      const waiter: Waiter = { resolve, reject, signal }
      waiter.onAbort = () => {
        const index = this.waiters.indexOf(waiter)
        if (index >= 0) this.waiters.splice(index, 1)
        reject(signal?.reason ?? new Error("aborted while waiting for a slot"))
      }
      this.waiters.push(waiter)
      signal?.addEventListener("abort", waiter.onAbort, { once: true })
    })
  }

  private permit(): SemaphoreRelease {
    let released = false
    return () => {
      if (released) return
      released = true

      const next = this.waiters.shift()
      if (next) {
        if (next.signal && next.onAbort) next.signal.removeEventListener("abort", next.onAbort)
        next.resolve(this.permit())
        return
      }
      this.available = Math.min(this.max, this.available + 1)
    }
  }
}

type FrameState = "active" | "suspended" | "pending" | "closed"

type Frame = {
  key: string
  parent?: Frame
  lease: Lease
  state: FrameState
}

type PendingFrame = {
  frame: Frame
  resolve: (release: SemaphoreRelease) => void
  reject: (reason?: unknown) => void
  signal?: AbortSignal
  onAbort?: () => void
}

type Lease = {
  active?: Frame
  pending: PendingFrame[]
  release: SemaphoreRelease
}

/**
 * A semaphore for nested session work.
 *
 * A child can take over its suspended parent's permit, but only one descendant
 * on that permit is active at a time. Parallel nested children queue on the same
 * lease instead of bypassing the global cap or deadlocking behind their parent.
 */
export class HierarchicalSemaphore {
  private readonly pool: Semaphore
  private readonly frames = new Map<string, Frame>()
  private readonly reserved = new Set<string>()

  constructor(max: number) {
    this.pool = new Semaphore(max)
  }

  async acquire(key: string, options?: { parent?: string; signal?: AbortSignal }): Promise<SemaphoreRelease> {
    if (this.frames.has(key) || this.reserved.has(key)) {
      throw new Error(`semaphore key is already active: ${key}`)
    }
    if (options?.signal?.aborted) {
      throw options.signal.reason ?? new Error("aborted while waiting for a slot")
    }

    const parent = options?.parent ? this.frames.get(options.parent) : undefined
    if (parent && parent.state !== "closed") return this.acquireNested(key, parent, options?.signal)

    this.reserved.add(key)
    try {
      const release = await this.pool.acquire(options?.signal)
      const lease: Lease = { pending: [], release }
      const frame: Frame = { key, lease, state: "active" }
      lease.active = frame
      this.frames.set(key, frame)
      return this.closer(frame)
    } finally {
      this.reserved.delete(key)
    }
  }

  private acquireNested(key: string, parent: Frame, signal?: AbortSignal): Promise<SemaphoreRelease> {
    const lease = parent.lease
    const frame: Frame = { key, parent, lease, state: "pending" }
    this.frames.set(key, frame)

    if (lease.active === parent && parent.state === "active") {
      parent.state = "suspended"
      frame.state = "active"
      lease.active = frame
      return Promise.resolve(this.closer(frame))
    }

    return new Promise<SemaphoreRelease>((resolve, reject) => {
      const pending: PendingFrame = { frame, resolve, reject, signal }
      pending.onAbort = () => {
        const index = lease.pending.indexOf(pending)
        if (index >= 0) lease.pending.splice(index, 1)
        frame.state = "closed"
        this.frames.delete(key)
        reject(signal?.reason ?? new Error("aborted while waiting for a nested slot"))
      }
      lease.pending.push(pending)
      signal?.addEventListener("abort", pending.onAbort, { once: true })
    })
  }

  private closer(frame: Frame): SemaphoreRelease {
    let closed = false
    return () => {
      if (closed) return
      closed = true
      this.close(frame)
    }
  }

  private close(frame: Frame): void {
    if (frame.state === "closed") return
    const wasActive = frame.lease.active === frame
    frame.state = "closed"
    if (this.frames.get(frame.key) === frame) this.frames.delete(frame.key)

    this.rejectOrphaned(frame.lease)
    if (!wasActive) return

    let ancestor = frame.parent
    while (ancestor?.state === "closed") ancestor = ancestor.parent

    // A descendant temporarily owns its ancestor's permit while that ancestor
    // awaits the nested task. When the descendant closes, only another direct
    // child of the nearest suspended ancestor may take over. An unrelated
    // sibling queued under a higher ancestor must wait until the current branch
    // has actually unwound, otherwise both it and the resumed parent run on the
    // same permit.
    const nextIndex = ancestor ? frame.lease.pending.findIndex((pending) => pending.frame.parent === ancestor) : 0
    const next = nextIndex >= 0 ? frame.lease.pending.splice(nextIndex, 1)[0] : undefined
    if (next) {
      if (next.signal && next.onAbort) next.signal.removeEventListener("abort", next.onAbort)
      next.frame.state = "active"
      frame.lease.active = next.frame
      next.resolve(this.closer(next.frame))
      return
    }

    if (ancestor) {
      ancestor.state = "active"
      frame.lease.active = ancestor
      return
    }

    frame.lease.active = undefined
    frame.lease.release()
  }

  private rejectOrphaned(lease: Lease): void {
    for (let index = lease.pending.length - 1; index >= 0; index--) {
      const pending = lease.pending[index]
      let ancestor: Frame | undefined = pending.frame.parent
      let orphaned = false
      while (ancestor) {
        if (ancestor.state === "closed") {
          orphaned = true
          break
        }
        ancestor = ancestor.parent
      }
      if (!orphaned) continue

      lease.pending.splice(index, 1)
      if (pending.signal && pending.onAbort) pending.signal.removeEventListener("abort", pending.onAbort)
      pending.frame.state = "closed"
      this.frames.delete(pending.frame.key)
      pending.reject(new Error("parent session ended while waiting for a nested slot"))
    }
  }
}
