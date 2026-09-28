import { test, expect } from "./fixtures"

test("global model state mounts on home and project routes without requiring SDK context", async ({
  page,
  gotoSession,
}) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))

  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible()

  await gotoSession()

  expect(errors.filter((error) => error.includes("SDK context must be used within a context provider"))).toEqual([])
})
