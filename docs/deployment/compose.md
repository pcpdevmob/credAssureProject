# Docker Compose

TODO owner: [Name 1].

## Profiles
## No Chroma server

## Corpus tools in a container (ADR 0020)
The `corpus` service (profile `tools`, `deploy/docker/Dockerfile.corpus`) runs the corpus targets:
- as a non-root user;
- with a read-only root filesystem and a `/tmp` tmpfs;
- with `cap_drop: [ALL]`, `no-new-privileges`, 1 GB memory and 1 CPU;
- with only `data/corpus` mounted read-write.

`CORPUS_CONTACT_EMAIL` comes from `.env`.

```bash
make corpus-docker-download   # = docker compose -f deploy/compose/compose.yaml --profile tools run --rm corpus make corpus-download
make corpus-docker-import     # files saved by hand in data/corpus/raw/
make corpus-docker-status
make corpus-docker-ingest     # Phase 7 indexing (make ingest), once implemented
```

Run it from a personal machine and network, not an employer's (ADR 0020).
