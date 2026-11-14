export const PageHeader = ({ title, sub, right }: { title: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode }) => (
  <div className="mb-6 flex flex-wrap items-end justify-between gap-4 animate-fadein">
    <div><h1 className="font-display text-3xl tracking-tight text-ink-950 sm:text-4xl">{typeof title === 'string' && title.includes(' ') ? <><span className="font-light">{title.slice(0, title.lastIndexOf(' '))}</span> <span className="font-semibold">{title.slice(title.lastIndexOf(' ') + 1)}</span></> : <span className="font-semibold">{title}</span>}</h1>{sub && <p className="mt-1.5 text-ink-500">{sub}</p>}</div>{right}
  </div>
);
