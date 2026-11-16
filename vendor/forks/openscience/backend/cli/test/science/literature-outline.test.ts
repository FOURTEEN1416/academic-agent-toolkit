import { expect, test } from "bun:test"
import { Literature } from "../../src/research/literature"

test("a paper's outline lists its numbered and standard headings by page, once each", () => {
  const pages = [
    "TabICLv2: In-Context Learning for Tables\n\nAbstract\nWe present...\n\n1 Introduction\nTabular data...",
    "2 Related Work\nPrior work...\n\n2.1 Foundation models for tables\nText here that is much longer than a heading and should not count as one because it runs on and on past the limit of ninety characters",
    "3 Methods\n...\n3.1 Pretraining\n...\nResults\nTable 1 shows...\n\nReferences\n[1] ...",
  ]
  expect(Literature.outline(pages)).toEqual([
    { page: 1, heading: "Abstract" },
    { page: 1, heading: "1 Introduction" },
    { page: 2, heading: "2 Related Work" },
    { page: 2, heading: "2.1 Foundation models for tables" },
    { page: 3, heading: "3 Methods" },
    { page: 3, heading: "3.1 Pretraining" },
    { page: 3, heading: "Results" },
    { page: 3, heading: "References" },
  ])
  expect(Literature.outline(["no headings here, only prose."])).toEqual([])
})
