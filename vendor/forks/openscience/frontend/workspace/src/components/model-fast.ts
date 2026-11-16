export type FastCapableRoute = {
  id?: string
  modes?: Record<string, unknown>
  provider?: { id: string; name?: string }
}

/** What the Speed section shows for the selected route. */
export type FastMode = {
  active: boolean
  /** The route offers a Fast tier the toggle can switch to. */
  offered: boolean
  /** One line under the toggle: a subscription route, or a route without the
   * tier while another route of the same model has it. */
  note?: string
}

/** The model id without a route's own prefix, so `openai/gpt-5.6-sol` on
 * Ace and `gpt-5.6-sol` on a key or the Codex subscription read as one model. */
export function routeModelBase(id: string) {
  return id.replace(/^[^/]+\//, "").toLowerCase()
}

const offersFast = (route: FastCapableRoute) => Object.prototype.hasOwnProperty.call(route.modes ?? {}, "fast")

export function exactRouteFastMode(
  route: FastCapableRoute | undefined,
  tier: string,
  siblings: readonly FastCapableRoute[] = [],
): FastMode | undefined {
  if (!route) return
  if (offersFast(route)) {
    const subscription = route.provider?.id === "openai-codex"
    return {
      active: tier === "fast",
      offered: true,
      ...(subscription ? { note: "Included in your ChatGPT subscription." } : {}),
    }
  }
  // The same model has a Fast tier on another route: say so rather than
  // letting the section disappear when the route changes.
  const base = route.id ? routeModelBase(route.id) : undefined
  const elsewhere = base
    ? siblings.filter(
        (sibling) => sibling !== route && !!sibling.id && routeModelBase(sibling.id) === base && offersFast(sibling),
      )
    : []
  if (!elsewhere.length) return
  const names = [
    ...new Set(elsewhere.map((sibling) => sibling.provider?.name ?? sibling.provider?.id ?? "another route")),
  ]
  return { active: false, offered: false, note: `Not offered on this route. Available through ${names.join(" or ")}.` }
}
