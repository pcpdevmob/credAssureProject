# Hosted deployment on Azure (evaluators' link)

One Azure VM runs the app for evaluators and mentors at `https://credassure.sharentest.com`, from submission (27 Nov)
to about 19 Dec, then it is deleted. The 5 Dec live demo still runs on the Mac (ADR 0036); this link is the backup.
Plan, costs and decisions: `claude/CredAssure_Deployment_Plan.md` in the Project.

```
browser ──HTTPS──▶ Caddy (80/443, certificate) ──▶ web (static app)
                                               └─▶ /v1 → gateway ──▶ course Qwen3-8B, else Hugging Face (Featherless)
                    disk: var/case.db · var/corpus.db · var/chroma-local-bge · data/frozen/v1/hr.db
```

| File | What it does |
|---|---|
| `deploy/compose/production.yaml` | Caddy + gateway + web; only Caddy publishes ports (80, 443); restart on failure; health check; logs capped (5 × 10 MB per service) |
| `deploy/caddy/Caddyfile` | HTTPS for `$DOMAIN`; `/v1/*` → gateway (streams unbuffered), everything else → web |
| `deploy/env/models-hosted.env` | Course model first, Hugging Face fallback; the evaluated retrieval settings (same as `models-local.env`); MFA on |
| `deploy/env/server.env.example` | Template for the server's `.env`: domain, keys, secrets, seed passwords |
| `deploy/scripts/server-setup.sh` | One-time VM setup: Docker, firewall (22/80/443), swap, sqlite3, security updates, nightly backup |
| `deploy/scripts/prod.sh` | `docker compose` for this stack (`up -d --build`, `ps`, `logs`, `restart`, `down`) |
| `deploy/scripts/smoke.sh` | From any laptop: certificate, web, health, sign-in, cases, copilot, sign-out → PASS/FAIL per step |
| `deploy/scripts/nightly-backup.sh` | Online backup of `case.db` at 02:15 IST, integrity-checked, 7 kept in `var/backups/` |

**Model failover.** Each model call goes to the course endpoint first. If it ends without an answer (no connection,
timeout, server error after the retries, wrong key, or the course circuit is open), the same call is sent once to
Hugging Face → Featherless `Qwen/Qwen3-8B`. A request the endpoint rejects as invalid is not resent. Each switch logs
`llm failover` with the prompt name and the reason. The copilot drops to "unavailable" (gates, figures, routing and
approval keep working) only when **both** endpoints are down. `LLM_FALLBACK_*` is unset everywhere else, so tests and
the evaluation are unchanged.

## Before the day (Pritish, ~45 min)

1. **Hugging Face:** account → Settings → Billing → add $5 credit → Access Tokens → *fine-grained* token with
   "Make calls to Inference Providers". Keep it in your password manager.
2. **Course endpoint:** the group key and the vm06 CA file (`.pem`).
3. **DNS:** tell Claude the output of `dig +short NS sharentest.com` (who hosts the domain's DNS).
4. **On the Mac** (one time, before copying): `make hr-db`; check `var/corpus.db` and `var/chroma-local-bge/` exist.

## Deployment day (~2 h, Claude gives each command)

1. **Resource group.** Azure portal → Resource groups → Create → `credassure-rg`, region **Central India**.
2. **VM.** Virtual machines → Create → Ubuntu Server 24.04 LTS, size **B4as_v2**, authentication **SSH public key**
   (download the `.pem`), inbound ports **SSH (22)** only, OS disk 64 GB Standard SSD.
3. **Network.** On the VM's public IP: set **Static**, DNS name label `credassure-demo`. In the network security
   group: allow **80** and **443** from Any; restrict **22** to *My IP address*.
4. **DNS record.** At the DNS provider of `sharentest.com`: **A** record, name `credassure`, value = the VM's IP,
   TTL 300 (Cloudflare: *DNS only*, grey cloud). Check from the Mac: `dig +short credassure.sharentest.com`.
5. **Connect** from the Mac:
   ```bash
   chmod 600 ~/Downloads/credassure_key.pem
   ssh -i ~/Downloads/credassure_key.pem azureuser@credassure-demo.centralindia.cloudapp.azure.com
   ```
6. **Set up** (on the VM):
   ```bash
   git clone https://github.com/pcpdevmob/iitkgpCredAssure.git credassure && cd credassure
   sudo bash deploy/scripts/server-setup.sh
   exit   # log in again so the docker group applies, then: cd credassure
   cp deploy/env/server.env.example .env && chmod 600 .env
   openssl rand -base64 48   # → JWT_SECRET
   openssl rand -base64 32   # → MFA_ENCRYPTION_KEY
   nano .env                 # fill: LLM_API_KEY, LLM_FALLBACK_API_KEY, JWT_SECRET, MFA_ENCRYPTION_KEY, SEED_PASSWORD
   ```
   The repository is public; `git clone` needs no login. Use the `main` branch (merged code only).
7. **Copy the data** (from the Mac, in the repo folder). These files stay on the VM (legal basis L4: local use only):
   ```bash
   K=~/Downloads/credassure_key.pem; H=azureuser@credassure-demo.centralindia.cloudapp.azure.com
   scp -i $K var/corpus.db $H:credassure/var/
   scp -i $K -r var/chroma-local-bge $H:credassure/var/
   scp -i $K data/frozen/v1/hr.db $H:credassure/data/frozen/v1/
   scp -i $K <path-to-course-ca>.pem $H:credassure/var/certs/course-ca.pem
   ```
   Then on the VM: `sudo chown -R 10001:10001 var` (the gateway container's user).
8. **Start** (only once `dig` shows the VM's IP):
   ```bash
   deploy/scripts/prod.sh up -d --build        # first build ~10–15 min (models are baked into the image)
   deploy/scripts/prod.sh ps                   # gateway "healthy", caddy and web "running"
   deploy/scripts/prod.sh logs caddy | grep -i certificate   # "certificate obtained successfully"
   ```
9. **Demo data and admin** (on the VM; the gateway is stopped for the reset):
   ```bash
   deploy/scripts/prod.sh stop gateway
   deploy/scripts/prod.sh run --rm --no-deps gateway python scripts/demo_reset.py
   deploy/scripts/prod.sh run --rm --no-deps -e BOOTSTRAP_ADMIN_PASSWORD='<12+ chars, no part of the name>' \
     gateway python -m credassure.ledger.seed var/case.db --bootstrap-admin it.admin
   deploy/scripts/prod.sh up -d
   ```
10. **Check the model path** (on the VM): `deploy/scripts/prod.sh logs gateway | grep -c "llm failover"` after a copilot
    question. 0 = the course endpoint answered. Every call failing over = the course endpoint is not reachable from
    Azure (VPN-only?): switch to Hugging Face only with the commented block in `.env`, then `prod.sh up -d`.
11. **Smoke test** (from the Mac):
    ```bash
    SMOKE_USER=prep.e001 SMOKE_PASSWORD='<its password>' deploy/scripts/smoke.sh https://credassure.sharentest.com
    ```
    All lines PASS. Then sign in as `it.admin` in the browser: change the temporary password, enrol MFA, create one
    evaluator account per mentor (Accounts page).
12. **Budget alert.** Cost Management → Budgets → $100 monthly, emails at 50 % and 80 %.

## Running it (5 min a day)

| When | What |
|---|---|
| Daily | Run `smoke.sh` (or sign in and open a case); glance at Azure cost |
| Daily, automatic | `case.db` backup at 02:15 IST → `var/backups/` (7 kept); log in `/var/log/credassure-backup.log` |
| Weekly | Portal → VM → Disks → snapshot; `prod.sh logs --since 168h gateway \| grep -c "llm failover"`; Hugging Face credit |
| Code fix (blockers only) | `git pull && deploy/scripts/prod.sh up -d --build` |
| End (~19 Dec) | `scp` the newest `var/backups/*.gz` to the Mac, then delete `credassure-rg` (stops all charges) |

## If X breaks, do Y

| Sign | Likely cause | Do |
|---|---|---|
| Browser: certificate warning or "can't reach" | DNS not pointing at the VM yet, or 80/443 closed | `dig +short credassure.sharentest.com` = VM IP? NSG allows 80/443? `prod.sh logs caddy`. Fallback: set `DOMAIN=credassure-demo.centralindia.cloudapp.azure.com` in `.env`, `prod.sh up -d` |
| `smoke.sh`: gateway ready FAIL / `prod.sh ps` shows unhealthy | gateway failed at start | `prod.sh logs --tail 80 gateway`. "JWT_SECRET" / "MFA_ENCRYPTION_KEY" → fill `.env`; "hr.db is not readable" → copy hr.db (step 7) and `chown` |
| `model=open` in smoke, copilot "unavailable" | both model endpoints down | Course key or CA wrong? HF credit used up? Fix `.env`, `prod.sh up -d`. Figures and approvals keep working meanwhile |
| Many `llm failover` lines | course endpoint slow or down | Nothing to do (Hugging Face is answering); check the HF credit |
| Copilot answers "I can't verify…" for everything | index not mounted | `ls var/chroma-local-bge` on the VM; re-copy (step 7), `chown`, `prod.sh restart gateway` |
| "database is locked" / permission denied in `var/` | ownership | `sudo chown -R 10001:10001 var && prod.sh restart gateway` |
| Disk full | logs or images | `docker system prune -f` (keeps running containers and volumes) |
| VM slow, out of memory | embedder + reranker + a burst | `prod.sh restart gateway`; if it repeats, resize to `B4as_v2` → `D4as_v5` in the portal |
| Need to restore a backup | bad data | `prod.sh stop gateway`; `gunzip -c var/backups/case-<date>.db.gz > var/case.db`; `rm -f var/case.db-wal var/case.db-shm`; `sudo chown 10001:10001 var/case.db`; `prod.sh up -d` |

## Security notes

- Only 80/443 are open to the internet; SSH by key from one IP; the gateway, web and data are not reachable directly.
- Secrets live only in the VM's `.env` (mode 600), never in git. `docker compose config` prints them: don't share its output.
- MFA is enforced for Director, VP and account admin (`MFA_ENFORCED=true`); evaluators sign in with their own accounts.
- Only synthetic data; PII redaction runs before every model call, including the Hugging Face fallback.
- `/docs` (interactive API) is not routed by Caddy, so it is not public.
