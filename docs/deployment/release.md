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

## v1.1.0 checklist (submission, 27 Nov 2026)
Checked on 25 Nov: `make release VERSION=1.1.0` builds the bundle from `main` (CHANGELOG section found; frozen v1 and
v2 hashes, test-set hash, guardrail lock, locks and `openapi.json` recorded; the newest E-reports and the G4 gate
report copied).

1. Done 25 Nov: K4 (#57), K5 prep, the safety_v2 freeze and the K5 results PR (#69) merged; #70 ("No loan needed")
   merged. `RELEASE.json` also hashes `evaluation/safety_v2/FROZEN.sha256`.
2. Done on branch `release/v1.1.0`: `CHANGELOG.md` section dated 2026-11-27; every line's PR merged. Merge that PR.
3. Suresh, on the Mac, from a clean `main` (`git status` empty, so `git_dirty` is false):
   `git checkout main && git pull && make install && make release VERSION=1.1.0`. Optional: build the images first
   (`make up`) so their IDs are recorded. Check `var/release/v1.1.0/RELEASE.json`: `git_commit` is the merge commit of
   step 2 and `git_dirty` is false. Send RELEASE.json and sbom.cdx.json to the owner.
4. Owner only: `git tag -a v1.1.0 <git_commit from RELEASE.json> -m "CredAssure 1.1.0: IIT KGP capstone submission"`
   and `git push origin v1.1.0`, then a GitHub release with `RELEASE.json` and `sbom.cdx.json` attached.
