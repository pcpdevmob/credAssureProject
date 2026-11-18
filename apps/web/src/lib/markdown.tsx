// Help centre (U5): a small Markdown subset rendered as React elements, never as HTML strings, so a help page cannot
// inject markup. Headings, paragraphs, bullet and numbered lists, tables, **bold**, `code` and [links](...).
import type { ReactNode } from 'react';

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*]+\*)/g;
  let last = 0; let i = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > last) out.push(text.slice(last, m.index));
    const t = m[0]; const k = `${key}-${i++}`;
    if (t.startsWith('**')) out.push(<b key={k}>{t.slice(2, -2)}</b>);
    else if (t.startsWith('`')) out.push(<code key={k} className="rounded bg-sunken px-1 font-mono text-[0.85em]">{t.slice(1, -1)}</code>);
    else if (t.startsWith('[')) {
      const [, label, href] = /\[([^\]]+)\]\(([^)]+)\)/.exec(t)!;
      const help = /^([\w-]+)\.md(#.*)?$/.exec(href); // links between help pages stay in the help centre
      out.push(help ? <a key={k} className="text-brand-700 underline" href={`/help/#${help[1]}`}>{label}</a> : /^https:\/\//.test(href) ? <a key={k} className="text-brand-700 underline" href={href} rel="noreferrer noopener" target="_blank">{label}</a> : <span key={k}>{label}</span>);
    } else out.push(<i key={k}>{t.slice(1, -1)}</i>);
    last = m.index! + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

const cells = (row: string) => row.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());

export function Markdown({ source, id }: { source: string; id: string }) {
  const lines = source.replace(/\r/g, '').split('\n');
  const blocks: ReactNode[] = [];
  let i = 0; let n = 0;
  const key = () => `${id}-${n++}`;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim() || line.startsWith('<!--')) { i++; continue; }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) { const L = Math.min(h[1].length + 1, 4); const k = key(); const T = `h${L}` as 'h2' | 'h3' | 'h4'; blocks.push(<T key={k} className={L === 2 ? 'mt-6 text-lg font-semibold' : 'mt-4 font-semibold'}>{inline(h[2], k)}</T>); i++; continue; }
    if (line.startsWith('|')) {
      const rows: string[] = []; while (i < lines.length && lines[i].startsWith('|')) rows.push(lines[i++]);
      const [head, , ...body] = rows; const k = key();
      blocks.push(<div key={k} className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{cells(head).map((c, j) => <th key={j} className="border-b border-line px-2 py-1 font-semibold">{inline(c, `${k}h${j}`)}</th>)}</tr></thead>
        <tbody>{body.map((r, ri) => <tr key={ri}>{cells(r).map((c, j) => <td key={j} className="border-b border-line px-2 py-1 align-top">{inline(c, `${k}r${ri}c${j}`)}</td>)}</tr>)}</tbody></table></div>);
      continue;
    }
    const li = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(line);
    if (li) {
      const ordered = /\d/.test(li[1]); const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      const k = key(); const L = ordered ? 'ol' : 'ul';
      blocks.push(<L key={k} className={`mt-2 space-y-1 pl-5 ${ordered ? 'list-decimal' : 'list-disc'}`}>{items.map((t, j) => <li key={j}>{inline(t, `${k}-${j}`)}</li>)}</L>);
      continue;
    }
    if (line.startsWith('```')) { const code: string[] = []; i++; while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]); i++; blocks.push(<pre key={key()} className="mt-3 overflow-x-auto rounded-lg bg-sunken p-3 text-xs">{code.join('\n')}</pre>); continue; }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#|\||\s*([-*]|\d+\.)\s|```)/.test(lines[i])) para.push(lines[i++]);
    const k = key(); blocks.push(<p key={k} className="mt-2 leading-relaxed">{inline(para.join(' '), k)}</p>);
  }
  return <>{blocks}</>;
}
