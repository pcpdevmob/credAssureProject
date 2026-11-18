# Error messages

When something goes wrong, CredAssure shows a banner with two lines: **what happened** and **how to fix it**. If a file or
form field is the problem, the message appears next to that field and names the row where it can. CredAssure never shows raw
server output or stack traces.

Each error has a stable code (`code` in the API's problem+json body). The web app's mapper (`apps/web/src/lib/problem.ts`)
uses the same table as this page. Keep the two in step.

| Code | You see | How to fix it |
|---|---|---|
| `VALIDATION_FAILED` | The server's description of the problem, with field, row and reason under each affected field | Correct the fields marked below and submit again. |
| `UNAUTHENTICATED` | Your session expired | Sign in again to continue. |
| `FORBIDDEN` | Your role cannot do this | Ask the person this case is routed to. |
| `STEP_UP_REQUIRED` | Approving more than ₹1,50,00,000 needs your password again | Enter your own password in the confirm dialog. Five wrong tries lock it for a minute. |
| `REPORT_STALE` | The report is stale: figures changed after it was made. Regenerate it before approving | The preparer opens the case and chooses Regenerate report (a new version). Reject and return still work. |
| `ATTESTATION_REQUIRED` | Confirm you reviewed the Critic findings and safety events before approving | Tick the box under Your decision (it states AI text is a draft and figures come from the fact ledger), then approve. Reject and return need no tick. |
| `NOT_FOUND` | The case or figure does not exist, or is not visible to you | Check the case ID, or open the case from the cases list. |
| `TOOL_NOT_ALLOWED` | An agent asked for a tool outside its allowlist | Report it to the evaluator. |
| `COLLECTION_NOT_ALLOWED` | A search touched a document collection this case cannot use | Rephrase the question. |
| `CASE_REQUIRED` | The action needs an open case | Open a case first, then try again. |
| `CONFLICT` | Someone changed the case after you opened it | Reload the case and try again. |
| `RUN_IN_PROGRESS` | A stage run is already going for this case | Wait for it to finish. |
| `RATE_LIMITED` | Too many requests in a short time | Wait a minute and try again. |
| `PAYLOAD_TOO_LARGE` | The upload is over 2 MB | Upload a smaller file. |
| `UNSUPPORTED_MEDIA_TYPE` | The file type is not accepted | Upload JSON or CSV (Markdown for KFS documents). |
| `NOT_IMPLEMENTED` | The feature is not available yet | — |
| `INTERNAL_ERROR` | "Something went wrong on the server." (details are never shown) | Try again. If it keeps happening, tell the evaluator and quote the request ID. |

**Cannot reach the CredAssure service.** The browser could not connect, for example because the network is down or the
gateway is stopped. Check your connection and try again.

**Session expired.** Sign-in tokens are kept in memory only. Reloading the page, or waiting until the token expires, takes
you back to the sign-in screen. Sign in again to continue.
