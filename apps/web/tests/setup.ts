import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { handlers } from '@/mocks/handlers';

// Listen at load time, before any test imports lib/gateway: openapi-fetch keeps the `fetch` it sees when the client is
// created, so a later patch would let requests reach a real gateway on :8000.
export const server = setupServer(...handlers);
server.listen({ onUnhandledRequest: 'error' });
afterEach(() => { server.resetHandlers(); cleanup(); });
afterAll(() => server.close());
