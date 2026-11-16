'use client';
import { motion, useReducedMotion } from 'framer-motion';

/** Big animated "CredAssure" wordmark: letter-by-letter reveal, gold→emerald shimmer, soft glow pulse. Static under reduced motion. */
export default function BigTitle({ className = '' }: { className?: string }) {
  const reduce = useReducedMotion();
  const words = ['CredAssure'];
  let i = 0;
  return (
    <h1 aria-label="CredAssure" className={`relative font-display font-extrabold whitespace-nowrap leading-[.95] tracking-tight text-[clamp(2rem,10vw,4.25rem)] lg:text-[clamp(3rem,5.3vw,5.75rem)] ${className}`}>
      {!reduce && <motion.span aria-hidden className="pointer-events-none absolute -inset-x-6 -inset-y-4 -z-0 rounded-full bg-gold-400/20 blur-3xl" animate={{ opacity: [0.35, 0.8, 0.35] }} transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }} />}
      <span aria-hidden className="relative flex gap-x-[.25em]">
        {words.map(w => (
          <span key={w} className="inline-flex">
            {w.split('').map(ch => {
              const d = i++ * 0.05;
              return (
                <motion.span key={d} className="fb-shimmer inline-block bg-clip-text text-transparent"
                  initial={reduce ? false : { opacity: 0, y: '0.4em', rotateX: -70, filter: 'blur(6px)' }}
                  animate={{ opacity: 1, y: 0, rotateX: 0, filter: 'blur(0px)' }}
                  transition={{ delay: 0.15 + d, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                  style={reduce ? { animation: 'none' } : undefined}>{ch}</motion.span>
              );
            })}
          </span>
        ))}
      </span>
    </h1>
  );
}
