# CredAssure Setup Guide (Mac and Windows)

Nov 19, 2026 · Pritish Patil

This guide takes a new Mac or Windows machine from nothing to a running CredAssure: API, web app, local model and the 100-item evaluation. On Windows everything runs inside WSL2 (Ubuntu); only Ollama runs on Windows itself.

## What you need

Install the tools below before you start. On Windows every tool except Ollama goes inside WSL2 (Ubuntu), not on Windows itself.

| Tool | Version | Mac | Windows (inside WSL2 Ubuntu unless noted) | Check |
| --- | --- | --- | --- | --- |
| git | any recent | Xcode Command Line Tools or Homebrew | `apt install git` | `git --version` |
| make, sqlite3, openssl | system | Xcode Command Line Tools | `apt install build-essential sqlite3 openssl` | `make -v` |
| uv | latest | `brew install uv` | install script from astral.sh | `uv --version` |
| Python | 3.12 (uv installs it) | `uv python install 3.12` | `uv python install 3.12` | `uv run python -V` |
| Node.js + npm | 22 LTS (22.12 or later) | `brew install node@22` | nvm, then `nvm install 22` | `node -v` |
| Ollama | latest | Ollama app for macOS | Ollama for Windows (on Windows, not WSL) | `ollama --version` |
| Docker | optional (Langfuse tracing only) | Docker Desktop | Docker Desktop with WSL integration | `docker compose version` |

**Hardware.** A 16 GB Apple Silicon Mac runs `qwen3:8b` on its GPU at an 8K context. On Windows, an NVIDIA GPU with 8 GB or more of VRAM is recommended; on CPU alone the model works but a full evaluation takes several hours.

**Disk.** Allow about 15 GB: the model (~5 GB), the embedding and reranker models (~1.5 GB, downloaded on first use), the Python and Node dependencies, and the document library.

**Access.** You need read access to the private GitHub repo and a way to get the raw document library: a copy from a teammate, or time to rebuild it from the sources (it is not in git; see *Build the data*). Use **npm** for the web app; don't use yarn or `corepack enable`.

## Set up on a Mac

1. Install the Command Line Tools (git, make, sqlite3):

   ```bash
   xcode-select --install
   ```
2. Install Homebrew from brew.sh if you don't have it, then the tools:

   ```bash
   brew install uv node@22
   echo 'export PATH="/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
   uv python install 3.12
   ```
3. Install the Ollama app from ollama.com, open it once so it appears in the menu bar, then give it an 8K context and pull the models:

   ```bash
   launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
   launchctl setenv OLLAMA_KEEP_ALIVE 30m
   pkill -x Ollama; sleep 2; open -a Ollama
   ollama pull qwen3:8b
   ```

   `launchctl setenv` does not survive a reboot: run the two `setenv` lines and restart the app after every restart of the Mac.
4. Clone the repo onto the working branch and install:

   ```bash
   git clone https://github.com/pcpdevmob/iitkgpCredAssure.git CredAssure
   cd CredAssure
   git checkout feature/LendWise
   git config core.hooksPath .githooks
   make install
   npm install
   ```

`make install` runs `uv sync --all-packages --all-extras`. Never run a bare `uv sync`: it drops the reranker extra. Then continue with *Configure*.

## Set up on Windows

The Makefile and scripts need a Linux shell, so the project runs inside WSL2. Ollama runs on Windows, where it can use the GPU, and WSL reaches it on `localhost`. Windows 11 is assumed.

1. **Install WSL2 with Ubuntu.** In PowerShell as Administrator, then restart:

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

   Open *Ubuntu* from the Start menu and create your Linux user.
2. **Let WSL reach Windows on localhost.** Create `C:\Users\<you>\.wslconfig` with:

   ```ini
   [wsl2]
   networkingMode=mirrored
   ```

   Then run `wsl --shutdown` in PowerShell and reopen Ubuntu.
3. **Install Ollama for Windows** from ollama.com. Give it an 8K context, restart it, and pull the model (PowerShell):

   ```powershell
   setx OLLAMA_CONTEXT_LENGTH 8192
   setx OLLAMA_KEEP_ALIVE 30m
   ```

   Quit Ollama from the system tray and start it again (a new value only applies after a restart), then:

   ```powershell
   ollama pull qwen3:8b
   ```
4. **Install the tools inside Ubuntu:**

   ```bash
   sudo apt update && sudo apt install -y build-essential git sqlite3 openssl curl
   curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
   uv python install 3.12
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && source ~/.bashrc
   nvm install 22
   curl -s localhost:11434/api/version     # must print Ollama's version
   ```
5. **Clone into the Linux file system** (`~`, not `/mnt/c/...`, which is many times slower), then install:

   ```bash
   cd ~ && git clone https://github.com/pcpdevmob/iitkgpCredAssure.git CredAssure
   cd CredAssure
   git checkout feature/LendWise
   git config core.hooksPath .githooks
   make install
   npm install
   ```

From here on, every command in this guide runs in the Ubuntu terminal, except the `ollama` commands, which you can run in either. Open the repo in VS Code from Ubuntu with `code .` (WSL extension). Browsers on Windows open `http://localhost:8000` and `http://localhost:3000` as usual.

## Configure

Two files hold the settings. `.env` holds your secrets and is never committed; `deploy/env/models-local.env` holds the model settings and is already in the repo.

1. Create `.env` from the template and set two values:

   ```bash
   cp .env.example .env
   ```

   | Key | What to put |
   | --- | --- |
   | `JWT_SECRET` | 32 or more random characters, e.g. the output of `openssl rand -hex 32` |
   | `SEED_PASSWORD_<USERNAME>` | Optional: one account's own password (12+ characters, never shared). Others get a random first password in `var/initial-passwords.txt` |

   Leave the model keys empty for local runs. Never commit `.env`, paste it into chat, or share it.
2. Check the model settings. `make` reads `deploy/env/models-local.env` by default (`MODELS=local`). It points at Ollama (`http://localhost:11434/v1`, `qwen3:8b`), embeds and reranks locally (`bge-small`, `bge-reranker-base`), and sets the copilot's answerability threshold. Don't edit it for a normal setup.
3. Confirm Ollama has the 8K context. A model only shows in `ollama ps` while it is loaded, so load it first:

   ```bash
   ollama run qwen3:8b "hi" >/dev/null
   ollama ps            # CONTEXT must say 8192
   ```

   If it says 2048 or 4096, the context setting was lost: repeat step 3 of your platform's setup and restart Ollama. Runs on a smaller context silently cut the prompts and score far lower.

The graded course endpoint (`MODELS=course`) needs its own keys and certificates from the course portal; see `docs/setup/prerequisites.md` in the repo.

## Build the data and the document library

The synthetic data is in git and frozen; the HR database, case database and search index are built locally. The raw regulatory documents are **not** in git (legal basis L3/L4), so copy them from a teammate or rebuild them from the sources (step 2).

1. Build the HR store and the case and corpus databases (seeds the sign-in users):

   ```bash
   make hr-db
   make db
   ```
2. Get the raw document library into `data/corpus/raw/` in the repo. It is never in git: the Acts are legal basis L3 ("never commit raw text") and the RBI, CGTMSE and bank documents are L4 ("files never redistributed"), and `make corpus-audit` fails on any committed raw file. Use one of these:
   - **Copy it** (fastest): download `credassure-share-2026-11-19.zip` (~870 MB) from Pritish's Google Drive (shared only with the team, never by public link) into the repo folder and unzip it there: `unzip credassure-share-2026-11-19.zip`. It fills `data/corpus/raw/` (1,092 documents), `data/corpus/text/` (the extracted text the index is built from, so the index matches the evaluated one) and `var/eval/` (the 88/100 run and the five ablation runs). Then delete the zip. Never commit it or its contents to git.
   - **Rebuild it from the sources** (slower, no copy needed): download what can be fetched automatically, then save the rest by hand from the list it writes, then import:

     ```bash
     make corpus-download      # 1 request a second; blocked hosts go to the manual list
     # save each file listed in data/corpus/MANUAL_DOWNLOADS.md into data/corpus/raw/
     make corpus-import
     ```

     RBI, e-Gazette, incometaxindia and India Code are always downloaded by hand, from a personal network.

   Either way, check every file against the committed hashes:

   ```bash
   make corpus-verify
   ```

   Fix any file it reports as missing or changed before going on. Never commit anything under `data/corpus/raw/` or `data/corpus/text/`.
3. Build the search index (keyword index plus local embeddings):

   ```bash
   make ingest
   ```

   The first run downloads the embedding and reranker models from Hugging Face (~1.5 GB) and takes a while. A complete library reports about 1,084 real and 191 synthetic documents (1,275 in total).

Don't run `make data` or `make testset`: both refuse once the data is frozen, by design.

## Run the app

Use two terminals, with Ollama already running (menu bar on Mac, system tray on Windows).

1. **API**, terminal 1:

   ```bash
   make run-api
   ```

   Check it in terminal 2:

   ```bash
   curl -s localhost:8000/v1/health/live      # {"status":"ok"}
   curl -s localhost:8000/v1/health/ready     # databases, model circuit, quota
   ```

   Swagger is at http://localhost:8000/docs.
2. **Web app**, terminal 2:

   ```bash
   make run-ui
   ```

   Open http://localhost:3000 and sign in with the account's first password from `var/initial-passwords.txt`; you are asked to change it.

| Username | Role |
| --- | --- |
| `demo.preparer`, `demo.preparer2`, `prep.e001` to `prep.e020` | Preparer: create cases, upload, run stages, ask the copilot |
| `demo.director` | Director, Finance: decides proposals below ₹1.5 crore |
| `demo.vp` | VP, Finance: decides proposals above ₹1.5 crore and held boundary cases |
| `demo.evaluator` | Evaluator: runs evaluations, reads traces and the audit log |

Whoever prepares a case can't approve it. Some `prep.e0xx` users fail onboarding on purpose (expired training, wrong role).

Before committing any code change, run `make check` (lint, types, tests, security scan); the pre-push hook runs the same checks.

## Run the evaluation

The evaluation starts its own copy of the API, so `make run-api` doesn't need to be running. Each run writes a folder under `var/eval/`. A full run takes about 40 minutes on a 16 GB Apple Silicon Mac; keep the machine awake (on Mac, prefix commands with `caffeinate -i`; on Windows, set *Sleep* to *Never* while plugged in).

1. Full run (100 items), then save its folder name:

   ```bash
   make eval
   RUN=$(ls -1d var/eval/*T* | grep -Ev -- '-A[0-9]+$' | tail -1); echo $RUN
   cat $RUN/summary.json
   ```
2. Ablations A1 to A5, each on its own categories (about 1 to 2 hours in total):

   ```bash
   make eval-ablations
   ABL=$(ls -1d var/eval/*-A[0-9] | tail -5 | tr '\n' ' '); echo $ABL
   ```
3. Judge J1 and the human sample:

   ```bash
   make eval-judge RUN=$RUN        # grades answers, writes a 20% human sample
   # a teammate who did not write those gold answers labels the sample, then:
   make eval-kappa RUN=$RUN
   ```
4. Report:

   ```bash
   make eval-report RUN=$RUN ABL="$ABL" OUT=evaluation/reports/E13-<date>.md
   ```

Scored runs always call the model; they never reuse cached replies. `RUN` and `ABL` only last for the current terminal: in a new one, set them again from the folder names. Never edit anything under `evaluation/testset/v1/` or `evaluation/retrieval/v1/`; they are frozen.

**What to expect.** On `qwen3:8b` at an 8K context, the reference run (19 Nov 2026) scored **88/100**: every category full except regulatory at 13/25. Regulatory moves by about one item between runs, because the model does not always cite the same passage. A run far below this usually means the context fell back to 2048 or the document library is incomplete; see *Troubleshooting*.

**Labelling without re-running.** The shared zip includes the reference run and the five ablation runs under `var/eval/`, so a teammate can label the J1 sample with `make eval-judge RUN=var/eval/20261119T091531` without re-running the 40-minute evaluation (the judge itself still needs Ollama).

## Troubleshooting

These are the problems the team has already hit, with their fixes.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: sentence_transformers` during `make ingest` or `make eval` | Dependencies installed with a bare `uv sync`, without extras | `make install` |
| `prompt_tokens` stuck near 2050; copilot abstains on most questions | Ollama running with a 2048 context | Set `OLLAMA_CONTEXT_LENGTH=8192` (Mac: `launchctl setenv`; Windows: `setx`), restart Ollama, check `ollama ps` |
| `ollama ps` prints nothing | No model is loaded right now (normal after 5 idle minutes) | `ollama run qwen3:8b "hi" >/dev/null`, then `ollama ps` |
| `bind: address already in use` from `ollama serve` | The Ollama app is already running | Use the running app; don't start a second server |
| Quitting Ollama from a script is cancelled on Mac | The app asks for confirmation | Quit from the menu bar, or `pkill -x Ollama` |
| `zsh: parse error near` a command with `<run>` | The angle-bracket placeholder was pasted as typed | Replace `<run>` with the real folder, e.g. `var/eval/20261118T223845` |
| `no matches found: var/eval/...-A*` | Each ablation folder has its own timestamp | Use the `ABL=` line from *Run the evaluation* |
| `/results.jsonl: No such file or directory` | `RUN` is empty in a new terminal | `RUN=var/eval/<folder>` again |
| Many tests fail with a missing `hr.db` after switching branches | `hr.db` is git-ignored and was not built in this checkout | `make hr-db` |
| Push refused at the `openapi-diff` step | No local `main` branch to compare against | `git fetch origin main && git branch main origin/main` |
| Sign-in fails from the web app | Web app on a port the API doesn't allow | Use port 3000 (default) or 5173 |
| WSL: `curl localhost:11434` fails | Mirrored networking not on, or Ollama not running on Windows | Check `.wslconfig`, run `wsl --shutdown`, start Ollama |
| WSL: installs and tests are very slow | Repo cloned under `/mnt/c` | Clone into `~` inside Ubuntu |

More detail is in the repo: `README.md` and `docs/setup/` (`prerequisites.md`, `local-dev.md`, `troubleshooting.md`).
