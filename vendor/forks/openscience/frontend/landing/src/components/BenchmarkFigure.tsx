import type { Benchmark } from "@/data/benchmarks"
import { BIO_TASKS, NUMBERS, OSB, TB4_BEST, TBS_DOMAINS, type Harness } from "@/data/benchmark"

/* Four figures in one chart language, after the terminal-bench-science.ai
   view: a light grid, quiet ticks, ochre for other agents, and turquoise for
   OpenScience. Drawn at the size they render in a four-column row, so the
   type stays at its nominal size. */

const W = 220
const H = 170
const L = 30
const R = W - 6
const T = 24
const B = H - 30
const ink = "var(--color-text-strong)"
const accent = "var(--color-accent)"
const other = "var(--color-chart-cc)"
const soft = "var(--color-accent-soft)"
const grid = "var(--color-border-weak)"
const tick = { fontSize: 10, fill: "var(--color-text-weak)" } as const

function Frame({
  xs,
  ys,
  xLabel,
  yLabel,
}: {
  xs: [number, string][]
  ys: [number, string][]
  xLabel: string
  yLabel: string
}) {
  return (
    <>
      {ys.map(([y, label]) => (
        <g key={label}>
          <line x1={L} y1={y} x2={R} y2={y} stroke={grid} />
          <text x={L - 5} y={y + 3.5} textAnchor="end" {...tick}>
            {label}
          </text>
        </g>
      ))}
      {xs.map(([x, label]) => (
        <g key={label}>
          <line x1={x} y1={T} x2={x} y2={B} stroke={grid} />
          <text x={x} y={B + 14} textAnchor="middle" {...tick}>
            {label}
          </text>
        </g>
      ))}
      <line x1={L} y1={B + 0.5} x2={R} y2={B + 0.5} stroke="var(--color-text)" />
      <line x1={L + 0.5} y1={T} x2={L + 0.5} y2={B} stroke="var(--color-text)" />
      {xLabel ? (
        <text x={(L + R) / 2} y={H - 2} textAnchor="middle" {...tick}>
          {xLabel}
        </text>
      ) : null}
      <text x={L} y={T - 10} {...tick}>
        {yLabel}
      </text>
    </>
  )
}

function Square({ x, y, mine }: { x: number; y: number; mine?: boolean }) {
  const s = mine ? 7 : 5
  return <rect x={x - s / 2} y={y - s / 2} width={s} height={s} fill={mine ? accent : other} opacity={mine ? 1 : 0.8} />
}

/* Terminal-Bench Science by domain: OpenScience against the strongest
   public entry (Codex, same lead model), dashed. */
function Domains() {
  const [ours, best] = TBS_DOMAINS.series
  const n = TBS_DOMAINS.domains.length
  const sx = (i: number) => L + 12 + (i / (n - 1)) * (R - L - 24)
  const sy = (v: number) => B - ((v - 40) / 60) * (B - T)
  const line = (values: readonly number[]) => values.map((v, i) => `${i ? "L" : "M"}${sx(i)} ${sy(v)}`).join(" ")
  const top = ours.values.reduce((a, v, i) => (v > ours.values[a] ? i : a), 0)
  return (
    <>
      <Frame
        xs={TBS_DOMAINS.domains.map((d, i) => [
          sx(i),
          ({ Engineering: "Eng.", Physical: "Phys." } as Record<string, string>)[d] ?? d,
        ])}
        ys={[50, 70, 90].map((v) => [sy(v), `${v}%`])}
        xLabel=""
        yLabel="solved, by domain"
      />
      <path d={`${line(ours.values)} L${sx(n - 1)} ${B} L${sx(0)} ${B} Z`} fill={soft} stroke="none" />
      <path d={line(best.values)} fill="none" stroke={other} strokeWidth="1" strokeDasharray="3 3" opacity="0.9" />
      <path d={line(ours.values)} fill="none" stroke={accent} strokeWidth="1.25" />
      {ours.values.map((v, i) => (
        <g key={i}>
          <Square x={sx(i)} y={sy(best.values[i])} />
          <Square x={sx(i)} y={sy(v)} mine />
        </g>
      ))}
      <text x={sx(top)} y={sy(ours.values[top]) - 9} textAnchor="middle" fontSize="10.5" fill={ink}>
        OpenScience
      </text>
    </>
  )
}

/* Ranked bars, highest first: Terminal-Bench 4.0 (science) by the best
   entry of each harness, and OpenScience Bench. */
function Comparison({
  rows,
  max,
  label,
}: {
  rows: readonly { name: string; value: number; harness: Harness }[]
  max: number
  label: string
}) {
  const x0 = 76
  const x1 = W - 32
  const pitch = Math.min(26, (H - T) / rows.length)
  const bar = pitch * 0.55
  const sx = (v: number) => x0 + (v / max) * (x1 - x0)
  return (
    <>
      <text x={0} y={T - 10} {...tick}>
        {label}
      </text>
      <line x1={x0 + 0.5} y1={T - 2} x2={x0 + 0.5} y2={T + pitch * rows.length} stroke="var(--color-text)" />
      {rows.map((row, i) => {
        const mine = row.harness === "os"
        const y = T + pitch * i + (pitch - bar) / 2
        const fill = mine ? ink : "var(--color-text-weak)"
        return (
          <g key={row.name}>
            <text x={x0 - 6} y={y + bar / 2 + 3.5} textAnchor="end" fontSize="10.5" fill={fill}>
              {row.name}
            </text>
            <rect
              x={x0 + 1}
              y={y}
              width={sx(row.value) - x0}
              height={bar}
              fill={mine ? accent : other}
              opacity={mine ? 1 : 0.55}
            />
            <text x={sx(row.value) + 5} y={y + bar / 2 + 3.5} fontSize="10" fill={fill}>
              {row.value}%
            </text>
          </g>
        )
      })}
    </>
  )
}

/* BiomniBench-DA: one dot per task, highest first; OpenScience's mean is
   the solid line and AIPOCH's the dashed one. */
function Dots() {
  const scores = [...BIO_TASKS].sort((a, b) => b - a)
  const n = scores.length
  const sx = (i: number) => L + 6 + (i / (n - 1)) * (R - L - 12)
  const sy = (v: number) => B - (v / 100) * (B - T)
  const ours = NUMBERS.bio_mean
  const theirs = NUMBERS.bio_other
  return (
    <>
      <Frame
        xs={[0, 24, 49].map((i) => [sx(i), `${i + 1}`])}
        ys={[25, 50, 75, 100].map((v) => [sy(v), String(v)])}
        xLabel="50 tasks, by score"
        yLabel="score"
      />
      <line x1={L} x2={R} y1={sy(theirs)} y2={sy(theirs)} stroke={other} strokeDasharray="3 3" opacity="0.9" />
      <line x1={L} x2={R} y1={sy(ours)} y2={sy(ours)} stroke={accent} strokeWidth="1.25" />
      {scores.map((v, i) => (
        <circle key={i} cx={sx(i)} cy={sy(v)} r="1.8" fill={accent} opacity={0.9} />
      ))}
      <text x={L + 6} y={sy(theirs) + 13} fontSize="10.5" fill={ink}>
        OpenScience {ours}
      </text>
      <text x={L + 6} y={sy(theirs) + 26} {...tick}>
        AIPOCH {theirs}
      </text>
    </>
  )
}

export function BenchmarkFigure({ benchmark, index }: { benchmark: Benchmark; index: number }) {
  return (
    <div data-component="benchmark">
      <div data-component="stat-illustration">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`${benchmark.name}: OpenScience ${benchmark.score}${benchmark.unit}`}
        >
          {benchmark.chart === "domains" ? <Domains /> : null}
          {benchmark.chart === "ranked" ? <Comparison rows={TB4_BEST} max={80} label="solved, best entry" /> : null}
          {benchmark.chart === "openscience-bench" ? (
            <Comparison
              rows={OSB.rows.map((row) => ({ ...row, name: row.name.replace(" (BYOK)", "") }))}
              max={60}
              label="solved, pass@3"
            />
          ) : null}
          {benchmark.chart === "distribution" ? <Dots /> : null}
        </svg>
      </div>
      <span>
        <span data-slot="fig">Fig {index}.</span>
        <strong>
          {benchmark.score}
          {benchmark.unit}
        </strong>
        <a
          href={benchmark.href}
          {...(benchmark.href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}
        >
          {benchmark.name}
        </a>
      </span>
    </div>
  )
}
