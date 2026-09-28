import { createSignal, createEffect } from "solid-js"

/**
 * Per-user preferences for project rows on the home page:
 *  - favorites: sticky-on-top, marked with a filled star.
 *  - hidden:    filtered out of the recent list.
 *
 * New entries are keyed by the opaque openscience project ID. Legacy
 * worktree-keyed entries remain readable during project-list migration and
 * persisted to localStorage so they survive reloads. We do NOT delete
 * the project from openscience itself — openscience tracks workspaces globally,
 * and the user might want to "unhide" later.
 */

const FAV_KEY = "thesis-project-favorites-v1"
const HIDE_KEY = "thesis-project-hidden-v1"

function readSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? new Set(arr) : new Set()
  } catch {
    return new Set()
  }
}

function writeSet(key: string, set: Set<string>) {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)))
  } catch {}
}

const [favorites, setFavoritesSig] = createSignal<Set<string>>(readSet(FAV_KEY))
const [hidden, setHiddenSig] = createSignal<Set<string>>(readSet(HIDE_KEY))

createEffect(() => writeSet(FAV_KEY, favorites()))
createEffect(() => writeSet(HIDE_KEY, hidden()))

const paths = (values: string[]) => [...new Set(values.filter(Boolean))]

const toggleFavorite = (...values: string[]) => {
  const keys = paths(values)
  setFavoritesSig((prev) => {
    const next = new Set(prev)
    const pinned = keys.some((path) => next.has(path))
    for (const path of keys) {
      if (pinned) next.delete(path)
      else next.add(path)
    }
    return next
  })
  setHiddenSig((prev) => {
    if (!keys.some((path) => prev.has(path))) return prev
    const next = new Set(prev)
    for (const path of keys) next.delete(path)
    return next
  })
}

const hide = (...values: string[]) => {
  const keys = paths(values)
  setHiddenSig((prev) => {
    const next = new Set(prev)
    for (const path of keys) next.add(path)
    return next
  })
  setFavoritesSig((prev) => {
    if (!keys.some((path) => prev.has(path))) return prev
    const next = new Set(prev)
    for (const path of keys) next.delete(path)
    return next
  })
}

const unhide = (...values: string[]) => {
  const keys = paths(values)
  setHiddenSig((prev) => {
    if (!keys.some((path) => prev.has(path))) return prev
    const next = new Set(prev)
    for (const path of keys) next.delete(path)
    return next
  })
}

const isFavorite = (...values: string[]) => values.some((path) => favorites().has(path))
const isHidden = (...values: string[]) => values.some((path) => hidden().has(path))

export const projectPrefs = {
  favorites,
  hidden,
  toggleFavorite,
  hide,
  unhide,
  isFavorite,
  isHidden,
}
