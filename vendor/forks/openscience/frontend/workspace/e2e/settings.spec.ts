import { test, expect } from "./fixtures"
import { openSettings } from "./utils"

test("settings dialog navigates between sections and closes", async ({ page, gotoSession }) => {
  await gotoSession()

  const dialog = await openSettings(page)
  // The dialog opens on General; the rail lists every destination as spaced
  // groups without labels and ends in the account.
  await expect(dialog.getByRole("heading", { name: "General", exact: true })).toBeVisible()
  await expect(dialog.getByRole("region", { name: "Sound effects", exact: true })).toBeVisible()
  await expect(dialog.getByRole("switch", { name: "Play sound effects", exact: true })).toBeVisible()
  await expect(dialog.getByRole("button", { name: "Open Ace account", exact: true })).toBeVisible()

  await dialog.getByRole("button", { name: "Ace", exact: true }).click()
  await expect(dialog.getByRole("heading", { name: "Ace", exact: true })).toBeVisible()
  await expect(dialog.getByRole("heading", { name: "Account", exact: true })).toBeVisible()
  await expect(dialog.getByRole("button", { name: /^(?:Sign in|Disconnect)$/ })).toBeVisible()
  await expect(dialog.getByRole("heading", { name: "Model access", exact: true })).toBeVisible()
  await expect(dialog.getByRole("group", { name: "Model access mode", exact: true })).toBeVisible()

  // Trace sharing is a consent control, so it lives at the end of Permissions.
  await dialog.getByRole("button", { name: "Permissions", exact: true }).click()
  await expect(dialog.getByRole("heading", { name: "Permissions", exact: true })).toBeVisible()
  await expect(dialog.getByRole("heading", { name: "Data & privacy", exact: true })).toBeVisible()

  const back = dialog.getByRole("button", { name: "Back" })
  const forward = dialog.getByRole("button", { name: "Forward" })
  await expect(back).toBeEnabled()
  await back.click()
  await expect(dialog.getByRole("heading", { name: "Ace", exact: true })).toBeVisible()
  await expect(forward).toBeEnabled()
  await forward.click()
  await expect(dialog.getByRole("heading", { name: "Permissions", exact: true })).toBeVisible()

  await dialog.getByRole("button", { name: "Close" }).click()
  await expect(dialog).toHaveCount(0)
})

test("narrow settings menu owns its first Escape press", async ({ page, gotoSession }) => {
  await gotoSession()

  const dialog = await openSettings(page)
  await page.setViewportSize({ width: 560, height: 800 })
  const menu = dialog.locator(".settings-nav__mobile-trigger")
  await menu.click()
  await expect(menu).toHaveAttribute("aria-expanded", "true")

  await menu.press("Escape")
  await expect(dialog).toBeVisible()
  await expect(menu).toBeFocused()
  await expect(menu).toHaveAttribute("aria-expanded", "false")

  await menu.press("Escape")
  await expect(dialog).toHaveCount(0)
})
