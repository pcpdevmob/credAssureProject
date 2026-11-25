"""Contribution map (scope #18): commits and PRs on `main` by module, with each module's owner.

    uv run python scripts/contribution_map.py > docs/team/contribution-map.md

Ownership, not authorship: the owner column says who is responsible for a module (CODEOWNERS,
set 25 Nov 2026); the Git identities column says who committed. Most commits were made from one
machine, so a module's owner may never appear in its history. Read with CONTRIBUTIONS.md, where
each member confirms what they wrote.
"""

import re
import subprocess  # nosec B404 - read-only git commands
from collections import Counter, defaultdict

REF = "origin/main"
NOTE = (
    "**Ownership, not authorship.** *Owner* is who is responsible for the module "
    "(`.github/CODEOWNERS`, set 25 Nov 2026). *Git identities* is who made the commits. Most of "
    "the repository was committed from Pritish's machine (identities `pcpdev`, `Pritish`, and "
    "`Claude` for commits made with Claude Code there), so a module's owner may not appear among "
    "its committers. Where a member wrote code that was committed from that machine, they list it "
    "in their own signed statement in `CONTRIBUTIONS.md`, and Pritish confirms it.\n"
)
FOOT = (
    "\nA commit that touches several modules counts once in each. PRs are found from their merge "
    "commits in the history of `main`; most were merged into `feature/LendWise` and reached `main` "
    "through sync PRs (#31, #48, #51, #54, #56), so those sync PRs appear under many modules."
)

# (module path prefix, owner), most specific first; matches .github/CODEOWNERS and
# docs/build/REPO_STRUCTURE.md.
MODULES: list[tuple[str, str]] = [
    ("agents/onboarding/prototype/", "Mousita"),
    ("agents/onboarding/", "Mousita (0.3.0); Tejas (0.1-0.2)"),
    ("agents/supervisor/", "Abhishek"),
    ("agents/critic/", "Abhishek"),
    ("agents/working-capital/", "Suresh"),
    ("agents/lendwise/", "Pritish"),
    ("agents/copilot/", "Adesh"),
    ("apps/gateway/", "Abhishek"),
    ("apps/web/", "Suresh"),
    ("packages/api-client/", "Suresh"),
    ("packages/engines/", "Suresh (cash flow); Pritish (loan cost)"),
    ("packages/lender-sim/", "Pritish"),
    ("packages/retrieval/", "Adesh, Tejas"),
    ("packages/observability/", "Abhishek, Pritish"),
    ("packages/security/", "Abhishek, Pritish"),
    ("packages/core/", "Abhishek, Pritish"),
    ("packages/guardrails/", "Shared (default owner Pritish)"),
    ("packages/llm/", "Shared (default owner Pritish)"),
    ("packages/ledger/", "Shared (default owner Pritish)"),
    ("packages/tools/", "Shared (default owner Pritish)"),
    ("packages/reports/", "Shared (default owner Pritish)"),
    ("deploy/", "Suresh"),
    ("data/corpus/", "Tejas, Pritish"),
    ("evaluation/testset/", "Tejas"),
    ("evaluation/ablations/", "Abhishek"),
    ("evaluation/", "Shared evaluation (Abhishek, Tejas; harness Pritish)"),
    ("data/", "Shared data (generators, frozen sets)"),
    ("docs/", "Documentation (shared)"),
]


def git(*args: str) -> str:
    cmd = ["git", *args]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout  # noqa: S603  # nosec B603 B607


def module_of(path: str) -> str | None:
    for prefix, _ in MODULES:
        if path.startswith(prefix):
            return prefix
    return None


def main() -> None:
    owner = dict(MODULES)
    commits: dict[str, set[str]] = defaultdict(set)
    idents: dict[str, Counter[str]] = defaultdict(Counter)
    for block in git("log", REF, "--no-merges", "--format=@@%H|%an", "--name-only").split("@@")[1:]:
        head, *files = block.strip().split("\n")
        sha, name = head.split("|", 1)
        for mod in {mod_ for f in files if f and (mod_ := module_of(f))}:
            commits[mod].add(sha)
            idents[mod][name] += 1
    prs: dict[str, set[int]] = defaultdict(set)
    for line in git("log", REF, "--merges", "--format=%H %s").splitlines():
        sha, subject = line.split(" ", 1)
        pr = re.match(r"Merge pull request #(\d+)", subject)
        if not pr:
            continue
        files = git("diff", "--name-only", f"{sha}^1", sha).split()
        for mod in {mm for f in files if (mm := module_of(f))}:
            prs[mod].add(int(pr.group(1)))
    head = git("rev-parse", "--short", REF).strip()
    date = git("log", "-1", "--format=%cs", REF).strip()
    print("# Contribution map: commits and PRs by module\n")
    print(f"Generated from `main` at `{head}` ({date}) by `scripts/contribution_map.py`.\n")
    print(NOTE)
    print("| Module | Owner | Commits | PRs that changed it | Git identities (commits) |")
    print("|---|---|---|---|---|")
    for prefix, _ in MODULES:
        if not commits[prefix]:
            continue
        pr_list = ", ".join(f"#{n}" for n in sorted(prs[prefix])) or "—"
        who = ", ".join(f"{n} ({c})" for n, c in idents[prefix].most_common())
        print(f"| `{prefix}` | {owner[prefix]} | {len(commits[prefix])} | {pr_list} | {who} |")
    print(FOOT)


if __name__ == "__main__":
    main()
