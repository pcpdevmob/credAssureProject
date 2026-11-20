// Gateway base URL (/v1 routes). Sign-in uses the gateway's own accounts (ADR 0038).
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
