// P9 U5: evaluation scorecard mapping and the help-centre Markdown renderer (no HTML strings).
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { mapScorecard, evaluationService } from '@/services/evaluation';
import { Markdown } from '@/lib/markdown';

describe('U5 scorecard', () => {
  it('maps baseline, full and sorted ablations', () => {
    const s = mapScorecard({ target: 92,
      baseline: { strategy: 's2_cot_vote', passed: 61, total: 100, by_category: { routing: [3, 6] } },
      full: { run: 'r1', model: 'llama3.1:8b', passed: 94, total: 100, by_category: { routing: [6, 6] } },
      ablations: { A3: { run: 'r3', model: 'm', passed: 90, total: 25, by_category: {} }, A1: { run: 'r2', model: 'm', passed: 80, total: 30, by_category: {} }, A2: null } });
    expect(s.baseline?.detail).toBe('s2_cot_vote');
    expect(s.full?.detail).toBe('llama3.1:8b · r1');
    expect(s.ablations.map(a => a.label)).toEqual(['A1', 'A3']);
  });
  it('reads the gateway endpoint', async () => {
    const s = await evaluationService.scorecard();
    expect(s.full).toBeNull();
    expect(s.target).toBe(92);
  });
});

describe('U5 help Markdown', () => {
  it('renders headings, lists, tables and code as elements', () => {
    render(<Markdown id="t" source={'## Steps\n\n1. Log in with `demo.preparer`\n2. Open **Cases**\n\n| Code | Fix |\n|---|---|\n| STALE | Regenerate |'} />);
    expect(screen.getByRole('heading', { name: 'Steps' })).toBeTruthy();
    expect(screen.getByText('demo.preparer').tagName).toBe('CODE');
    expect(screen.getByRole('table')).toBeTruthy();
  });
  it('never turns markup or unsafe links into live elements', () => {
    const { container } = render(<Markdown id="x" source={'<script>alert(1)</script> [bad](javascript:alert(1)) [ok](faq.md#a)'} />);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('a[href^="javascript"]')).toBeNull();
    expect(container.querySelector('a[href="/help/#faq"]')).toBeTruthy();
    expect(container.textContent).toContain('<script>');
  });
});
