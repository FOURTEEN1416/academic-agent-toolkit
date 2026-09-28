import { createStore } from "solid-js/store"
import { workspaceScope } from "./scope"

export interface SessionTabStorage {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

interface ProjectTabs {
  active?: string
  tabs: string[]
  drafts: Record<string, boolean>
  seen: Record<string, number>
}

interface PersistedTabs {
  version: 1
  projects: Record<string, ProjectTabs>
}

const STORAGE_KEY = "openscience-session-tabs-v1"
const FALLBACK_PROJECT = workspaceScope("__workspace__", "sessions")

function empty(): ProjectTabs {
  return {
    tabs: [],
    drafts: {},
    seen: {},
  }
}

function record(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return
  return value as Record<string, unknown>
}

function restoreProject(value: unknown): ProjectTabs {
  const row = record(value)
  if (!row) return empty()
  const tabs = Array.isArray(row.tabs)
    ? row.tabs
        .filter((id): id is string => typeof id === "string" && !!id)
        .filter((id, index, all) => all.indexOf(id) === index)
    : []
  const stored = record(row.drafts)
  const drafts = Object.fromEntries(
    Object.entries(stored ?? {}).flatMap(([id, dirty]) => (tabs.includes(id) && dirty === true ? [[id, true]] : [])),
  )
  const saved = record(row.seen)
  const seen = Object.fromEntries(
    Object.entries(saved ?? {}).flatMap(([id, value]) =>
      tabs.includes(id) && typeof value === "number" && Number.isFinite(value) ? [[id, value]] : [],
    ),
  )
  return {
    active: typeof row.active === "string" && tabs.includes(row.active) ? row.active : tabs[0],
    tabs,
    drafts,
    seen,
  }
}

function restore(storage: SessionTabStorage | undefined) {
  if (!storage) return {}
  const raw = (() => {
    try {
      return storage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  })()
  if (!raw) return {}
  const parsed = (() => {
    try {
      return JSON.parse(raw) as unknown
    } catch {
      return
    }
  })()
  const root = record(parsed)
  const projects = record(root?.projects)
  if (root?.version !== 1 || !projects) return {}
  return Object.fromEntries(Object.entries(projects).map(([project, value]) => [project, restoreProject(value)]))
}

function browserStorage(): SessionTabStorage | undefined {
  if (typeof localStorage === "undefined") return
  return localStorage
}

export function createSessionTabs(options: { storage?: SessionTabStorage } = {}) {
  const storage = options.storage ?? browserStorage()
  const [store, setStore] = createStore({
    project: FALLBACK_PROJECT,
    projects: restore(storage) as Record<string, ProjectTabs>,
  })

  const current = () => store.projects[store.project] ?? empty()
  const persist = () => {
    if (!storage) return
    try {
      storage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          version: 1,
          projects: store.projects,
        } satisfies PersistedTabs),
      )
    } catch {}
  }
  const update = (next: ProjectTabs) => {
    setStore("projects", store.project, next)
    persist()
  }

  return {
    activateProject(project: string) {
      setStore("project", workspaceScope(project, "sessions"))
    },
    tabs: () => current().tabs,
    active: () => current().active,
    dirty: (id: string) => current().drafts[id] === true,
    unread(id: string, updated: number) {
      if (current().active === id) return false
      return updated > (current().seen[id] ?? 0)
    },
    open(id: string) {
      const tab = id.trim()
      if (!tab) return
      const state = current()
      const tabs = state.tabs.includes(tab) ? state.tabs : [...state.tabs, tab]
      update({ ...state, active: tab, tabs })
    },
    close(id: string) {
      const state = current()
      const index = state.tabs.indexOf(id)
      if (index === -1) return state.active
      const tabs = state.tabs.filter((tab) => tab !== id)
      const drafts = Object.fromEntries(Object.entries(state.drafts).filter(([tab]) => tab !== id))
      const seen = Object.fromEntries(Object.entries(state.seen).filter(([tab]) => tab !== id))
      const active = state.active === id ? (tabs[index - 1] ?? tabs[index] ?? tabs[0]) : state.active
      update({ active, tabs, drafts, seen })
      return active
    },
    move(id: string, to: number) {
      const state = current()
      const index = state.tabs.indexOf(id)
      if (index === -1) return
      const target = Math.max(0, Math.min(to, state.tabs.length - 1))
      if (target === index) return
      const tabs = [...state.tabs]
      tabs.splice(target, 0, tabs.splice(index, 1)[0])
      update({ ...state, tabs })
    },
    setDraft(id: string, dirty: boolean) {
      const state = current()
      if (!state.tabs.includes(id)) return
      if (dirty === (state.drafts[id] === true)) return
      const drafts = { ...state.drafts }
      if (dirty) drafts[id] = true
      if (!dirty) delete drafts[id]
      update({ ...state, drafts })
    },
    markRead(id: string, updated: number) {
      const state = current()
      if (!state.tabs.includes(id)) return
      if (!Number.isFinite(updated) || updated <= (state.seen[id] ?? 0)) return
      update({ ...state, seen: { ...state.seen, [id]: updated } })
    },
  }
}
