# Source-Neutral Link Governance

This repository must keep documentation portable across GitHub, mirrors, local
checkouts, release archives, and generated documentation sites. Documentation
source should not depend on GitHub's web renderer when a repo-local path can
describe the same target.

## Rules

- Link to repo-owned documents, scripts, config files, skills, templates, and
  other tracked files with relative paths from the current document.
- Do not write repo-owned file references as `github.com/.../blob/...` links in
  documentation source.
- Do not write repo-owned file references as `raw.githubusercontent.com/...`
  links in documentation source.
- Install and update prompts must describe the selected package location as
  `<source>` instead of hard-coding one host. `<source>` may be an official
  upstream URL, a mirror URL, a local checkout path, or a release archive.
- Keep paired public entry docs aligned, especially `README.md` and
  `README.zh.md`.

## Allowed External Exceptions

External links remain appropriate when the target is not a repo-local file:

- project home links, stars, forks, activity, Issues, Pull Requests, Releases,
  and other GitHub collaboration surfaces;
- badge, visitor, image, or generated status services;
- upstream project pages and contributor profiles;
- official provenance, license, citation, or support references that are
  intentionally external;
- tests or config fixtures that explicitly model the official upstream URL.

These exceptions must not be used for ordinary navigation between repo-owned
files. When a relative path works, use the relative path.

## Verification

`tests/runtime_neutral/test_docs_source_neutral_links.py` enforces the primary
source-neutral contract:

- documentation surfaces reject repo-owned `github.com/.../blob/...` links;
- documentation surfaces reject repo-owned `raw.githubusercontent.com/...`
  links;
- install prompts must use the `<source>` placeholder for selected package
  location.
