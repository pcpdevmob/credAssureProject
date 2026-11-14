// Gateway base URL (/v1 routes). Auth: "bridge" = finbridge auth service (MFA) hands out a gateway token;
// anything else = sign in directly with a gateway account (dev/test profile, no MFA).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
export const AUTH_LIVE = process.env.NEXT_PUBLIC_AUTH_MODE === 'bridge';
