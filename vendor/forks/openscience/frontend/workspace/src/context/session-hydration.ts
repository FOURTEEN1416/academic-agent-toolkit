export const SESSION_MESSAGE_CHUNK = 400

export type SessionHydrationInput = {
  hasSession: boolean
  hasMessages: boolean
  hydratedLimit?: number
  messageCount: number
  refresh?: boolean
}

export type SessionHydrationPlan = {
  skip: boolean
  loadMessages: boolean
  limit: number
}

export type HydrationMergeOptions = {
  /** Keep cached entities that are outside a partial server window. */
  preserveCached?: boolean
  /** Cached entities changed after the server snapshot request began. */
  preferCached?: ReadonlySet<string>
  /** Entities removed after the server snapshot request began. */
  removed?: ReadonlySet<string>
}

export function mergeHydratedMessages<T extends { id: string }>(
  cached: readonly T[],
  incoming: readonly T[],
  options: HydrationMergeOptions = {},
) {
  const merged = new Map((options.preserveCached ?? true) ? cached.map((message) => [message.id, message]) : [])
  for (const message of incoming) merged.set(message.id, message)
  if (options.preferCached?.size) {
    const live = new Map(cached.map((message) => [message.id, message]))
    for (const id of options.preferCached) {
      const message = live.get(id)
      if (message) merged.set(id, message)
    }
  }
  for (const id of options.removed ?? []) merged.delete(id)
  return [...merged.values()].sort((a, b) => a.id.localeCompare(b.id))
}

/** Leave enough room for a full missed-event chunk, not just a handful of turns. */
export function reconnectHydrationLimit(messageCount: number) {
  return Math.max(SESSION_MESSAGE_CHUNK, messageCount + SESSION_MESSAGE_CHUNK)
}

/**
 * The messages endpoint returns the newest N entries. If that window is full
 * and has not reached any previously hydrated message, expand until it does so
 * there can be no unobserved gap between cached and fetched history.
 */
export function nextReconnectHydrationLimit(input: { limit: number; snapshotCount: number; overlapsCached: boolean }) {
  if (input.snapshotCount < input.limit || input.overlapsCached) return undefined
  return input.limit + Math.max(input.limit, SESSION_MESSAGE_CHUNK)
}

/** Only the newest reconnect request for one session may update its transcript. */
export function createReconnectGenerationGuard() {
  const active = new Map<string, number>()
  let sequence = 0
  return {
    begin(key: string) {
      const generation = ++sequence
      active.set(key, generation)
      return generation
    },
    isCurrent(key: string, generation: number) {
      return active.get(key) === generation
    },
    invalidate(key: string) {
      active.delete(key)
    },
  }
}

function initialLimit(count: number) {
  if (count <= SESSION_MESSAGE_CHUNK) return SESSION_MESSAGE_CHUNK
  return Math.ceil(count / SESSION_MESSAGE_CHUNK) * SESSION_MESSAGE_CHUNK
}

/**
 * Plan a session transcript load without coupling route lifecycle to the SDK.
 *
 * Normal callers keep the existing cache fast path. An active route revisit
 * opts into refresh, which requests the cached history plus one chunk of
 * headroom. The caller merges that snapshot with the hydrated transcript so
 * even an unusually long inactive turn cannot truncate older history.
 */
export function sessionHydrationPlan(input: SessionHydrationInput): SessionHydrationPlan {
  const hydrated = input.hydratedLimit !== undefined
  const refresh = input.refresh === true
  const limit = refresh
    ? Math.max(input.hydratedLimit ?? 0, input.messageCount + SESSION_MESSAGE_CHUNK, SESSION_MESSAGE_CHUNK)
    : hydrated
      ? (input.hydratedLimit ?? SESSION_MESSAGE_CHUNK)
      : initialLimit(input.messageCount)

  return {
    skip: input.hasSession && input.hasMessages && hydrated && !refresh,
    loadMessages: !input.hasMessages || !hydrated || refresh,
    limit,
  }
}
