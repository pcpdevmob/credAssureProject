'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, Bot, CheckCircle2, ChevronRight, FileSearch, Fingerprint, GitBranch, Handshake, IndianRupee, KeyRound, Landmark, Lock, Menu, PlayCircle, ScrollText, ShieldCheck, Sparkles, Users, X, Scale, Gauge } from 'lucide-react';
import BigTitle from '@/components/fx/BigTitle';

const ease = [0.16, 1, 0.3, 1] as const;
const Reveal = ({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) => {
  const reduce = useReducedMotion();
  return <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-60px' }} transition={{ duration: .7, delay, ease }}>{children}</motion.div>;
};
const H2 = ({ a, b, dark = false, className = '' }: { a: string; b: string; dark?: boolean; className?: string }) => (
  <h2 className={`font-display text-[clamp(2rem,5vw,3.5rem)] font-normal leading-[1.05] tracking-[-.03em] ${className}`}>
    <span className={dark ? 'text-white' : 'text-ink-950'}>{a}</span> <span className={dark ? 'text-ink-400' : 'text-ink-400'}>{b}</span>
  </h2>
);
const NAV = [['#how', 'How it works'], ['#agents', 'Agents'], ['#security', 'Security'], ['#team', 'Team']];

const Tag = ({ children, dark = false }: { children: React.ReactNode; dark?: boolean }) => <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${dark ? 'bg-white/10 text-brand-200' : 'bg-brand-50 text-brand-700 ring-1 ring-brand-100'}`}><i className={`h-1.5 w-1.5 rounded-full ${dark ? 'bg-brand-300' : 'bg-brand-500'}`} />{children}</span>;

function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed inset-x-0 top-0 z-50 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto grid h-16 max-w-[1400px] grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 sm:px-6">
        <nav className="hidden gap-6 text-sm text-ink-600 md:flex">{NAV.map(([h, l]) => <a key={h} href={h} className="hover:text-ink-950">{l}</a>)}</nav>
        <span className="md:hidden" />
        <Link href="/" className="flex items-center gap-2 font-display text-lg font-semibold tracking-[.12em] text-ink-950"><span className="grid h-7 w-7 place-items-center rounded-lg bg-ink-950 text-gold-300"><Landmark className="h-3.5 w-3.5" /></span>FINBRIDGE<span className="text-brand-600">AI</span></Link>
        <div className="flex items-center justify-end gap-2">
          <a href="#demo" className="hidden rounded-full px-3 py-2 text-sm text-ink-600 hover:text-ink-950 sm:inline">Watch demo flow</a>
          <Link href="/login/" className="hidden rounded-full bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800 sm:inline-flex">Sign in</Link>
          <button aria-label="Menu" onClick={() => setOpen(!open)} className="text-ink-900 sm:hidden">{open ? <X /> : <Menu />}</button>
        </div>
      </div>
      {open && <div className="border-t border-line bg-white px-5 py-4 sm:hidden">{NAV.map(([h, l]) => <a key={h} href={h} onClick={() => setOpen(false)} className="block py-2 text-ink-700">{l}</a>)}<Link href="/login/" className="mt-3 block rounded-full bg-ink-950 py-2.5 text-center font-medium text-white">Sign in</Link></div>}
    </header>
  );
}

function TeamBanner() {
  const reduce = useReducedMotion(); const t = 'Team IntelliCore';
  return (
    <div className="mx-auto max-w-[1400px] px-3 pb-8 pt-8 text-center sm:pt-12">
      <motion.p initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .9, ease }} className="text-[clamp(.7rem,2.6vw,1rem)] font-semibold uppercase tracking-[.28em] text-gold-700">Capstone Project · IIT Kharagpur</motion.p>
      <h2 aria-label={t} className="mt-3 whitespace-nowrap font-display text-[clamp(1.85rem,9.6vw,7.5rem)] font-bold leading-[1.05] tracking-[-.035em]">
        {t.split('').map((ch, i) => <span key={i} aria-hidden className={reduce ? 'inline-block' : 'fb-wave'} style={{ ['--i' as string]: i } as React.CSSProperties}><span className="fb-team-grad inline-block" style={{ animationDelay: `${i * 60}ms` }}>{ch === ' ' ? '\u00a0' : ch}</span></span>)}
      </h2>
      <motion.p initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: .5, duration: .9 }} className="mt-3 text-[clamp(.95rem,2.4vw,1.35rem)] text-ink-600">Designed and built by six members of Team IntelliCore.</motion.p>
    </div>
  );
}

function Hero() {
  const reduce = useReducedMotion();
  return (
    <section className="bg-white px-2 pt-16 sm:px-4">
      <TeamBanner />
      <div className="relative mx-auto max-w-[1400px] overflow-hidden rounded-[28px] bg-ink-950 px-5 pb-0 pt-14 text-white sm:rounded-[36px] sm:px-10 sm:pt-20 lg:px-16">
        <div aria-hidden className="pointer-events-none absolute inset-0 [background:radial-gradient(45%_55%_at_15%_0%,color-mix(in_srgb,var(--fb-brand-500)_22%,transparent),transparent_70%),radial-gradient(35%_45%_at_95%_20%,color-mix(in_srgb,var(--fb-gold-400)_10%,transparent),transparent_70%)]" />
        <div className="relative grid gap-8 lg:grid-cols-[1.5fr_1fr] lg:items-end">
          <div>
                        <div><BigTitle className="!text-[clamp(2.3rem,10.5vw,6.5rem)] lg:!text-[clamp(3rem,5.6vw,6.5rem)]" /></div>
            <Reveal delay={.5}><p className="mt-5 max-w-3xl font-display text-[clamp(1.5rem,3.8vw,3rem)] font-light leading-[1.06] tracking-[-.03em]"><span className="text-white">Working capital for MSMEs,</span> <span className="text-ink-400">agentic <span className="inline-grid h-[1em] w-[1em] translate-y-[.12em] place-items-center rounded-full bg-gold-400/15 ring-1 ring-gold-300/40"><IndianRupee className="h-[.6em] w-[.6em] text-gold-300" /></span> and audited <Sparkles className="inline h-[.8em] w-[.8em] -translate-y-[.05em] text-brand-400" /></span></p></Reveal>
          </div>
          <Reveal delay={.7} className="lg:pb-3">
            <p className="max-w-md text-base text-ink-300">Three specialist AI agents size the real funding gap, negotiate with three lenders and route every proposal to a human approver, with GO/NO-GO gates and a full audit trail.</p>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row">
              <Link href="/login/" className="group inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full bg-white px-6 py-3 font-medium text-ink-950 hover:bg-ink-100">Sign in <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></Link>
              <a href="#demo" className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-6 py-3 font-medium text-white ring-1 ring-white/20 hover:bg-white/[.06]"><PlayCircle className="h-5 w-5 text-brand-400" />Watch demo flow</a>
            </div>
          </Reveal>
        </div>
        <Reveal delay={.9}><ProductMock /></Reveal>
        {!reduce && <motion.div aria-hidden className="pointer-events-none absolute bottom-0 left-1/2 h-40 w-[60%] -translate-x-1/2 rounded-full bg-brand-500/20 blur-[90px]" animate={{ opacity: [.4, .8, .4] }} transition={{ duration: 5, repeat: Infinity }} />}
      </div>
    </section>
  );
}

function SideToggle() {
  return <div className="fixed bottom-4 right-4 z-40 hidden rounded-full bg-white p-1 text-xs font-medium shadow-lg ring-1 ring-line sm:flex"><a href="#how" className="rounded-full px-3 py-1.5 text-ink-600 hover:text-ink-950">For MSMEs</a><a href="#demo" className="rounded-full bg-ink-950 px-3 py-1.5 text-white">For approvers</a></div>;
}

function ProductMock() {
  const bars = [38, 52, 46, 70, 62, 88, 74, 96, 81, 68, 58, 44];
  return (
    <div className="relative mx-auto -mb-6 mt-14 max-w-5xl text-left">
      <div className="rounded-t-[28px] bg-gradient-to-b from-white/20 to-white/[.02] p-[1px] pb-0">
        <div className="overflow-hidden rounded-t-[27px] bg-ink-900 pb-6">
          <div className="flex items-center gap-1.5 border-b border-white/5 px-4 py-3"><i className="h-2.5 w-2.5 rounded-full bg-rose-400/70" /><i className="h-2.5 w-2.5 rounded-full bg-amber-300/70" /><i className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" /><span className="ml-3 truncate text-[11px] text-slate-500">finbridge · Case FB-2026-0142 · Shivneri Electronics, Pune</span></div>
          <div className="grid gap-4 p-4 sm:grid-cols-3 sm:p-6">
            {[['Requested', '₹2.00 Cr', 'text-slate-300'], ['Validated need', '₹1.74 Cr', 'text-emerald-400'], ['Best APR · Kshitij v3', '11.2%', 'text-gold-300']].map(([l, v, c]) => (
              <div key={l} className="rounded-2xl bg-white/[.03] p-4 ring-1 ring-white/5"><p className="text-[11px] uppercase tracking-wider text-slate-500">{l}</p><p className={`mt-1 font-display text-2xl font-semibold ${c}`}>{v}</p></div>))}
            <div className="rounded-2xl bg-white/[.03] p-4 ring-1 ring-white/5 sm:col-span-2">
              <p className="text-xs text-ink-300">Monthly funding gap (₹ L) · illustrative</p>
              <div className="mt-4 flex h-32 items-end gap-1.5">{bars.map((h, i) => <motion.div key={i} initial={{ height: 0 }} whileInView={{ height: `${h}%` }} viewport={{ once: true }} transition={{ delay: .9 + i * .04, duration: .6, ease }} className={`flex-1 rounded-t-md ${i === 7 ? 'bg-gradient-to-t from-emerald-600 to-emerald-300' : 'bg-white/10'}`} />)}</div>
            </div>
            <div className="space-y-2 rounded-2xl bg-white/[.03] p-4 ring-1 ring-white/5">
              <p className="text-xs text-ink-300">Supervisor gates</p>
              {['Readiness', 'Data checks', 'Funding gap', 'Lender offers', 'Verification'].map((g, i) => <p key={g} className="flex items-center gap-2 text-sm text-slate-200"><CheckCircle2 className={`h-4 w-4 ${i < 4 ? 'text-emerald-400' : 'text-slate-600'}`} />{g}<span className={`ml-auto text-[10px] font-semibold ${i < 4 ? 'text-emerald-400' : 'text-slate-500'}`}>{i < 4 ? 'GO' : '…'}</span></p>)}
            </div>
          </div>
        </div>
      </div>
      <div className="hidden">
        <p className="text-[11px] uppercase tracking-wider text-slate-500">Routed for approval</p><p className="mt-1 text-sm font-medium text-white">₹1.74 Cr &gt; ₹1.5 Cr → VP Finance</p>
        <div className="mt-3 flex gap-2"><span className="rounded-full bg-emerald-400/15 px-2.5 py-1 text-[11px] font-medium text-emerald-300">Awaiting decision</span><span className="rounded-full bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">Audited</span></div>
      </div>
    </div>
  );
}

function Stats() {
  const s = [['3', 'specialist agents + Supervisor'], ['7', 'GO/NO-GO gates per case'], ['3', 'simulated lenders negotiated'], ['100%', 'decisions human-approved']];
  return (
    <section className="bg-white px-5 py-16">
      <div className="mx-auto grid max-w-6xl grid-cols-2 gap-px overflow-hidden rounded-3xl bg-line lg:grid-cols-4">
        {s.map(([v, l], i) => <Reveal key={l} delay={i * .08} className="bg-white p-6 text-center sm:p-8"><p className="font-display text-4xl font-light tracking-tight text-ink-950 sm:text-5xl">{v}</p><p className="mt-2 text-sm text-ink-500">{l}</p></Reveal>)}
      </div>
      <p className="mt-4 text-center text-xs text-ink-500">Prototype design figures, illustrative only · synthetic data</p>
    </section>
  );
}

function Audiences() {
  const C = ({ t, d, pts, cta, href, primary, art }: { t: string; d: string; pts: string[]; cta: string; href: string; primary?: boolean; art: React.ReactNode }) => (
    <Reveal className="relative overflow-hidden rounded-[28px] bg-sunken p-7 text-ink-950 sm:p-9">
      <div className="relative z-10 max-w-[18rem]"><h3 className="font-display text-3xl font-normal tracking-tight">{t}</h3><p className="mt-2 text-sm text-ink-500">{d}</p>
        <ul className="mt-6 space-y-2.5 text-sm text-ink-700">{pts.map(p => <li key={p} className="flex gap-2"><span className="text-brand-600">+</span>{p}</li>)}</ul>
        <a href={href} className={`mt-8 inline-flex rounded-full px-5 py-3 text-sm font-semibold ${primary ? 'bg-ink-950 text-white hover:bg-ink-800' : 'bg-white text-ink-950 ring-1 ring-line hover:bg-ink-50'}`}>{cta}</a></div>
      <div aria-hidden className="absolute -right-6 bottom-0 top-10 hidden w-[36%] sm:block">{art}</div>
    </Reveal>);
  return (
    <section id="how" className="scroll-mt-20 bg-white px-5 py-20">
      <div className="mx-auto max-w-6xl">
        <Reveal className="text-center"><Tag>How it works</Tag><H2 a="One workflow," b="two sides of the table" className="mt-4" /><p className="mx-auto mt-4 max-w-xl text-slate-500">FinBridge prepares a lender-ready case for the MSME and gives approvers the evidence to say yes or no with confidence.</p></Reveal>
        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          <C t="For MSMEs" d="Borrow what you need, not what you guess." pts={['Upload GST, bank and order documents', 'See your true monthly funding gap', 'Compare offers on APR, not headline rate']} cta="Sign in to start a case" href="/login/" primary
            art={<div className="h-full rounded-l-2xl bg-ink-800 p-4 ring-1 ring-white/10"><p className="font-display text-2xl text-white/90">Funding gap</p><p className="mt-1 text-[11px] text-emerald-300">● Peak ₹1.79 Cr · Jan-27</p><div className="mt-4 space-y-2">{[80, 64, 92, 48].map((w, i) => <div key={i} className="h-2 rounded-full bg-white/10"><div className="h-2 rounded-full bg-emerald-400/70" style={{ width: `${w}%` }} /></div>)}</div></div>} />
          <C t="For approvers" d="Decide with evidence, not slide decks." pts={['Routed by amount: VP or Director Finance', 'Every gate, offer and comment audited', 'Approve, reject or send back with notes']} cta="See the demo flow" href="#demo"
            art={<div className="relative h-full"><div className="absolute right-10 top-6 grid h-20 w-20 place-items-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-700 font-display text-lg font-semibold shadow-[0_0_50px_rgba(52,211,153,.6)]">GO</div><div className="absolute bottom-6 right-4 h-36 w-36 rotate-45 rounded-3xl border border-emerald-400/30 bg-gradient-to-br from-emerald-400/10 to-transparent" /></div>} />
        </div>
      </div>
    </section>
  );
}

function Statements() {
  const items = [['Over-borrowing', 'is expensive.', 'MSMEs often request a round number. FinBridge validates the real gap month by month.'], ['Headline rates', 'hide fees.', 'LendWise compares APR, fees and net disbursal across three lenders.'], ['Every decision', 'stays human.', 'The system never accepts a loan; a routed approver does, on the record.']];
  const ref = useRef<HTMLDivElement>(null); const [active, setActive] = useState(0);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start center', 'end center'] });
  useEffect(() => scrollYProgress.on('change', v => setActive(Math.min(2, Math.max(0, Math.floor(v * 3))))), [scrollYProgress]);
  const y = useTransform(scrollYProgress, [0, 1], [30, -30]);
  return (
    <section className="bg-white px-5 pb-28">
      <div className="mx-auto max-w-6xl">
        <Reveal className="text-center"><Tag>Why FinBridge</Tag><WordFade words={['Size,', 'negotiate', 'and', 'approve']} /></Reveal>
        <div ref={ref} className="mt-16 grid items-center gap-12 lg:grid-cols-2">
          <div className="space-y-10">{items.map(([a, b, d], i) => <div key={a} className={`transition-all duration-500 ${active === i ? 'opacity-100' : 'opacity-30'}`}><p className="font-display text-3xl tracking-tight text-midnight-950"><span className="text-ink-950">{a}</span> <span className="text-ink-400">{b}</span></p><p className="mt-2 max-w-sm text-sm text-slate-500">{d}</p></div>)}</div>
          <motion.div style={{ y }} className="relative mx-auto w-full max-w-md">
            <div className="aspect-[4/5] rounded-[28px] bg-[radial-gradient(circle_at_30%_20%,var(--fb-brand-900),var(--fb-ink-900)_70%)] p-6">
              <p className="text-xs uppercase tracking-wider text-emerald-300/80">LendWise · round 3</p>
              {[['Kshitij Capital', '11.2% APR', 'Best'], ['Udyamrekha Bank', '12.4% APR', ''], ['Pragati Setu', '13.9% APR', 'Hidden fees']].map(([n, r, t], i) => <div key={n} className={`mt-4 flex items-center justify-between rounded-2xl p-4 text-white ring-1 ${i === 0 ? 'bg-emerald-400/15 ring-emerald-400/40' : 'bg-white/5 ring-white/10'}`}><div><p className="text-sm font-medium">{n}</p><p className="text-xs text-ink-300">{r}</p></div>{t && <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${i === 0 ? 'bg-emerald-400 text-midnight-950' : 'bg-rose-400/20 text-rose-200'}`}>{t}</span>}</div>)}
            </div>
            <div className="absolute -bottom-8 -left-6 w-60 rounded-2xl bg-ink-800 p-4 text-white shadow-2xl ring-1 ring-white/10 sm:-left-12">
              <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-gold-400/20 text-gold-200"><Scale className="h-5 w-5" /></span><div><p className="text-sm font-medium">Shivneri Electronics</p><p className="text-[11px] text-ink-300">Pune · Electronics mfg</p></div></div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]"><div className="rounded-lg bg-white/5 p-2"><p className="text-ink-300">Requested</p><p className="font-semibold">₹2.00 Cr</p></div><div className="rounded-lg bg-emerald-400/10 p-2"><p className="text-emerald-300">Validated</p><p className="font-semibold">₹1.74 Cr</p></div></div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function Agents() {
  const steps = [
    { i: FileSearch, t: 'Onboarding agent', d: 'Collects GST, bank statements and orders; checks readiness and flags prompt-injection in uploaded files.' },
    { i: Gauge, t: 'Working Capital Advisory', d: 'Builds the monthly cash-flow and sizes the true funding gap, with buffer and unused limits netted off.' },
    { i: Handshake, t: 'LendWise', d: 'Negotiates with three simulated lenders over rounds and compares APR, fees and net disbursal.' },
    { i: GitBranch, t: 'Supervisor GO/NO-GO', d: 'Seven gates from readiness to verification. Nothing moves forward without evidence.' },
    { i: Users, t: 'VP / Director approval', d: 'Over ₹1.5 Cr routes to the VP Finance, under to the Director. Humans decide; the system never accepts a loan.' },
  ];
  return (
    <section id="agents" className="relative mx-2 overflow-hidden rounded-[28px] sm:mx-4 bg-ink-950 px-5 py-24 text-white sm:rounded-[56px]">
      <div aria-hidden className="pointer-events-none absolute -right-40 top-20 h-96 w-96 rounded-full bg-emerald-500/10 blur-[100px]" />
      <div id="demo" className="mx-auto grid max-w-6xl scroll-mt-24 gap-14 lg:grid-cols-[1fr_1.1fr]">
        <Reveal>
          <h2 className="font-display text-[clamp(2rem,5vw,3.5rem)] font-normal leading-[1.05] tracking-[-.03em]"><span className="text-emerald-400">Agents</span> do the legwork.<br /><span className="text-slate-500">People make the call.</span></h2>
          <p className="mt-5 max-w-md text-ink-300">The demo flow: a Preparer opens a case, the agents work it through every gate, and the routed approver decides, all in about five minutes.</p>
          <Link href="/login/" className="mt-8 inline-flex items-center gap-2 rounded-full bg-white/10 px-5 py-3 text-sm font-medium ring-1 ring-white/10 hover:bg-white/15">Try it, sign in <ChevronRight className="h-4 w-4" /></Link>
        </Reveal>
        <ol className="relative space-y-3 before:absolute before:bottom-6 before:left-[27px] before:top-6 before:w-px before:bg-gradient-to-b before:from-emerald-400/60 before:to-white/5">
          {steps.map((s, k) => <Reveal key={s.t} delay={k * .08}><li className="relative flex gap-4 rounded-2xl bg-ink-900 p-4 ring-1 ring-white/[.07] hover:ring-emerald-400/30">
            <span className="relative z-10 grid h-14 w-14 shrink-0 place-items-center rounded-xl bg-ink-800 ring-1 ring-white/10"><s.i className="h-6 w-6 text-emerald-400" /></span>
            <div><p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Step {k + 1}</p><p className="font-medium">{s.t}</p><p className="mt-1 text-sm text-ink-300">{s.d}</p></div></li></Reveal>)}
        </ol>
      </div>
    </section>
  );
}

function Features() {
  const f = [[Bot, 'Agentic, not a chatbot', 'Specialist agents with clear inputs, outputs and hand-offs, coordinated by a Supervisor.'], [IndianRupee, 'True cost of credit', 'APR with processing fees, insurance and net disbursal, not just the headline rate.'], [ScrollText, 'Complete audit trail', 'Every gate result, offer round, comment and decision is time-stamped.'], [FileSearch, 'Document intelligence', 'CSV, Excel and PDF extraction with status, and prompt-injection flags on uploads.'], [GitBranch, 'Policy-driven routing', '₹1.5 Cr threshold routing, with ambiguous cases held for clarification.'], [Sparkles, 'Swap-in services', 'Typed service layer: each agent owner plugs in a real API without touching the UI.']] as const;
  return (
    <section className="bg-white px-5 py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal className="text-center"><Tag>Features</Tag><H2 a="Built for" b="credit committees" className="mt-4" /><p className="mx-auto mt-4 max-w-xl text-slate-500">Everything a finance team needs to trust an AI-prepared proposal.</p></Reveal>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{f.map(([I, t, d], i) => <Reveal key={t} delay={(i % 3) * .08} className="group rounded-3xl bg-sunken p-7 transition hover:-translate-y-1 hover:bg-white hover:shadow-xl"><span className="grid h-11 w-11 place-items-center rounded-xl bg-midnight-950 text-emerald-400"><I className="h-5 w-5" /></span><p className="mt-5 font-display text-lg font-medium text-midnight-950">{t}</p><p className="mt-1.5 text-sm text-slate-500">{d}</p></Reveal>)}</div>
      </div>
    </section>
  );
}

function Security() {
  const s = [[Fingerprint, 'Two-step sign-in', 'TOTP with Google or Microsoft Authenticator, plus one-time backup codes.'], [ScrollText, 'Append-only user logs', 'Sign-ins, failures, MFA and password changes, in SAST with IP and browser.'], [KeyRound, 'Role-based approvals', 'Preparer, VP Finance and Director Finance, each with their own permissions.'], [Lock, 'Hardened sessions', 'scrypt-hashed passwords, httpOnly cookies, rate limits, invite-only accounts.']] as const;
  const reduce = useReducedMotion();
  const coins: [typeof Lock, string, string][] = [[ShieldCheck, 'left-[38%] top-[30%] h-32 w-32', 'h-12 w-12'], [Fingerprint, 'left-[12%] top-[10%] h-20 w-20', 'h-8 w-8'], [KeyRound, 'right-[10%] top-[4%] h-16 w-16', 'h-6 w-6'], [Lock, 'right-[16%] bottom-[8%] h-14 w-14', 'h-5 w-5']];
  return (
    <section id="security" className="scroll-mt-20 bg-white px-5 py-24">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <Reveal><Tag>Security</Tag><h2 className="mt-4 font-display text-[clamp(1.9rem,4.4vw,3.2rem)] font-normal leading-[1.08] tracking-[-.03em] text-ink-950">Security is built in, <span className="text-ink-400">not bolted on.</span></h2><p className="mt-3 max-w-md text-ink-500">The live prototype runs real authentication on its own server.</p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2">{s.map(([I, t, d]) => <div key={t} className="rounded-2xl bg-sunken p-4"><I className="h-5 w-5 text-brand-700" /><p className="mt-2 text-sm font-medium text-ink-950">{t}</p><p className="mt-1 text-xs text-ink-500">{d}</p></div>)}</div>
          <Link href="/login/" className="mt-8 inline-flex rounded-full bg-ink-950 px-5 py-2.5 text-sm font-medium text-white hover:bg-ink-800">Sign in securely</Link></Reveal>
        <div aria-hidden className="relative mx-auto aspect-square w-full max-w-md">
          <div className="absolute inset-[18%] rounded-full bg-brand-200/40 blur-3xl" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" fill="none"><ellipse cx="50" cy="52" rx="44" ry="22" stroke="var(--fb-brand-300)" strokeWidth=".3" transform="rotate(-18 50 52)" /></svg>
          {coins.map(([I, pos, ic], i) => <motion.div key={i} className={`absolute grid place-items-center rounded-full bg-ink-950 text-white shadow-2xl ${pos}`} animate={reduce ? undefined : { y: [0, -10, 0] }} transition={{ duration: 4 + i, repeat: Infinity, ease: 'easeInOut' }}><I className={ic} /></motion.div>)}
        </div>
      </div>
    </section>
  );
}

function WordFade({ words }: { words: string[] }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 90%', 'start 40%'] });
  return <h2 ref={ref} className="mt-4 font-display text-[clamp(2.2rem,6vw,4.5rem)] font-normal leading-[1.05] tracking-[-.03em] text-ink-950">{words.map((w, i) => <Word key={i} p={scrollYProgress} i={i} n={words.length}>{w}</Word>)}</h2>;
}
function Word({ p, i, n, children }: { p: ReturnType<typeof useScroll>['scrollYProgress']; i: number; n: number; children: string }) {
  const reduce = useReducedMotion();
  const o = useTransform(p, [i / n, (i + 1) / n], [0.18, 1]);
  return <motion.span style={reduce ? undefined : { opacity: o }} className="mr-[.25em] inline-block">{children}</motion.span>;
}

function Problem() {
  return (
    <section className="bg-white px-5 pb-24">
      <Reveal className="mx-auto max-w-4xl text-center">
        <p className="text-xs font-semibold uppercase tracking-[.2em] text-emerald-600">Problem statement</p>
        <blockquote className="mt-5 font-display text-[clamp(1.4rem,3.2vw,2.3rem)] font-light leading-snug tracking-tight text-midnight-950">“India’s MSMEs struggle to get the <span className="text-emerald-600">right amount</span> of working capital at the <span className="text-emerald-600">right cost</span>; proposals are slow, opaque and hard to audit.”</blockquote>
        <p className="mt-4 text-sm text-slate-500">Why FinBridge: our capstone brief, paraphrased by the team</p>
      </Reveal>
    </section>
  );
}

const TEAM = ['Suresh Nagarajanna', 'Tejas Tipre', 'Abhishek Pareek', 'Adesh Surroach', 'Mousita Dhar', 'Pritish Patil'];
function Team() {
  return (
    <section id="team" className="bg-white px-5 pb-28">
      <div className="mx-auto max-w-6xl">
        <Reveal className="text-center"><Tag>The team</Tag><H2 a="Meet the" b="six of us" className="mt-4" /></Reveal>
        <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">{TEAM.map((n, i) => <Reveal key={n} delay={i * .05} className="rounded-3xl bg-slate-50 p-5 text-center ring-1 ring-slate-200/70"><span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-midnight-900 to-brand-950 font-display text-lg font-semibold text-gold-200 ring-4 ring-white">{n.split(' ').map(x => x[0]).join('')}</span><p className="mt-3 text-sm font-medium leading-tight text-midnight-950">{n}</p></Reveal>)}</div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="bg-white px-5 pb-10">
      <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[32px] bg-ink-950 px-6 py-16 text-center text-white">
        <div aria-hidden className="absolute inset-0 [background:radial-gradient(50%_80%_at_50%_100%,rgba(16,185,129,.3),transparent)]" />
        <div className="relative"><h2 className="font-display text-[clamp(1.8rem,4.5vw,3rem)] font-normal tracking-tight">Ready to see it <span className="text-emerald-400">end-to-end?</span></h2><p className="mt-3 text-ink-300">Accounts are invite-only. Ask your Global Admin for access.</p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row"><Link href="/login/" className="rounded-full bg-emerald-400 px-7 py-3.5 font-semibold text-midnight-950 hover:bg-emerald-300">Sign in</Link><a href="#demo" className="rounded-full px-7 py-3.5 font-medium ring-1 ring-white/20 hover:bg-white/5">Watch demo flow</a></div></div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="bg-white px-5 pb-10 pt-6">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 border-t border-slate-200 pt-6 text-sm text-slate-500 sm:flex-row">
        <p className="font-display font-semibold text-midnight-950">FinBridge<span className="text-emerald-600">AI</span></p>
        <p className="text-center">FinBridge AI · Team IntelliCore · IIT Kharagpur Capstone</p>
        <p className="text-xs">Synthetic data & simulated lenders only</p>
      </div>
    </footer>
  );
}

export default function Landing() {
  return <main className="min-h-screen overflow-x-clip bg-white"><Nav /><Hero /><Stats /><Audiences /><Statements /><Agents /><Features /><Security /><Problem /><Team /><CTA /><Footer /><SideToggle /></main>;
}
