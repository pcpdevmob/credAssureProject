// Gateway base URL (/v1 routes). Auth: anything but "bridge" = the gateway's own accounts (ADR 0038: sign-in stages,
// TOTP MFA when MFA_ENFORCED, user admin); "bridge" = the old finbridge auth service (deploy/auth) hands out a gateway token.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
export const AUTH_LIVE = process.env.NEXT_PUBLIC_AUTH_MODE === 'bridge';
