// A wrong password on the sign-in page said "not authenticated Sign in again to continue." (25 Nov): say what is wrong.
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';

Object.defineProperty(window, 'matchMedia', { writable: true, value: (q: string) => ({ matches: false, media: q, onchange: null, addListener: () => {}, removeListener: () => {}, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false }) });
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

describe('sign-in message', () => {
  it('says wrong username or password on a refused sign-in, not "sign in again"', async () => {
    server.use(http.post(`${API}/v1/auth/token`, () => HttpResponse.json(
      { type: 'about:blank', title: 'not authenticated', status: 401, code: 'UNAUTHENTICATED', detail: 'not authenticated' },
      { status: 401, headers: { 'content-type': 'application/problem+json' } })));
    const { default: Login } = await import('@/app/login/page');
    render(<Login />);
    await userEvent.type(screen.getByLabelText('Username'), 'prep.e001');
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText(/Wrong username or password/)).toBeTruthy();
    expect(screen.queryByText(/Sign in again to continue/)).toBeNull();
  });
});
