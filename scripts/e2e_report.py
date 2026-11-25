"""make e2e-report: every profile and flow end to end on a private copy of the app; Excel + PDF.

    make e2e-report                                     # report in var/e2e-report/<timestamp>/
    make e2e-report ARGS="--smoke-url https://..."      # also a read-only check of a deployed site

What it does, in order:
1. Starts its own gateway on 127.0.0.1 (a free port) with a fresh case database under
   var/e2e-report/<timestamp>/, newly generated secrets, the model off and MFA on. It never writes
   to var/case.db, the e2e database or any deployed server: write tests only ever go to that
   private gateway. Your .env is not needed (a CASE_DATABASE_URL in it is refused: no MySQL).
2. Drives the real API like the web app does, as every account: the 10 scenarios of
   data/test-pack (expected results from docs/setup/e2e-testing.md part 9), the three question
   cards, seven HR profiles for the preparer check, the approval rules (Director, VP step-up,
   stale report, held case, return, reject, maker-checker), access control, the evaluator, the
   account admin, sessions and lender PDFs.
3. Writes results.json, CredAssure_E2E_Report_<date>.xlsx and .html, and the .pdf when Playwright's
   Chromium is installed (npx playwright install chromium).

--smoke-url only reads: the sign-in page and /v1/health/live and /ready. No sign-in, no data.
All data is synthetic. The model is off, so Ask CredAssure and PDF figure drafting are not covered.
"""

from __future__ import annotations

import argparse
import base64
import glob
import html
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from credassure.security import mfa

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "test-pack"
FROZEN = ROOT / "data" / "frozen" / "v1"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
AREAS = (
    "Test-pack scenarios",
    "Question cards",
    "Preparer check (HR profiles)",
    "Approvals",
    "Access control",
    "Evaluator",
    "Account admin",
    "Sign-in and sessions",
    "Lender PDFs",
    "Deployed site (read only)",
)


@dataclass
class Check:
    area: str
    test: str
    expected: str
    actual: str
    passed: bool
    case: str = ""
    note: str = ""


@dataclass
class Run:
    checks: list[Check] = field(default_factory=list)
    cases: dict[str, str] = field(default_factory=dict)

    def add(self, area: str, test: str, expected: str, actual: str, ok: bool, **kw: str) -> None:
        self.checks.append(Check(area, test, expected, actual, bool(ok), **kw))
        print(f"{'PASS' if ok else 'FAIL'} [{area}] {test}: {actual}", flush=True)

    def guard(self, area: str, test: str, fn: Any) -> None:
        """One check that raised is a failed check, not a stopped run."""
        try:
            fn()
        except Exception as e:
            self.add(area, test, "no error", f"error: {type(e).__name__}: {str(e)[:300]}", False)


def rupees(paise: int | None) -> str:
    """₹ in the Indian grouping (₹1,42,00,000)."""
    if paise is None:
        return "—"
    n = str(paise // 100)
    head, tail = n[:-3], n[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(([head] if head else []) + groups + [tail])


# ---------------------------------------------------------------- the private gateway


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def dotenv_value(key: str) -> str:
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].split("#")[0].strip()
    return ""


LOCAL_ROLES = {
    "preparer": "demo.preparer",
    "preparer2": "demo.preparer2",
    "director": "demo.director",
    "vp": "demo.vp",
    "evaluator": "demo.evaluator",
    "admin": "it.admin",
}


@dataclass
class Accounts:
    """Who plays each role, and their passwords and authenticator keys.

    Local: the seeded accounts with one fixture password. Live: read from an accounts file
    (ROLE_<role>=<username>, PW_<username>=..., TOTP_<username>=...); the tool writes the new
    passwords and authenticator keys back to that file (0600), so the next run signs in again.
    """

    role: dict[str, str]
    pw: dict[str, str] = field(default_factory=dict)
    totp: dict[str, str] = field(default_factory=dict)
    fixture: str = ""
    file: Path | None = None
    base_url: str = ""

    @classmethod
    def load(cls, path: Path) -> Accounts:
        acc = cls(role={}, file=path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, v = (x.strip() for x in line.split("=", 1))
            if k.startswith("ROLE_"):
                acc.role[k[5:].lower()] = v
            elif k.startswith("PW_") and v:
                acc.pw[k[3:]] = v
            elif k.startswith("TOTP_") and v:
                acc.totp[k[5:]] = v
            elif k == "BASE_URL":
                acc.base_url = v
        missing = [r for r in ("preparer", "director", "vp", "evaluator") if r not in acc.role]
        if missing:
            raise SystemExit(f"{path}: set ROLE_{missing[0].upper()}=<username> (see --help)")
        return acc

    def save(self) -> None:
        if not self.file:
            return
        lines = self.file.read_text(encoding="utf-8").splitlines()
        want = {f"PW_{u}": v for u, v in self.pw.items()} | {
            f"TOTP_{u}": v for u, v in self.totp.items()
        }
        out = []
        for line in lines:
            k = line.split("=", 1)[0].strip()
            out.append(f"{k}={want.pop(k)}" if k in want else line)
        out += [f"{k}={v}" for k, v in want.items()]
        self.file.write_text("\n".join(out) + "\n", encoding="utf-8")
        self.file.chmod(0o600)


UVICORN = [sys.executable, "-m", "uvicorn", "credassure.gateway.main:app", "--factory"]


class Gateway:
    """The real gateway (uvicorn) on 127.0.0.1 with its own database; stopped at the end."""

    def __init__(self, out: Path) -> None:
        self.out = out
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.db = out / "case.db"
        self.fixture = "E2e-" + secrets.token_urlsafe(18)  # every seeded account's first password
        self.admin_pw = "Adm-" + secrets.token_urlsafe(18)
        self.proc: subprocess.Popen[bytes] | None = None
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("SEED_PASSWORD")}
        self.env.update(
            APP_ENV="dev",
            TENANT_ID="default",
            CASE_DB=str(self.db),
            CHECKPOINT_DB=str(out / "checkpoints.db"),
            LLM_ENABLED="false",
            LLM_CACHE_PATH="",
            REPLAY_MODE="false",
            TRACING_ENABLED="false",
            LANGFUSE_HOST="",
            JWT_SECRET=secrets.token_urlsafe(48),
            MFA_ENCRYPTION_KEY=base64.b64encode(os.urandom(32)).decode(),
            MFA_ENFORCED="true",
            APPROVAL_STEP_UP="true",
            RATE_LIMIT="100000/minute",  # one tester drives every account from one address
            UI_ORIGINS="http://127.0.0.1",
            E2E_REPORT_PASSWORD=self.fixture,
            BOOTSTRAP_ADMIN_PASSWORD=self.admin_pw,
        )

    def _py(self, *args: str) -> None:
        cmd = [sys.executable, "-m", *args]
        subprocess.run(cmd, cwd=ROOT, env=self.env, check=True)  # noqa: S603 - our interpreter

    def start(self) -> None:
        if dotenv_value("CASE_DATABASE_URL") or os.environ.get("CASE_DATABASE_URL"):
            raise SystemExit(
                "CASE_DATABASE_URL is set: remove it (MySQL is never used for this test)."
            )
        if not (FROZEN / "hr.db").exists():
            self._py("credassure.datagen", "hr-db")
        self._py("credassure.ledger.migrate", "upgrade", "case", str(self.db))
        self._py("credassure.ledger.seed", str(self.db), "--password-env", "E2E_REPORT_PASSWORD")
        self._py("credassure.ledger.seed", str(self.db), "--bootstrap-admin", "it.admin")
        log = (self.out / "gateway.log").open("wb")
        self.proc = subprocess.Popen(  # noqa: S603 - fixed argv, our own interpreter
            [*UVICORN, "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=ROOT,
            env=self.env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        for _ in range(120):
            try:
                if httpx.get(f"{self.url}/v1/health/live", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            if self.proc.poll() is not None:
                break
            time.sleep(1)
        self.stop()
        raise SystemExit(f"gateway did not start; see {self.out / 'gateway.log'}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------- an API client per person


class Api:
    """Signs in like the web app (password, first-time password change, authenticator, code)."""

    def __init__(self, url: str, acc: Accounts, live: bool = False) -> None:
        self.acc, self.live = acc, live
        self.role = acc.role
        self.http = httpx.Client(base_url=url, timeout=300)
        self.used: dict[str, int] = {}
        self.sent: list[float] = []  # live: stay under the site's per-user rate limit

    def password(self, user: str) -> str:
        pw = self.acc.pw.get(user) or self.acc.fixture
        if not pw:
            raise RuntimeError(f"no password for {user}: add PW_{user}= to the accounts file")
        return pw

    def code(self, user: str) -> str:
        """A fresh code: never the same 30 s step twice for one user (a code works once)."""
        step = mfa.step_of(time.time())
        if self.used.get(user, -1) >= step:
            time.sleep((step + 1) * 30 - time.time() + 1)
            step = mfa.step_of(time.time())
        self.used[user] = step
        return mfa.totp_at(self.acc.totp[user], step)

    def call(self, method: str, path: str, tok: str | None = None, **kw: Any) -> tuple[int, Any]:
        h = {"Authorization": f"Bearer {tok}"} if tok else {}
        h.update(kw.pop("headers", {}))
        if self.live:  # 90 a minute in all, below the site's 120 per user
            now = time.monotonic()
            self.sent = [t for t in self.sent if now - t < 60]
            if len(self.sent) >= 90:
                time.sleep(60 - (now - self.sent[0]) + 0.5)
            self.sent.append(time.monotonic())
        r = self.http.request(method, path, headers=h, **kw)
        for _ in range(3):
            if r.status_code != 429:
                break
            time.sleep(30)
            r = self.http.request(method, path, headers=h, **kw)
        ct = r.headers.get("content-type", "")
        return r.status_code, (r.json() if "json" in ct and r.content else r.text)

    def token(self, user: str, password: str | None = None) -> tuple[int, dict[str, Any]]:
        s, b = self.call(
            "POST",
            "/v1/auth/token",
            json={"username": user, "password": password or self.password(user)},
        )
        return s, b if isinstance(b, dict) else {}

    def login(self, user: str) -> str:
        s, b = self.token(user)
        if s != 200:
            raise RuntimeError(f"sign-in {user}: {s}")
        for _ in range(4):
            if b.get("stage") == "full":
                return str(b["access_token"])
            tok, nxt = str(b["access_token"]), b.get("next", [])
            if "change_password" in nxt:
                new = "Np-" + secrets.token_urlsafe(16)
                body = {"current_password": self.password(user), "new_password": new}
                if self.call("POST", "/v1/auth/password", tok, json=body)[0] != 200:
                    raise RuntimeError(f"{user}: password change refused")
                self.acc.pw[user] = new
                self.acc.save()
                s, b = self.token(user)
            elif "enrol_mfa" in nxt:
                s, st = self.call(
                    "POST",
                    "/v1/auth/mfa/setup",
                    tok,
                    json={"current_password": self.password(user)},
                )
                self.acc.totp[user] = st["secret"]
                self.acc.save()
                s, b = self.call("POST", "/v1/auth/mfa/enable", tok, json={"code": self.code(user)})
                if s != 200:
                    raise RuntimeError(f"{user}: authenticator set-up refused")
            elif "verify_mfa" in nxt:
                s, b = self.call("POST", "/v1/auth/mfa/verify", tok, json={"code": self.code(user)})
            else:
                raise RuntimeError(f"{user}: unexpected sign-in step {nxt}")
        raise RuntimeError(f"{user}: sign-in did not finish")


# ---------------------------------------------------------------- case helpers


def new_case_fields(folder: str) -> dict[str, Any]:
    md = (PACK / folder / "manual-entry.md").read_text(encoding="utf-8")

    def cell(label: str) -> str:
        m = re.search(rf"\| {label} \| ([^|]+) \|", md)
        if not m:
            raise ValueError(f"{folder}: {label} not in manual-entry.md")
        return m.group(1).strip()

    def paise(text: str) -> int:
        return int(text.replace(",", "")) * 100

    return {
        "msme_name": cell("MSME legal name").replace("Manual test", "E2E test"),
        "order_ref": cell("PO reference"),
        "order_value_paise": paise(cell("Order value")),
        "indicative_amount_paise": paise(cell("Requested amount")),
        "due_date": "2027-05-15",
    }


def lender_names(folder: str) -> dict[str, str]:
    out = {}
    for f in glob.glob(str(PACK / folder / "lender-files" / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        out[d["offer_id"]] = str(d.get("lender_name", "?")).replace(" (synthetic)", "")
    return out


class Cases:
    def __init__(self, api: Api) -> None:
        self.api = api

    def create(self, tok: str, folder: str, lender_files: bool = True) -> tuple[str, list[str]]:
        s, c = self.api.call("POST", "/v1/cases", tok, json=new_case_fields(folder))
        if s != 201:
            raise RuntimeError(f"create case: {s} {c}")
        cid = str(c["case_id"])
        wb = next((PACK / folder).glob("case-data-*.xlsx"))
        s, w = self.api.call(
            "POST",
            f"/v1/cases/{cid}/workbook",
            tok,
            files={"file": (wb.name, wb.read_bytes(), XLSX_MIME)},
        )
        if s not in (200, 201):
            raise RuntimeError(f"workbook: {s} {w}")
        flags: list[str] = []
        if lender_files:
            files = sorted((PACK / folder / "lender-files").iterdir())
            for f in [x for x in files if x.suffix == ".json"] + [
                x for x in files if x.suffix == ".md"
            ]:
                kind = "offer" if f.suffix == ".json" else "kfs"
                mime = "application/json" if kind == "offer" else "text/markdown"
                s, r = self.upload(tok, cid, kind, f.name, f.read_bytes(), mime)
                if s >= 300:
                    raise RuntimeError(f"upload {f.name}: {s} {r}")
                if isinstance(r, dict) and r.get("injection_flags"):
                    flags.append(f"{f.name}: {', '.join(r['injection_flags'])}")
        return cid, flags

    def upload(
        self, tok: str, cid: str, kind: str, name: str, data: bytes, mime: str
    ) -> tuple[int, Any]:
        return self.api.call(
            "POST",
            f"/v1/cases/{cid}/files",
            tok,
            params={"kind": kind},
            files={"file": (name, data, mime)},
        )

    def run(self, tok: str, cid: str) -> dict[str, Any]:
        key = f"e2e-{cid}-{time.time_ns()}"
        s, j = self.api.call("POST", f"/v1/cases/{cid}/run", tok, headers={"Idempotency-Key": key})
        if s != 202:
            raise RuntimeError(f"run: {s} {j}")
        for _ in range(900):
            s, st = self.api.call("GET", f"/v1/jobs/{j['job_id']}", tok)
            if st.get("status") in ("succeeded", "failed", "cancelled", "error"):
                return dict(st)
            time.sleep(2 if self.api.live else 1)
        raise TimeoutError(f"job {j['job_id']}")

    def get(self, tok: str, cid: str) -> dict[str, Any]:
        return dict(self.api.call("GET", f"/v1/cases/{cid}", tok)[1])

    def offers(self, tok: str, cid: str) -> dict[str, Any]:
        o = self.api.call("GET", f"/v1/cases/{cid}/offers", tok)[1]
        return o if isinstance(o, dict) else {}

    @staticmethod
    def stage(c: dict[str, Any], name: str) -> dict[str, Any]:
        return next((s for s in c.get("stages", []) if s["stage"] == name), {})

    def decide(self, tok: str, cid: str, decision: str, **kw: Any) -> tuple[int, Any]:
        _, ib = self.api.call("GET", f"/v1/cases/{cid}/inbox", tok)
        ib = ib if isinstance(ib, dict) else {}
        body = {
            "decision": decision,
            "expected_version": ib.get("row_version", 0),
            "comment": "E2E test",
        }
        if decision == "approve":
            body |= {"attested": True, "report_version": ib.get("report_version")}
        body |= kw
        return self.api.call("POST", f"/v1/cases/{cid}/decision", tok, json=body)

    def history(self, tok: str, cid: str) -> str:
        return json.dumps(
            self.api.call("GET", f"/v1/cases/{cid}/history", tok)[1], ensure_ascii=False
        )


# ---------------------------------------------------------------- the suites

SCENARIOS: dict[str, dict[str, Any]] = {  # docs/setup/e2e-testing.md part 9
    "01-director-route": {
        "need": 14200000,
        "route": "director_finance",
        "status": "AWAITING_APPROVAL",
        "rank": ["Brahmaputra Industrial Bank", "Aravali Commercial Bank"],
    },
    "02-vp-route-negotiation": {
        "need": 17500000,
        "route": "vp_finance",
        "status": "AWAITING_APPROVAL",
        "rank": ["Aravali Commercial Bank", "Falgu Merchant Bank"],
    },
    "03-held-exactly-1-5-crore": {"need": 15000000, "status": "HELD"},
    "04-missing-schedule-question": {"need": 11000000, "asks": "lendwise"},
    "05-missing-case-data-question": {"asks": "working_capital"},
    "06-conflicting-case-data": {"asks": "working_capital"},
    "07-not-enough-affordable-offers": {"need": 14800000, "blocked": True},
    "08-no-loan-needed": {"need": 0, "route": "director_finance", "status": "AWAITING_APPROVAL"},
    "09-injection-in-lender-document": {"need": 6200000, "blocked": True, "flags": True},
    "10-wrong-case-document": {
        "need": 14200000,
        "route": "director_finance",
        "status": "AWAITING_APPROVAL",
        "rank": ["Brahmaputra Industrial Bank", "Aravali Commercial Bank"],
        "mismatch": True,
    },
}


def describe(e: dict[str, Any]) -> str:
    parts = []
    if "need" in e:
        parts.append(f"need {rupees(e['need'] * 100)}")
    if "route" in e:
        parts.append(f"routed to {e['route']}")
    if "status" in e:
        parts.append(f"status {e['status']}")
    if "rank" in e:
        parts.append("ranked " + " > ".join(e["rank"]))
    if "asks" in e:
        parts.append(f"{e['asks']} stops with a question")
    if e.get("blocked"):
        parts.append("lender comparison blocked")
    if e.get("flags"):
        parts.append("hidden instructions flagged and ignored")
    if e.get("mismatch"):
        parts.append("KFS naming another case flagged")
    return "; ".join(parts)


def scenarios(run: Run, api: Api, cs: Cases) -> None:
    area = "Test-pack scenarios"
    tok = api.login(api.role["preparer"])
    for folder, e in SCENARIOS.items():

        def one(folder: str = folder, e: dict[str, Any] = e) -> None:
            cid, flags = cs.create(tok, folder)
            run.cases[folder] = cid
            cs.run(tok, cid)
            c, o = cs.get(tok, cid), cs.offers(tok, cid)
            names = lender_names(folder)
            rank = [names.get(x, x) for x in (o.get("ranking") or [])]
            need = (c.get("recommended_amount") or {}).get("paise")
            ok = True
            if "need" in e:
                ok &= need == e["need"] * 100
            if "route" in e:
                ok &= c.get("route") == e["route"]
            if "status" in e:
                ok &= c["status"] == e["status"]
            if "rank" in e:
                ok &= rank == e["rank"]
            act = f"status {c['status']}, route {c.get('route')}, need {rupees(need)}"
            act += f", ranked {rank or '—'}"
            if "asks" in e:
                q = cs.stage(c, e["asks"]).get("question")
                ok &= bool(q)
                act += f"; question: {q}"
            if e.get("blocked"):
                ok &= o.get("gate") == "NO_GO"
                act += f"; lender gate {o.get('gate')}"
            if e.get("flags"):
                ok &= bool(flags)
            if e.get("mismatch"):
                ok &= any("KFS_CASE_MISMATCH" in f for f in flags)
            if flags:
                act += "; upload flags: " + " | ".join(flags)
            run.add(area, folder, describe(e), act, ok, case=cid)

        run.guard(area, folder, one)


def question_cards(run: Run, api: Api, cs: Cases) -> None:
    area = "Question cards"
    tok = api.login(api.role["preparer"])
    receipts = (
        "week,source,amount,confirmed\n1,order_advance,5120000,true\n4,other_customer,1338000,false\n"
        "7,other_customer,1057000,false\n9,order_milestone,6144000,true\n12,order_milestone,8192000,true\n"
        "15,order_milestone,6144000,true\n"
    )
    receivables = (
        "invoice_id,customer,amount,due_week,expected_week\n"
        "INV-14-001,Other Customer 1,644000,7,8\n"
        "INV-14-002,Other Customer 2,897000,20,20\nINV-14-003,Other Customer 3,433000,3,5\n"
        "INV-14-004,Other Customer 4,927000,15,15\n"
    )
    opening = json.loads((FROZEN / "cases" / "CA-2026-0013" / "opening_position.json").read_text())
    opening["min_cash_buffer"] = 1000000
    sch = PACK / "04-missing-schedule-question" / "answer-the-question" / "KFS-OF-02-B-v1-SCH.md"
    answers: dict[str, tuple[list[tuple[str, str, bytes, str]], str, str]] = {
        "04-missing-schedule-question": (
            [("kfs", sch.name, sch.read_bytes(), "text/markdown")],
            "AWAITING_APPROVAL",
            "the schedule of charges from answer-the-question/ is added; on to approval",
        ),
        "05-missing-case-data-question": (
            [
                (
                    "opening_position",
                    "opening_position.json",
                    json.dumps(opening).encode(),
                    "application/json",
                )
            ],
            "NO_GO",
            "a ₹10 lakh buffer is added; funding need passes; lender comparison then blocks "
            "(frozen design: no eligible offer for this case)",
        ),
        "06-conflicting-case-data": (
            [
                ("receipts", "receipts.csv", receipts.encode(), "text/csv"),
                ("receivables", "receivables.csv", receivables.encode(), "text/csv"),
            ],
            "AWAITING_APPROVAL",
            "receipts match the order value, duplicate invoice renamed; on to approval",
        ),
    }
    for folder, (files, want, expected) in answers.items():

        def one(
            folder: str = folder, files: Any = files, want: str = want, expected: str = expected
        ) -> None:
            cid = run.cases[folder]
            codes = [cs.upload(tok, cid, k, n, d, m)[0] for k, n, d, m in files]
            cs.run(tok, cid)
            c = cs.get(tok, cid)
            need = (c.get("recommended_amount") or {}).get("paise")
            gate = cs.offers(tok, cid).get("gate")
            got = c["status"] if want != "NO_GO" else gate
            act = f"uploads {codes}; status {c['status']}, need {rupees(need)}, lender gate {gate}"
            ok = all(x < 300 for x in codes) and got == want
            if want == "NO_GO":
                ok &= cs.stage(c, "working_capital").get("decision") == "GO"
            run.add(area, f"{folder}: answer the card, then Continue", expected, act, ok, case=cid)

        run.guard(area, folder, one)


PROFILES = {  # docs/setup/e2e-testing.md part 6
    "prep.e001": ("GO", "passes the preparer check"),
    "prep.e009": ("NO_GO", "blocked: a mandatory training has expired"),
    "prep.e012": ("NEEDS_INPUT", "needs information: a training record is missing"),
    "prep.e014": ("NO_GO", "blocked: role not authorised to prepare proposals"),
    "prep.e017": ("NO_GO", "blocked: policy acknowledgement missing"),
    "prep.e019": ("NO_GO", "blocked: a training is still in progress"),
    "prep.e020": ("NO_GO", "blocked: two failures (expired training, missing acknowledgement)"),
}


def profiles(run: Run, api: Api, cs: Cases) -> None:
    area = "Preparer check (HR profiles)"
    items = list(PROFILES.items())
    if api.live:  # the main preparer is the passing profile; the others only with a password given
        items = [(api.role["preparer"], PROFILES["prep.e001"])] + [
            (u, v) for u, v in items[1:] if u in api.acc.pw
        ]
    for user, (want, expected) in items:

        def one(user: str = user, want: str = want, expected: str = expected) -> None:
            tok = api.login(user)
            cid, _ = cs.create(tok, "01-director-route", lender_files=False)
            cs.run(tok, cid)
            st = cs.stage(cs.get(tok, cid), "onboarding")
            blockers = st.get("blockers") or []
            msgs = [b.get("message", "") for b in blockers]
            who = all("Who fixes it" in (b.get("next_action") or "") for b in blockers)
            ok = st.get("decision") == want and (want == "GO" or (bool(blockers) and who))
            if user == "prep.e020":
                ok &= len(blockers) >= 2
            act = f"preparer check {st.get('decision')}; " + ("; ".join(msgs) or "no blockers")
            if blockers:
                act += f"; says who fixes it: {who}"
            run.add(area, user, expected, act, ok, case=cid)

        run.guard(area, user, one)


def approvals_and_access(run: Run, api: Api, cs: Cases) -> None:
    cmap = run.cases
    vp = api.role["vp"]
    ptok, dtok, vtok = (api.login(api.role[r]) for r in ("preparer", "director", "vp"))
    acc, apr = "Access control", "Approvals"

    def isolation() -> None:
        if "preparer2" not in api.role:
            return
        p2tok = api.login(api.role["preparer2"])
        s, _ = api.call("GET", f"/v1/cases/{cmap['01-director-route']}", p2tok)
        _, lst = api.call("GET", "/v1/cases", p2tok)
        items = lst.get("items", []) if isinstance(lst, dict) else lst
        seen = [x for x in items if x.get("case_id") in cmap.values()]
        run.add(
            acc,
            "a second preparer opens the first one's case",
            "refused, and not listed",
            f"open {s}; {len(seen)} of the first preparer's cases listed",
            s in (403, 404) and not seen,
        )

    def maker_checker() -> None:
        s, r = cs.decide(ptok, cmap["01-director-route"], "approve")
        run.add(
            acc,
            "maker-checker: the preparer approves their own case",
            "refused (403)",
            f"{s} {r.get('detail', '') if isinstance(r, dict) else ''}",
            s == 403,
        )

    def director_scope() -> None:
        _, ib = api.call("GET", "/v1/inbox", dtok)
        ids = [x["case_id"] for x in ib.get("items", [])]
        want = [
            cmap[k] for k in ("01-director-route", "08-no-loan-needed", "10-wrong-case-document")
        ]
        other = [cmap[k] for k in ("02-vp-route-negotiation", "03-held-exactly-1-5-crore")]
        s1, _ = api.call("GET", f"/v1/cases/{cmap['02-vp-route-negotiation']}", dtok)
        s2, _ = cs.decide(dtok, cmap["03-held-exactly-1-5-crore"], "approve")
        ok = all(w in ids for w in want) and not any(o in ids for o in other) and s1 in (403, 404)
        run.add(
            acc,
            "Director sees only Director-routed cases",
            "Director cases listed; VP and held cases not listed, not open, not decidable",
            f"inbox {len(ids)} cases; VP case open {s1}; decide held case {s2}",
            ok and s2 in (403, 404),
        )

    for name, fn in (
        ("isolation", isolation),
        ("maker-checker", maker_checker),
        ("scope", director_scope),
    ):
        run.guard(acc, name, fn)

    def director() -> None:
        cid = cmap["01-director-route"]
        s, _ = cs.decide(dtok, cid, "approve", attested=False)
        run.add(
            apr,
            "approve without ticking the review box",
            "refused (422)",
            str(s),
            s == 422,
            case=cid,
        )
        s, _ = cs.decide(dtok, cid, "approve", comment="Approved in the E2E report run")
        st = cs.get(ptok, cid)["status"]
        run.add(
            apr,
            "Director approves scenario 01 (below ₹1.5 crore: no password or code)",
            "APPROVED",
            f"{s}; status {st}",
            s == 200 and st == "APPROVED",
            case=cid,
        )
        s, _ = cs.decide(dtok, cid, "approve")
        run.add(
            apr, "decide the same case twice", "refused", str(s), s in (403, 409, 422), case=cid
        )
        cid = cmap["08-no-loan-needed"]
        s, _ = cs.decide(dtok, cid, "approve", comment="No new facility needed")
        st = cs.get(ptok, cid)["status"]
        run.add(
            apr,
            "Director approves scenario 08 (₹0 need: confirms no new facility)",
            "APPROVED",
            f"{s}; status {st}",
            s == 200 and st == "APPROVED",
            case=cid,
        )
        cid = cmap["10-wrong-case-document"]
        s, _ = cs.decide(
            dtok,
            cid,
            "return",
            return_stage="lendwise",
            comment="Replace the KFS naming another case",
        )
        c = cs.get(ptok, cid)
        seen = "Replace the KFS" in cs.history(ptok, cid)
        run.add(
            apr,
            "Director returns scenario 10 to the lender stage",
            "RETURNED; the preparer sees the comment; that stage reopens",
            f"{s}; status {c['status']}, stage {c.get('current_stage')}; comment in history {seen}",
            s == 200 and c["status"] == "RETURNED" and seen,
            case=cid,
        )
        cid = cmap["04-missing-schedule-question"]
        s, _ = cs.decide(dtok, cid, "reject", comment="Rejected in the E2E run: cost too high")
        st, seen = cs.get(ptok, cid)["status"], "cost too high" in cs.history(ptok, cid)
        run.add(
            apr,
            "Director rejects with a reason",
            "REJECTED; reason in history",
            f"{s}; status {st}; reason in history {seen}",
            s == 200 and st == "REJECTED" and seen,
            case=cid,
        )

    def vp_decisions() -> None:
        cid, names = cmap["02-vp-route-negotiation"], lender_names("02-vp-route-negotiation")
        s, _ = api.call("POST", f"/v1/agents/lendwise/cases/{cid}/negotiate", ptok)
        rank = [names.get(x, x) for x in (cs.offers(ptok, cid).get("ranking") or [])]
        run.add(
            apr,
            "negotiation round 1 (fee waiver) on scenario 02",
            "Falgu Merchant Bank moves to first",
            f"{s}; ranked {rank}",
            s in (200, 202) and rank[:1] == ["Falgu Merchant Bank"],
            case=cid,
        )
        _, ib = api.call("GET", f"/v1/cases/{cid}/inbox", vtok)
        s, r = cs.decide(vtok, cid, "approve", password=api.password(vp), mfa_code=api.code(vp))
        code = r.get("code") if isinstance(r, dict) else ""
        run.add(
            apr,
            "VP approves while the report is stale",
            "refused: report stale",
            f"inbox warnings {ib.get('warnings')}; approve {s} {code}",
            s == 409 and code == "REPORT_STALE",
            case=cid,
        )
        api.call("POST", f"/v1/cases/{cid}/report", ptok)
        s1, r1 = cs.decide(vtok, cid, "approve", password=api.password(vp), mfa_code="000000")
        s0, _ = cs.decide(vtok, cid, "approve")
        run.add(
            apr,
            "VP approves above ₹1.5 crore with a wrong code, then with no password",
            "both refused",
            f"wrong code {s1} {r1.get('code') if isinstance(r1, dict) else ''}; no password {s0}",
            s1 in (401, 403) and s0 in (401, 403, 422),
            case=cid,
        )
        s, _ = cs.decide(vtok, cid, "approve", password=api.password(vp), mfa_code=api.code(vp))
        st = cs.get(ptok, cid)["status"]
        run.add(
            apr,
            "VP approves after the report is regenerated (password + fresh code)",
            "APPROVED",
            f"{s}; status {st}",
            s == 200 and st == "APPROVED",
            case=cid,
        )
        cid = cmap["03-held-exactly-1-5-crore"]
        s, _ = cs.decide(vtok, cid, "approve", password=api.password(vp), mfa_code=api.code(vp))
        st = cs.get(ptok, cid)["status"]
        run.add(
            apr,
            "VP decides the case held at exactly ₹1.5 crore",
            "APPROVED by the VP",
            f"{s}; status {st}",
            s == 200 and st == "APPROVED",
            case=cid,
        )

    run.guard(apr, "Director decisions", director)
    run.guard(apr, "VP decisions", vp_decisions)


def evaluator(run: Run, api: Api, cs: Cases) -> None:
    area, cmap = "Evaluator", run.cases
    etok = api.login(api.role["evaluator"])
    s, lst = api.call("GET", "/v1/cases", etok)
    items = lst.get("items", []) if isinstance(lst, dict) else lst
    s1, sf = api.call("GET", f"/v1/cases/{cmap['09-injection-in-lender-document']}/safety", etok)
    flagged = (sf.get("counts") or {}).get("injection_flagged") if isinstance(sf, dict) else None
    run.add(
        area,
        "reads every case and the safety panel",
        "every case listed; safety events readable",
        f"{len(items)} cases listed ({s}); safety {s1}, injection flags {flagged}",
        s == 200 and len(items) >= len(cmap) and s1 == 200 and bool(flagged),
    )
    s3, _ = api.call("POST", "/v1/cases", etok, json=new_case_fields("01-director-route"))
    s4, _ = cs.decide(etok, cmap["10-wrong-case-document"], "reject")
    s5, _ = api.call(
        "POST",
        f"/v1/cases/{cmap['10-wrong-case-document']}/run",
        etok,
        headers={"Idempotency-Key": "ev"},
    )
    run.add(
        area,
        "tries to create, decide and run",
        "all refused",
        f"create {s3}, decide {s4}, run {s5}",
        all(x in (403, 404) for x in (s3, s4, s5)),
    )
    bad = []
    for cid in cmap.values():
        s, a = api.call("GET", f"/v1/cases/{cid}/audit", etok)
        if s != 200 or not (isinstance(a, dict) and a.get("chain_ok")):
            bad.append(f"{cid}: {s}")
    run.add(
        area,
        "audit hash chain on every scenario case",
        "verified",
        f"{len(cmap)} cases; problems {bad or 'none'}",
        not bad,
    )


def admin(run: Run, api: Api) -> None:
    area = "Account admin"
    adm, vp = api.role["admin"], api.role["vp"]
    tag = datetime.now(UTC).strftime("%m%d%H%M%S")
    newp, taken = f"e2e.tmp{tag}", f"e2e.taken{tag}"
    atok = api.login(adm)
    run.add(
        area,
        "it.admin first sign-in",
        "new password and authenticator set up, then signed in",
        f"authenticator linked {adm in api.acc.totp}",
        adm in api.acc.totp,
    )
    s, r = api.call(
        "POST",
        "/v1/admin/users",
        atok,
        json={"username": taken, "display_name": "E2E", "role": "preparer", "emp_id": "E003"},
    )
    run.add(
        area,
        "account for an HR id already in use",
        "refused (one account per HR employee)",
        f"{s} {r.get('detail', '') if isinstance(r, dict) else ''}",
        s == 409,
    )
    s, r = api.call(
        "POST",
        "/v1/admin/users",
        atok,
        json={"username": newp, "display_name": "E2E New Preparer", "role": "preparer"},
    )
    _, us = api.call("GET", "/v1/admin/users", atok)
    ids = {
        u["username"]: u["user_id"] for u in (us.get("items", us) if isinstance(us, dict) else us)
    }
    s2, rp = api.call("POST", f"/v1/admin/users/{ids[newp]}/reset-password", atok)
    tmp = next((v for k, v in rp.items() if "password" in k), "") if isinstance(rp, dict) else ""
    s3, b = api.token(newp, tmp)
    run.add(
        area,
        "create a preparer; reset its password",
        "temporary password shown once; it forces a new one",
        f"create {s}; reset {s2}; sign-in {s3}, next {b.get('next')}",
        s == 201 and s2 == 200 and s3 == 200 and "change_password" in b.get("next", []),
    )
    api.acc.pw[newp] = tmp
    api.login(newp)
    new_pw = api.acc.pw.pop(newp, tmp)  # the password it changed to; not kept in the file
    s, _ = api.call("POST", f"/v1/admin/users/{ids[vp]}/reset-mfa", atok)
    _, b = api.token(vp)
    run.add(
        area,
        "lost phone: reset two-step verification for demo.vp",
        "the VP sets up the authenticator again",
        f"{s}; next sign-in asks {b.get('next')}",
        s == 200 and "enrol_mfa" in b.get("next", []),
    )
    api.acc.totp.pop(vp, None)
    api.login(vp)
    s1, _ = api.call("GET", f"/v1/cases/{next(iter(run.cases.values()))}", atok)
    s2, _ = api.call("GET", "/v1/cases", atok)
    run.add(
        area,
        "admin opens a case",
        "refused (an admin never opens a case)",
        f"case {s1}; list {s2}",
        s1 in (403, 404) and s2 in (403, 404),
    )
    s, _ = api.call("POST", f"/v1/admin/users/{ids[newp]}/disable", atok)
    s2, _ = api.token(newp, new_pw)
    run.add(
        area,
        "disable an account",
        "sign-in refused",
        f"disable {s}; sign-in {s2}",
        s == 200 and s2 == 401,
    )
    _, ev = api.call("GET", "/v1/admin/users/events", atok)
    kinds = sorted(
        {e.get("event_type", "") for e in (ev.get("items", ev) if isinstance(ev, dict) else ev)}
    )
    need = {
        "USER_CREATED",
        "PASSWORD_RESET",
        "MFA_RESET",
        "USER_DISABLED",
        "MFA_ENROLLED",
        "PASSWORD_CHANGED",
    }
    run.add(
        area,
        "user log records account events",
        ", ".join(sorted(need)),
        ", ".join(kinds),
        need <= set(kinds),
    )


def sessions(run: Run, api: Api) -> None:
    area = "Sign-in and sessions"
    s, _ = api.token(api.role["preparer"], "wrong-password-123")
    run.add(area, "wrong password", "refused (401)", str(s), s == 401)
    tok = api.login(api.role.get("preparer2", api.role["preparer"]))
    s1, _ = api.call("POST", "/v1/auth/logout", tok)
    s2, _ = api.call("GET", "/v1/cases", tok)
    run.add(
        area,
        "sign out",
        "the old token is refused",
        f"logout {s1}; reuse {s2}",
        s1 in (200, 204) and s2 == 401,
    )
    _, b = api.token(api.role["director"])
    s3, _ = api.call("GET", "/v1/cases", b.get("access_token"))
    run.add(
        area,
        "Director after the password only",
        "only the code step is open",
        f"stage {b.get('stage')}; cases {s3}",
        b.get("stage") == "mfa" and s3 in (401, 403),
    )
    s4, _ = api.call("GET", "/v1/cases")
    run.add(area, "no token", "refused (401)", str(s4), s4 == 401)


def pdfs(run: Run, api: Api, cs: Cases) -> None:
    area = "Lender PDFs"
    tok = api.login(api.role["preparer"])
    cid, _ = cs.create(tok, "01-director-route", lender_files=False)
    res = []
    for f in sorted((PACK / "01-director-route" / "lender-pdfs").glob("*.pdf")):
        doc = "offer" if "offer letter" in f.name else "schedule" if "schedule" in f.name else "kfs"
        s, r = api.call(
            "POST",
            f"/v1/cases/{cid}/pdf",
            tok,
            params={"doc": doc},
            files={"file": (f.name, f.read_bytes(), "application/pdf")},
        )
        res.append((f.name, s, len(r.get("text", "")) if isinstance(r, dict) else 0))
    run.add(
        area,
        "read the 9 PDFs of scenario 01 (offer letters, KFS, schedules)",
        "each read (200) with its text; nothing stored",
        "; ".join(f"{n.split(' OF-')[-1]}: {s}, {k} chars" for n, s, k in res),
        len(res) == 9 and all(s == 200 and k > 200 for _, s, k in res),
        case=cid,
    )
    s, r = api.call(
        "POST",
        f"/v1/cases/{cid}/pdf",
        tok,
        params={"doc": "kfs"},
        files={"file": ("not-a.pdf", b"plain text", "application/pdf")},
    )
    run.add(
        area,
        "a file that is not a PDF",
        "refused with a plain message",
        f"{s} {r.get('detail', '') if isinstance(r, dict) else ''}",
        s in (400, 415, 422),
    )


def smoke(run: Run, url: str) -> None:
    """Read only: no sign-in, no data."""
    area = "Deployed site (read only)"
    base = url.rstrip("/")
    for path, want in (("/login/", "page"), ("/v1/health/live", "ok"), ("/v1/health/ready", "ok")):
        try:
            r = httpx.get(base + path, timeout=30, follow_redirects=True)
            body = r.text[:200].replace("\n", " ")
            ok = r.status_code == 200 and (want == "page" or '"ok"' in r.text)
            run.add(
                area,
                f"GET {path}",
                "200" + (", status ok" if want == "ok" else ""),
                f"{r.status_code} {body}",
                ok,
            )
        except httpx.HTTPError as e:
            run.add(area, f"GET {path}", "reachable", f"{type(e).__name__}: {e}", False)


# ---------------------------------------------------------------- report


def write_xlsx(path: Path, run: Run, meta: dict[str, str]) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    bold, head = Font(bold=True, name="Arial"), PatternFill("solid", fgColor="F4F2EC")
    ws.append(["CredAssure end-to-end test report"])
    ws["A1"].font = Font(bold=True, size=14, name="Arial")
    for k, v in meta.items():
        ws.append([k, v])
    ws.append([])
    ws.append(["Area", "Checks", "Passed", "Failed"])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, head
    for a in AREAS:
        rows = [c for c in run.checks if c.area == a]
        if rows:
            ws.append([a, len(rows), sum(c.passed for c in rows), sum(not c.passed for c in rows)])
    n = len(run.checks)
    ws.append(
        ["Total", n, sum(c.passed for c in run.checks), sum(not c.passed for c in run.checks)]
    )
    for c in ws[ws.max_row]:
        c.font = bold
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 34, 60
    rs = wb.create_sheet("Results")
    cols = ["#", "Area", "Test", "Expected", "Actual", "Result", "Case", "Note"]
    rs.append(cols)
    for c in rs[1]:
        c.font, c.fill = bold, head
    red, green = PatternFill("solid", fgColor="FDE2E1"), PatternFill("solid", fgColor="E3F4E8")
    for i, c in enumerate(run.checks, 1):
        rs.append(
            [
                i,
                c.area,
                c.test,
                c.expected,
                c.actual,
                "Pass" if c.passed else "Fail",
                c.case,
                c.note,
            ]
        )
        rs.cell(rs.max_row, 6).fill = green if c.passed else red
    for i, w in enumerate((5, 24, 40, 45, 70, 8, 15, 30), 1):
        rs.column_dimensions[get_column_letter(i)].width = w
    for row in rs.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.font = Font(name="Arial", size=10)
    rs.auto_filter.ref = rs.dimensions
    rs.freeze_panes = "A2"
    wb.save(path)


CSS = """@page{size:A4;margin:14mm 12mm}
body{font-family:Arial,sans-serif;font-size:9.5pt;color:#1b1b1b}h1{font-size:18pt;color:#14213D;margin:0}
h2{font-size:12pt;color:#14213D;border-bottom:1px solid #ddd;margin:14px 0 6px}
.meta td{border:0;padding:1px 8px 1px 0}table{border-collapse:collapse;width:100%;font-size:8.3pt}
th,td{border:1px solid #ddd;padding:3px 5px;vertical-align:top;text-align:left}
th{background:#F4F2EC}
tr{page-break-inside:avoid}.p{color:#17663a;font-weight:bold}.f{color:#b42318;font-weight:bold}
.k{display:flex;gap:8px}.k div{flex:1;border:1px solid #ddd;border-radius:6px;padding:6px}
.k b{font-size:15pt;display:block}"""


def write_html(path: Path, run: Run, meta: dict[str, str]) -> None:
    esc = html.escape
    n, ok = len(run.checks), sum(c.passed for c in run.checks)
    out = [
        "<!doctype html><meta charset=utf-8><title>CredAssure E2E report</title>"
        f"<style>{CSS}</style>"
    ]
    out.append("<h1>CredAssure end-to-end test report</h1><table class=meta>")
    out += [f"<tr><td><b>{esc(k)}</b></td><td>{esc(v)}</td></tr>" for k, v in meta.items()]
    out.append(f"</table><div class=k><div><b>{ok} / {n}</b>checks passed</div>")
    out.append(f"<div><b class={'p' if ok == n else 'f'}>{n - ok}</b>failed</div></div>")
    fails = [c for c in run.checks if not c.passed]
    if fails:
        out.append(
            "<h2>Failures</h2><table><tr><th>Area</th><th>Test</th><th>Expected</th><th>Actual</th></tr>"
        )
        out += [
            f"<tr><td>{esc(c.area)}</td><td>{esc(c.test)}</td><td>{esc(c.expected)}</td><td>{esc(c.actual)}</td></tr>"
            for c in fails
        ]
        out.append("</table>")
    for a in AREAS:
        rows = [c for c in run.checks if c.area == a]
        if not rows:
            continue
        out.append(f"<h2>{esc(a)} — {sum(c.passed for c in rows)}/{len(rows)}</h2>")
        out.append(
            "<table><tr><th style='width:24%'>Test</th><th style='width:27%'>Expected</th>"
            "<th>Actual</th><th style='width:6%'></th></tr>"
        )
        for c in rows:
            case = f"<br><small>{esc(c.case)}</small>" if c.case else ""
            note = f"<br><small>{esc(c.note)}</small>" if c.note else ""
            out.append(
                f"<tr><td>{esc(c.test)}{case}</td><td>{esc(c.expected)}</td><td>{esc(c.actual)}{note}</td>"
                f"<td class={'p' if c.passed else 'f'}>{'Pass' if c.passed else 'Fail'}</td></tr>"
            )
        out.append("</table>")
    path.write_text("\n".join(out), encoding="utf-8")


def write_pdf(html_path: Path, pdf_path: Path) -> str:
    """Print the HTML with Playwright's Chromium (the web app's dev dependency)."""
    node = shutil.which("node")
    script = ROOT / "scripts" / "e2e_report_pdf.cjs"
    if not node or not (ROOT / "node_modules" / "@playwright" / "test").exists():
        return "PDF skipped: run npm ci (Playwright) to get the PDF; the HTML and Excel are written"
    r = subprocess.run(  # noqa: S603 - fixed argv
        [node, str(script), str(html_path), str(pdf_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return "PDF written" if r.returncode == 0 else f"PDF skipped: {r.stderr.strip()[-300:]}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--out", type=Path, default=None, help="report folder (default var/e2e-report/<time>)"
    )
    ap.add_argument(
        "--smoke-url", default="", help="also check a deployed site, read only (no sign-in)"
    )
    ap.add_argument(
        "--live",
        type=Path,
        default=None,
        metavar="ACCOUNTS_FILE",
        help="run every check ON A DEPLOYED SITE, as the accounts in this file (BASE_URL=..., "
        "ROLE_<role>=<username>, PW_<username>=...); creates 'E2E test (synthetic)' cases there",
    )
    ap.add_argument("--yes", action="store_true", help="with --live: do not ask before starting")
    a = ap.parse_args(argv)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = a.out or ROOT / "var" / "e2e-report" / stamp
    out.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> str:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)  # noqa: S603,S607
        return r.stdout.strip()

    run, gw, acc = Run(), None, None
    if a.live:
        acc = Accounts.load(a.live)
        local = acc.base_url.startswith(("http://127.0.0.1", "http://localhost"))
        if not (acc.base_url.startswith("https://") or local):
            raise SystemExit(f"{a.live}: set BASE_URL=https://<site>")
        print(
            f"LIVE run on {acc.base_url} as {', '.join(f'{k}={v}' for k, v in acc.role.items())}."
        )
        print("It creates 'E2E test (synthetic)' cases there and decides them.")
        if not a.yes and input(f"Type {acc.base_url.split('//')[1]} to go on: ").strip() not in (
            acc.base_url.split("//")[1],
            acc.base_url.split("//")[1].rstrip("/"),
        ):
            raise SystemExit("stopped: nothing was sent")
        r = httpx.get(f"{acc.base_url.rstrip('/')}/v1/health/live", timeout=30)
        if r.status_code != 200:
            raise SystemExit(f"{acc.base_url} is not answering ({r.status_code})")
    else:
        gw = Gateway(out)
        acc = Accounts(role=dict(LOCAL_ROLES), pw={"it.admin": gw.admin_pw}, fixture=gw.fixture)
    t0 = time.monotonic()
    if gw:
        gw.start()
    try:
        url = gw.url if gw else acc.base_url.rstrip("/")
        api = Api(url, acc, live=bool(a.live))
        cs = Cases(api)
        scenarios(run, api, cs)
        question_cards(run, api, cs)
        profiles(run, api, cs)
        approvals_and_access(run, api, cs)
        run.guard("Evaluator", "evaluator", lambda: evaluator(run, api, cs))
        if "admin" in api.role:
            run.guard("Account admin", "admin", lambda: admin(run, api))
        run.guard("Sign-in and sessions", "sessions", lambda: sessions(run, api))
        run.guard("Lender PDFs", "pdfs", lambda: pdfs(run, api, cs))
    finally:
        if gw:
            gw.stop()
    smoke_url = a.smoke_url or (acc.base_url if a.live else "")
    if smoke_url:
        smoke(run, smoke_url)
    n, ok = len(run.checks), sum(c.passed for c in run.checks)
    code_ref = (
        f"{git('branch', '--show-current') or 'detached'} @ {git('rev-parse', '--short', 'HEAD')}"
    )
    meta = {
        "Run": datetime.now(UTC).astimezone().strftime("%d %b %Y %H:%M %Z"),
        "Code": code_ref,
        "Set-up": (
            f"LIVE site {acc.base_url}; accounts "
            + ", ".join(f"{k}={v}" for k, v in acc.role.items())
            if a.live
            else "private gateway on 127.0.0.1, fresh synthetic database, MFA on, model off"
        ),
        "Covered": "10 test-pack scenarios, 3 question cards, 7 HR profiles, approvals, step-up, "
        "access control, evaluator, account admin, sessions, lender PDFs",
        "Not covered": "Ask CredAssure and PDF figure drafting (model and search index needed); "
        "browser layout",
        "Deployed site": (
            f"{acc.base_url}: every check above ran on it, plus its health checks"
            if a.live
            else (f"{a.smoke_url}: read-only health checks" if a.smoke_url else "not checked")
        ),
        "Result": f"{ok} of {n} checks passed in {round(time.monotonic() - t0)} s",
    }
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    (out / "results.json").write_text(
        json.dumps(
            {"meta": meta, "checks": [asdict(c) for c in run.checks]}, indent=1, ensure_ascii=False
        )
    )
    xlsx, htm = out / f"CredAssure_E2E_Report_{day}.xlsx", out / f"CredAssure_E2E_Report_{day}.html"
    write_xlsx(xlsx, run, meta)
    write_html(htm, run, meta)
    pdf_note = write_pdf(htm, out / f"CredAssure_E2E_Report_{day}.pdf")
    print(f"\n{ok}/{n} passed. Report: {out}\n{pdf_note}")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
