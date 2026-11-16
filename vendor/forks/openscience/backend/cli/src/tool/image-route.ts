import { Provider } from "@/provider/provider"
import { OpenScience } from "@/openscience"
import { Config } from "@/config/config"

/**
 * Which account renders images. Three routes exist: Ace, whose managed
 * gateway relays the image endpoint and settles it from the Wallet; the
 * person's own Gemini key; and the person's own OpenAI key. A personal
 * OpenRouter key is not a route: image spend goes through Ace or a provider
 * the person holds an account with directly. The system prompt states the
 * answer up front so the agent asks for a route instead of drawing a
 * schematic by hand when none is connected.
 */
export namespace ImageRoute {
  export type Kind = "ace" | "gemini" | "openai"

  export type Route = {
    kind: Kind
    key: string
    base: string
    /** How the route is named in receipts and errors. */
    label: string
    /** The model the route renders with, in the route's own naming. */
    model: string
  }

  /** Nano Banana Pro on Gemini and through Ace; GPT Image 2 on OpenAI. */
  export const MODELS: Record<Kind, string> = {
    ace: "google/gemini-3-pro-image",
    gemini: "gemini-3-pro-image",
    openai: "gpt-image-2",
  }

  const key = (provider: Awaited<ReturnType<typeof Provider.getProvider>> | undefined) =>
    typeof provider?.options?.apiKey === "string" ? provider.options.apiKey : provider?.key

  const base = (provider: Awaited<ReturnType<typeof Provider.getProvider>> | undefined, fallback: string) =>
    typeof provider?.options?.baseURL === "string" ? provider.options.baseURL.replace(/\/+$/, "") : fallback

  export async function resolve(): Promise<Route | undefined> {
    const mode = (await Config.get().catch(() => undefined))?.billing?.llm
    const google = await Provider.getProvider("google").catch(() => undefined)
    const openai = await Provider.getProvider("openai").catch(() => undefined)
    const openrouter = await Provider.getProvider("openrouter").catch(() => undefined)
    const googleKey = key(google)
    const openaiKey = key(openai)
    const managedKey = key(openrouter)
    const own: Route[] = [
      ...(googleKey && !OpenScience.isManagedKeyValue(googleKey)
        ? [
            {
              kind: "gemini" as const,
              key: googleKey,
              base: base(google, "https://generativelanguage.googleapis.com/v1beta"),
              label: "your Gemini key",
              model: MODELS.gemini,
            },
          ]
        : []),
      ...(openaiKey && !OpenScience.isManagedKeyValue(openaiKey)
        ? [
            {
              kind: "openai" as const,
              key: openaiKey,
              base: base(openai, "https://api.openai.com/v1"),
              label: "your OpenAI key",
              model: MODELS.openai,
            },
          ]
        : []),
    ]
    const ace: Route[] =
      openrouter?.source === "managed" && managedKey && OpenScience.isManagedKeyValue(managedKey)
        ? [
            {
              kind: "ace" as const,
              key: managedKey,
              base: base(openrouter, ""),
              label: "Ace",
              model: MODELS.ace,
            },
          ]
        : []
    // The billing mode decides as it does for chat: a managed account renders
    // through Ace, a BYOK account through its own key, and a person with both
    // uses the key they connected themselves.
    if (mode === "managed") return ace[0]
    if (mode === "byok") return own[0]
    return own[0] ?? ace[0]
  }

  export const UNAVAILABLE =
    "Image generation is unavailable. Turn on Ace, or connect a Gemini or OpenAI key in Customize → Models; a personal OpenRouter key does not render images."

  /** The environment line the system prompt carries. */
  export async function line(): Promise<string> {
    const route = await resolve().catch(() => undefined)
    if (route) return `Image generation: available (generate_image renders with ${route.model} via ${route.label})`
    return "Image generation: unavailable (needs Ace or the user's own Gemini or OpenAI key in Customize → Models). When a schematic, diagram or illustration is asked for, say so and ask which route to connect; do not draw it with TikZ, SVG or matplotlib in its place, and do not call generate_image. Plots of data are unaffected and still come from matplotlib."
  }
}
