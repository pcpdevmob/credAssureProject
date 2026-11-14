// The one allowed raw fetch (tests/test_boundaries.py): same-origin calls to the finbridge auth service only (/api/auth, /api/users); cookie session + CSRF header.
export async function http<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, { ...init, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'finbridge', ...(init.headers || {}) } });
  if (!res.ok) { let m = ''; try { m = (await res.json()).error; } catch { /* */ } throw new Error(m || `Request failed (${res.status})`); }
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}
