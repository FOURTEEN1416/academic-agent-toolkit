export const URLS = {
  docs: "https://github.com/synthetic-sciences/OpenScience#readme",
  changelog: "/settings/updates/releases",
  releases: "https://github.com/synthetic-sciences/OpenScience/releases",
  dashboardBilling: "https://app.syntheticsciences.ai/billing",
  /** A team workspace's own billing page; /billing is the signed-in account's Personal wallet. */
  workspaceBilling: (organizationId: string) =>
    `https://app.syntheticsciences.ai/workspace/${encodeURIComponent(organizationId)}/billing`,
} as const
