'use client';
import { animate, motion, useInView, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

/** Animated number counter (respects reduced motion). */
export function CountUp({ value, format = (n: number) => Math.round(n).toLocaleString('en-IN') }: { value: number; format?: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null); const inView = useInView(ref, { once: true }); const reduce = useReducedMotion();
  const [v, setV] = useState(reduce ? value : 0);
  useEffect(() => { if (!inView) return; if (reduce) { setV(value); return; } const c = animate(0, value, { duration: 1.1, ease: [0.16, 1, 0.3, 1], onUpdate: setV }); return () => c.stop(); }, [inView, value, reduce]);
  return <span ref={ref} className="num">{format(v)}</span>;
}

/** Glass card with subtle pointer tilt (disabled for reduced motion / touch). */
export function TiltCard({ className, children }: { className?: string; children: React.ReactNode }) {
  const reduce = useReducedMotion(); const x = useMotionValue(0); const y = useMotionValue(0);
  const rx = useSpring(useTransform(y, [-0.5, 0.5], [6, -6]), { stiffness: 200, damping: 18 }); const ry = useSpring(useTransform(x, [-0.5, 0.5], [-6, 6]), { stiffness: 200, damping: 18 });
  return <motion.div style={reduce ? undefined : { rotateX: rx, rotateY: ry, transformPerspective: 900 }}
    onPointerMove={e => { if (reduce || e.pointerType !== 'mouse') return; const r = e.currentTarget.getBoundingClientRect(); x.set((e.clientX - r.left) / r.width - 0.5); y.set((e.clientY - r.top) / r.height - 0.5); }}
    onPointerLeave={() => { x.set(0); y.set(0); }}
    whileHover={reduce ? undefined : { y: -3 }} className={cn('glass rounded-2xl', className)}>{children}</motion.div>;
}

export const Stagger = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <motion.div className={className} initial="h" animate="s" variants={{ h: {}, s: { transition: { staggerChildren: 0.07 } } }}>{children}</motion.div>);
export const Item = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <motion.div className={className} variants={{ h: { opacity: 0, y: 14 }, s: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] } } }}>{children}</motion.div>);
