import { Landmark } from 'lucide-react';
export const Logo = ({ dark }: { dark?: boolean }) => (
  <div className="flex items-center gap-2">
    <div className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-gold-300 via-gold-500 to-emerald-500 shadow-lg shadow-gold-500/30"><Landmark className="h-4 w-4 text-midnight-950" /></div>
    <span className={`font-display text-lg font-bold tracking-tight ${dark ? 'text-slate-900' : 'text-white'}`}>Cred<span className="text-gold-400">Assure</span></span>
  </div>
);
