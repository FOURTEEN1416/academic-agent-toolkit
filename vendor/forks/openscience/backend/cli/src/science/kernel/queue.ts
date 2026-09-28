export class KernelQueue {
  private tail: Promise<void> = Promise.resolve()
  private size = 0

  get depth() {
    return this.size
  }

  run<T>(task: () => Promise<T>, signal?: AbortSignal): Promise<T> {
    this.size += 1
    const result = this.tail.then(() => {
      if (signal?.aborted) throw new Error("Execution aborted before starting")
      return task()
    })
    this.tail = result.then(
      () => undefined,
      () => undefined,
    )
    return result.finally(() => {
      this.size -= 1
    })
  }
}
