export function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => {
    if (char === "&") return "&amp;"
    if (char === "<") return "&lt;"
    if (char === ">") return "&gt;"
    if (char === '"') return "&quot;"
    return "&#39;"
  })
}

export function htmlResponse(body: string, init: ResponseInit = {}) {
  const headers = new Headers(init.headers)
  headers.set("Content-Type", "text/html; charset=utf-8")
  headers.set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'none'")
  return new Response(body, {
    ...init,
    headers,
  })
}
