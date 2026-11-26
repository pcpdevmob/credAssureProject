# CredAssure documentation

## Requirements and design
- [Business requirements (BRD v3.1)](requirements/BRD.md)
- [Architecture](architecture/ARCHITECTURE.md) and [design detail](architecture/design-detail.md)
- [Architecture decision records](adr/README.md)
- Data: [data resources](data/DATA_RESOURCES.md), [data spec](data/DATA_SPEC.md), [corpus sources](data/RESOURCES.md)

## Responsible AI and security
- [System card](SYSTEM_CARD.md) and [model card](security/model-card.md)
- [Threat model](security/threat-model.md) (summary: [THREAT_MODEL.md](THREAT_MODEL.md)), [risk register](security/risk-register.md),
  [OWASP LLM and agentic mapping](security/owasp-asi-mapping.md)
- [Red-team log](redteam_log.md)

## Evaluation
- [Methodology](evaluation/methodology.md), [metrics](evaluation/metrics.md), [how to run](evaluation/how-to-run.md),
  [degradation matrix](evaluation/degradation-matrix.md), [course endpoint](evaluation/course-endpoint.md)
- Results: [`evaluation/reports/`](../evaluation/reports/), headline in the [G4 report](../evaluation/reports/G4-2026-11-24.md)

## Setup and development
- [Prerequisites](setup/prerequisites.md), [local development](setup/local-dev.md), [environment variables](setup/environment.md),
  [commands](setup/commands.md), [accounts and MFA](setup/accounts-and-mfa.md), [troubleshooting](setup/troubleshooting.md)
- [End-to-end testing, `make e2e-report` and the walk-through video](setup/e2e-testing.md)

## Deployment and operations
- [Hosted deployment](deployment/azure.md), [Docker Compose](deployment/compose.md), [environments](deployment/environments.md)
- [Runbook](deployment/RUNBOOK.md), [observability](deployment/observability.md), [backup and restore](deployment/backup-restore.md),
  [release](deployment/release.md)

## Using the app
- [Getting started](help/getting-started.md), [preparer](help/preparer.md), [approver](help/approver.md),
  [evaluator](help/evaluator.md), [Ask CredAssure](help/ask-credassure.md), [case authoring](help/case-authoring.md),
  [AI safety](help/ai-safety.md), [error messages](help/error-messages.md), [FAQ](help/faq.md), [glossary](help/glossary.md)

## Demo and team
- [Demo script](demo/demo-script.md), [demo runbook](demo/demo-runbook.md), [likely questions](demo/qa.md),
  [evidence slide](demo/evidence-slide.md)
- [Contributions](../CONTRIBUTIONS.md) and [contribution map](team/contribution-map.md)
