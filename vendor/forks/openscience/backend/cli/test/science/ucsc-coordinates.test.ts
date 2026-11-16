import { afterEach, beforeEach, expect, test } from "bun:test"
import { ucsc } from "../../src/science/connectors/genomics/ucsc"
import { clearCache, resetRateLimits } from "../../src/science/connectors/http"

const realFetch = globalThis.fetch

function stub(body: string): { url: () => string } {
  let seen = ""
  globalThis.fetch = (async (url: string) => {
    seen = String(url)
    return new Response(body, { status: 200 })
  }) as unknown as typeof fetch
  return { url: () => seen }
}

beforeEach(() => {
  clearCache()
  resetRateLimits()
})

afterEach(() => {
  globalThis.fetch = realFetch
})

test("a 1-based interval is sent with a 0-relative start", async () => {
  const s = stub('{"dna":"ACGT"}')
  await ucsc.fetch("chr1:100,000-100,010", { params: { genome: "hg38" } })
  // The API documents start as 0-relative and end as 1-relative, so a 1-based
  // inclusive 100000-100010 is start=99999&end=100010.
  expect(s.url()).toContain("start=99999&end=100010")
})

test("a single-base interval asks for the sequence, not the search endpoint", async () => {
  const s = stub('{"dna":"A"}')
  await ucsc.fetch("chr17:7676154-7676154", { params: { genome: "hg38" } })
  expect(s.url()).toContain("/getData/sequence")
  expect(s.url()).toContain("start=7676153&end=7676154")
  expect(s.url()).not.toContain("/search")
})

test("a long interval is still capped at 50,000 bases", async () => {
  const s = stub('{"dna":"ACGT"}')
  await ucsc.fetch("chr1:1-100000", { params: { genome: "hg38" } })
  expect(s.url()).toContain("start=0&end=50001")
})

test("a non-position term goes to the search endpoint", async () => {
  const s = stub('{"positionMatches":[]}')
  await ucsc.fetch("BRCA1", { params: { genome: "hg38" } })
  expect(s.url()).toContain("/search?search=BRCA1")
})
