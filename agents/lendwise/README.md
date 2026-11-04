# lendwise

Owner: Pritish. Requirement: LW-01.

Gate 3 lender comparison. Never accepts an offer.

Stage runs call `SupervisorPort` on the gateway. This agent does not call any other agent.
The router returns 501 until the agent phase. There is no path that accepts a lender offer.
