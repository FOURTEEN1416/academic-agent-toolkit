import nodefs, { type BigIntStats } from "node:fs"
import fs, { type FileHandle } from "node:fs/promises"
import z from "zod"

/** File IDs are uint64 values on Windows and may exceed JavaScript's exact
 * number range. Keep safe legacy numbers; encode larger IDs as decimal text
 * before JSON or equality can round adjacent files into the same object. */
export namespace FileIdentity {
  const maximum = (1n << 64n) - 1n
  export const Value = z.union([
    z.number().int().nonnegative(),
    z
      .string()
      .regex(/^(0|[1-9][0-9]{0,19})$/)
      .refine((value) => /^(0|[1-9][0-9]{0,19})$/.test(value) && BigInt(value) <= maximum, "File ID exceeds uint64"),
  ])
  export type Value = z.infer<typeof Value>

  export function encode(value: bigint): Value {
    if (value < 0n || value > maximum) throw new Error("File ID is outside uint64 range")
    return value <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(value) : value.toString()
  }

  export function equal(left: Value, right: Value) {
    // In particular, never convert an already-rounded unsafe Number to bigint.
    return BigInt(Value.parse(left)) === BigInt(Value.parse(right))
  }

  export function same(left: { dev: Value; ino: Value }, right: { dev: Value; ino: Value }) {
    return equal(left.dev, right.dev) && equal(left.ino, right.ino)
  }

  function integer(value: bigint) {
    const result = Number(value)
    if (!Number.isSafeInteger(result)) throw new Error("File metadata exceeds the safe integer range")
    return result
  }

  function milliseconds(value: bigint) {
    return Number(value / 1_000_000n) + Number(value % 1_000_000n) / 1_000_000
  }

  export function fromStat(value: BigIntStats) {
    return {
      dev: encode(value.dev),
      ino: encode(value.ino),
      size: integer(value.size),
      mode: integer(value.mode),
      mtimeMs: milliseconds(value.mtimeNs),
      ctimeMs: milliseconds(value.ctimeNs),
      isFile: () => value.isFile(),
      isDirectory: () => value.isDirectory(),
      isSymbolicLink: () => value.isSymbolicLink(),
    }
  }
  export type Stat = ReturnType<typeof fromStat>

  export async function lstat(file: string) {
    return fromStat(await fs.lstat(file, { bigint: true }))
  }

  export async function stat(handle: FileHandle) {
    return fromStat(await handle.stat({ bigint: true }))
  }

  export function fstat(fd: number) {
    return new Promise<Stat>((resolve, reject) => {
      nodefs.fstat(fd, { bigint: true }, (error, value) => {
        if (error) return reject(error)
        try {
          resolve(fromStat(value))
        } catch (error) {
          reject(error)
        }
      })
    })
  }
}
