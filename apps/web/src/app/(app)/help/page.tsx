// U5 help centre: docs/help/*.md read at build time (static export), rendered without HTML strings (lib/markdown).
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { PageHeader } from '@/components/PageHeader';
import { Card } from '@/components/ui';
import { Markdown } from '@/lib/markdown';

const DIR = join(process.cwd(), '..', '..', 'docs', 'help');
const ORDER = ['getting-started', 'preparer', 'approver', 'evaluator', 'ask-credassure', 'ai-safety', 'case-authoring', 'error-messages', 'faq', 'glossary'];

function pages() {
  const names = readdirSync(DIR).filter(f => f.endsWith('.md')).map(f => f.slice(0, -3));
  names.sort((a, b) => (ORDER.indexOf(a) + 1 || 99) - (ORDER.indexOf(b) + 1 || 99));
  return names.map(id => {
    const source = readFileSync(join(DIR, `${id}.md`), 'utf8');
    const title = /^#\s+(.*)$/m.exec(source)?.[1] ?? id;
    return { id, title, body: source.replace(/^#\s+.*$/m, '') };
  });
}

export default function Help() {
  const all = pages();
  return (<>
    <PageHeader title="Help centre" sub="Guides for each role, the error reference and the glossary" />
    <div className="grid gap-6 lg:grid-cols-4">
      <nav aria-label="Help pages" className="lg:col-span-1"><Card className="p-3"><ul className="space-y-1 text-sm">{all.map(p => <li key={p.id}><a className="block rounded-lg px-3 py-1.5 hover:bg-sunken" href={`#${p.id}`}>{p.title}</a></li>)}</ul></Card></nav>
      <div className="space-y-6 lg:col-span-3">{all.map(p => <Card key={p.id} className="p-5"><section id={p.id} aria-labelledby={`${p.id}-t`}><h2 id={`${p.id}-t`} className="text-xl font-bold">{p.title}</h2><Markdown source={p.body} id={p.id} /></section></Card>)}</div>
    </div>
  </>);
}
