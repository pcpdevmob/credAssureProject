# ADR 0034 — Image digest pinning: tooling now, pins from a networked machine

Status: Accepted · Date: 2026-11-18 · Scope #41 · Plan v3.4 P10 · Relates to ADR 0028, BUILD_SCOPE cut rule

## Context
Scope #41 asks for an SBOM in CI and images pinned by digest. The SBOM is built (`make sbom`, CI artifact
`sbom-cyclonedx`). Pinning needs each image's registry digest, and the workspace that built P10 cannot reach Docker Hub,
GHCR or the Langfuse registry. A digest written from memory would be wrong and unverifiable.

## Decision
- `scripts/pin_images.py` (`make pin-images`) rewrites every `FROM` in `deploy/docker/*` and every Compose `image:` to
  `name:tag@sha256:<multi-arch index digest>`, keeping the tag. `make pin-images ARGS=--check` lists unpinned images
  and needs no network.
- The pins themselves are committed from a machine with Docker and registry access, before the release build. This is
  tracked as human review H17. Until then the images are pinned by tag only, and `RELEASE.json` records the built
  image IDs so a release is still identifiable.
- This is a partial deferral of #41, recorded here as BUILD_SCOPE requires for any cut.

## Consequences
- A `docker compose build` before H17 may pull newer base images under the same tag.
- After H17, updating a base image is a deliberate `make pin-images` run and a reviewed diff.
