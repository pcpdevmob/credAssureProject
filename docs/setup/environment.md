# Environment variables

TODO owner: [Name 1].

## Required
| Variable | Used by | Meaning |
|---|---|---|
| `CORPUS_CONTACT_EMAIL` | `make corpus-harvest`, `make corpus-download` | Team contact address in the scripted User-Agent `CredAssure-capstone/1.0 (IIT KGP academic project; contact: <email>)` (ADR 0020). The commands refuse to start without a valid address. Set it in `.env`; never hard-code it. |

## Model
## Tracing
