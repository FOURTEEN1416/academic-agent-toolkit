export async function installFromGit(fetchFn: typeof fetch, baseUrl: string, url: string) {
  const endpoint = `${baseUrl.replace(/\/+$/, "")}/settings/skills/install`
  const res = await fetchFn(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(text || `Request failed (${res.status})`)
  }
  return res.json() as Promise<{ installed: unknown[]; rejected: unknown[]; warnings: unknown[] }>
}
