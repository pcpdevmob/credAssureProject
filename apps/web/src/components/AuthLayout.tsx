'use client';
import dynamic from 'next/dynamic';
import { useEffect, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Logo } from './Logo';
import BigTitle from './fx/BigTitle';
import { ShieldCheck, Bot, GitBranch, Scale } from 'lucide-react';

const Hero3D = dynamic(() => import('./fx/Hero3D'), { ssr: false, loading: () => <div className="h-full w-full" /> });

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  const [big, setBig] = useState(false); // only mount WebGL on large screens (keeps phones light)
  useEffect(() => { const m = window.matchMedia('(min-width: 1024px)'); const f = () => setBig(m.matches); f(); m.addEventListener('change', f); return () => m.removeEventListener('change', f); }, []);
  const f = [
    { i: Bot, t: 'Three specialist agents', d: 'Onboarding, Working Capital Advisory and LendWise, coordinated by a Supervisor.' },
    { i: GitBranch, t: 'GO / NO-GO gates', d: 'No proposal moves forward until every mandatory check is evidenced.' },
    { i: Scale, t: 'True cost comparison', d: 'APR, fees & net disbursal — not just the headline rate.' },
    { i: ShieldCheck, t: 'Human-controlled approval', d: 'Routed to VP or Director, Finance. The system never accepts a loan.' },
  ];
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <div className="mesh-midnight relative hidden overflow-hidden p-12 lg:flex lg:flex-col">
        <div className="pointer-events-none absolute inset-0 opacity-[.07] [background-image:linear-gradient(rgba(255,255,255,.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.6)_1px,transparent_1px)] [background-size:44px_44px]" />
        <div className="relative z-10"><Logo /></div>
        <div className="absolute inset-x-0 top-6 h-[44%]" aria-hidden>{big && <Hero3D still={!!reduce} />}</div>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7, ease: [0.16, 1, 0.3, 1] }} className="relative z-10 mt-auto max-w-xl">
          <BigTitle className="mb-5" />
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <p className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-gold-300/20 to-gold-500/10 px-3.5 py-1 text-xs font-semibold uppercase tracking-[.16em] text-gold-200 ring-1 ring-gold-300/40">Capstone Project · IIT Kharagpur</p>
            <p className="inline-flex items-center rounded-full bg-white/5 px-3 py-1 text-xs font-medium text-slate-300 ring-1 ring-white/10">₹ MSME working capital · agentic & audited</p>
          </div>
          <h2 className="font-display text-2xl font-bold leading-[1.15] tracking-tight text-white xl:text-3xl">Working-capital finance for MSMEs, <span className="text-gold-grad">audited end-to-end.</span></h2>
          <div className="mt-8 grid grid-cols-2 gap-3">{f.map((x, i) => <motion.div key={x.t} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .25 + i * .08 }} className="rounded-2xl bg-white/[.04] p-4 ring-1 ring-white/10 backdrop-blur"><x.i className="h-5 w-5 text-gold-300" /><p className="mt-2 text-sm font-semibold text-white">{x.t}</p><p className="mt-0.5 text-xs leading-relaxed text-slate-300">{x.d}</p></motion.div>)}</div>
          <div className="mt-8 flex items-end justify-between gap-4 border-t border-white/10 pt-5">
            <div><p className="text-[11px] uppercase tracking-[.2em] text-slate-400">Designed & built by</p><p className="font-display text-xl font-semibold"><span className="text-gold-grad">Team IntelliCore</span></p></div>
            <p className="text-right text-[11px] text-slate-400">Synthetic data &<br />simulated lenders only</p>
          </div>
        </motion.div>
      </div>
      <div className="relative flex flex-col">
        <div className="mesh-midnight overflow-hidden px-6 pb-8 pt-6 lg:hidden"><Logo /><BigTitle className="mt-5" /><p className="mt-4 text-[11px] font-semibold uppercase tracking-[.16em] text-gold-200">Capstone Project · IIT Kharagpur</p><p className="mt-1 font-display text-xl font-bold leading-tight text-white">MSME working capital, <span className="text-gold-grad">audited end-to-end.</span></p><p className="mt-2 text-xs text-slate-300">Designed & built by <span className="font-semibold text-gold-200">Team IntelliCore</span></p></div>
        <div className="flex flex-1 items-center justify-center p-6 sm:p-12"><motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }} className="w-full max-w-md">{children}</motion.div></div>
      </div>
    </div>
  );
}
