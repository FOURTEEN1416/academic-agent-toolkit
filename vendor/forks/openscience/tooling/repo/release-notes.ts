#!/usr/bin/env bun

import { $ } from "bun"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"

const unsigned = "The Windows desktop installer is unsigned while Microsoft Artifact Signing setup is incomplete."

export function windowsReleaseNote(body: string, signing: string) {
  if (signing !== "true" && signing !== "false") throw new Error("Windows signing state must be explicit")
  if (signing === "false") {
    if (body.split(/\r?\n/).includes(unsigned)) return body
    const newline = body.includes("\r\n") ? "\r\n" : "\n"
    return `${body}${body.endsWith("\n") ? newline : newline + newline}${unsigned}${newline}`
  }
  return body
    .split(/(?<=\n)/)
    .filter((line) => line.replace(/\r?\n$/, "") !== unsigned)
    .join("")
}

if (import.meta.main) {
  const tag = process.env.OPENSCIENCE_RELEASE_TAG ?? ""
  const signing = process.env.OPENSCIENCE_WINDOWS_SIGNING ?? ""
  if (!/^v\d+\.\d+\.\d+$/.test(tag)) throw new Error("Expected an exact stable release tag")
  // Validate before even reading or editing a release.
  windowsReleaseNote("", signing)
  const release = (await $`gh release view ${tag} --json body,isDraft`.json()) as {
    body: string
    isDraft: boolean
  }
  if (release.isDraft !== true || typeof release.body !== "string")
    throw new Error("Only draft release notes may be updated")
  const body = windowsReleaseNote(release.body, signing)
  if (body !== release.body) {
    const directory = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-release-notes-"))
    try {
      const file = path.join(directory, "notes.md")
      await Bun.write(file, body)
      await $`gh release edit ${tag} --notes-file ${file}`
    } finally {
      await fs.rm(directory, { recursive: true, force: true })
    }
  }
}
