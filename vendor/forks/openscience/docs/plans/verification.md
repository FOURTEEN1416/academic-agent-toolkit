# Verification loop

Run this loop after each major milestone.

## Local gates

1. Run focused tests for changed behavior.
2. Run `bun test` from `backend/cli`.
3. Run the workspace frontend tests and type checks used by the repository.
4. Build the distributable CLI packages.
5. Confirm the diff contains no Atlas or Memory implementation changes unless
   the user explicitly reopens that scope.

## Test-channel package gate

1. Commit and push only `aayam/kernel-science-workbench`.
2. Trigger the `test publish` workflow with packaged E2E and OS smoke inputs.
3. Record the unique prerelease version and workflow URL.
4. Install that exact version in a new isolated root.
5. Launch it with Atlas offline and no inherited OpenScience state.
6. Test the completed milestone in the browser at desktop, 720–1099px, and
   under 720px widths.
7. Inspect console errors and preserve screenshots for regressions.

Production/latest npm publishing is never part of this loop.

## Final gate

After product acceptance is complete, repair CI/CD and require the full
cross-platform, security, accessibility, package, and upgrade matrix to pass.
