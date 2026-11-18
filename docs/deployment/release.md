# Release

Scope #37 (release bundle) and #41 (supply-chain evidence).

## Version
Semantic versioning. `CHANGELOG.md` (Keep a Changelog) gets a `## [x.y.z] - date` section before tagging. Tags are
annotated (`git tag -a v1.0.0 -m ...`) and pushed only by the repo owner.

## Bundle
```bash
make release VERSION=1.0.0     # var/release/v1.0.0/
```
| File | Contents |
|---|---|
| `RELEASE.json` | version, git commit (and whether the tree was dirty), SHA-256 of `data/frozen/v1/SHA256SUMS`, `evaluation/FROZEN.sha256`, `config/guardrails.lock`, `uv.lock`, `package-lock.json`, `openapi.json`; the newest report per evaluation id; Docker image IDs where built; the CHANGELOG section |
| `sbom.cdx.json` | CycloneDX 1.5 SBOM of every locked Python and npm package (`make sbom`; CI uploads it as the `sbom-cyclonedx` artifact) |
| `reports/` | copies of those evaluation reports |

Build the images first (`make up`, or `docker compose -f deploy/compose/compose.yaml build`) on the release machine so
`RELEASE.json` records their IDs; otherwise it says Docker was not available.

## Image pinning
`make pin-images ARGS=--check` lists every `FROM` and Compose `image:` without a digest. `make pin-images` (Docker and
registry access needed) rewrites them to `name:tag@sha256:<index digest>`, keeping the tag. Run it on a machine with
network access and commit the result before the release build.
