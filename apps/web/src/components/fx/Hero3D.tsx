'use client';
// 3D hero: glass/metal globe with an orbiting gold ring, floating ₹ coins and subtle particles.
// Loaded lazily (next/dynamic, ssr:false) and only on large screens; reduced-motion users get a static frame.
import { Canvas, useFrame } from '@react-three/fiber';
import { ink, brand, gold } from '@/styles/tokens';
import { Float, Sparkles } from '@react-three/drei';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';

function rupeeTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 256; const g = c.getContext('2d')!;
  const grd = g.createRadialGradient(128, 110, 20, 128, 128, 128); grd.addColorStop(0, gold[200]); grd.addColorStop(0.6, gold[400]); grd.addColorStop(1, gold[600]);
  g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
  g.strokeStyle = 'rgba(120,80,10,.55)'; g.lineWidth = 10; g.beginPath(); g.arc(128, 128, 112, 0, Math.PI * 2); g.stroke();
  g.fillStyle = gold[700]; g.font = 'bold 150px Sora, Inter, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('₹', 128, 138);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function Coin({ position, speed, scale = 1, still }: { position: [number, number, number]; speed: number; scale?: number; still: boolean }) {
  const ref = useRef<THREE.Mesh>(null!); const tex = useMemo(rupeeTexture, []);
  useFrame((_, d) => { if (!still) ref.current.rotation.y += d * speed; });
  const mats = useMemo(() => [
    new THREE.MeshStandardMaterial({ color: gold[500], metalness: 1, roughness: 0.28 }),
    new THREE.MeshStandardMaterial({ map: tex, metalness: 0.75, roughness: 0.3 }),
    new THREE.MeshStandardMaterial({ map: tex, metalness: 0.75, roughness: 0.3 }),
  ], [tex]);
  return <Float speed={still ? 0 : 1.6} rotationIntensity={still ? 0 : 0.6} floatIntensity={still ? 0 : 1.2}>
    <mesh ref={ref} position={position} rotation={[Math.PI / 2, 0, 0.3]} scale={scale} material={mats}><cylinderGeometry args={[0.42, 0.42, 0.07, 48]} /></mesh>
  </Float>;
}

function Globe({ still }: { still: boolean }) {
  const g = useRef<THREE.Group>(null!); const ring = useRef<THREE.Mesh>(null!);
  useFrame((s, d) => { if (still) return; g.current.rotation.y += d * 0.12; ring.current.rotation.z += d * 0.25; g.current.position.y = Math.sin(s.clock.elapsedTime * 0.6) * 0.06; });
  return <group ref={g}>
    <mesh><icosahedronGeometry args={[1.35, 6]} /><meshPhysicalMaterial color={ink[700]} metalness={0.35} roughness={0.12} transmission={0.55} thickness={1.2} clearcoat={1} clearcoatRoughness={0.1} transparent opacity={0.92} /></mesh>
    <mesh><icosahedronGeometry args={[1.38, 3]} /><meshBasicMaterial color={brand[200]} wireframe transparent opacity={0.18} /></mesh>
    <mesh ref={ring} rotation={[1.2, 0.2, 0]}><torusGeometry args={[2.0, 0.025, 16, 160]} /><meshStandardMaterial color={gold[300]} metalness={1} roughness={0.2} emissive={gold[800]} emissiveIntensity={0.4} /></mesh>
    <mesh rotation={[1.75, -0.5, 0]}><torusGeometry args={[2.35, 0.012, 12, 160]} /><meshStandardMaterial color={brand[400]} metalness={0.8} roughness={0.3} emissive={brand[800]} emissiveIntensity={0.6} /></mesh>
  </group>;
}

export default function Hero3D({ still = false }: { still?: boolean }) {
  return <Canvas dpr={[1, 1.5]} camera={{ position: [0, 0.2, 6.2], fov: 42 }} gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }} frameloop={still ? 'demand' : 'always'}>
    <ambientLight intensity={0.35} />
    <directionalLight position={[4, 5, 3]} intensity={2.2} color={gold[50]} />
    <pointLight position={[-4, -2, 2]} intensity={30} color={ink[400]} />
    <pointLight position={[3, -3, -2]} intensity={18} color={brand[500]} />
    <Globe still={still} />
    <Coin position={[-2.3, 1.2, 0.6]} speed={1.1} still={still} />
    <Coin position={[2.4, -1.0, 0.9]} speed={-0.9} scale={0.85} still={still} />
    <Coin position={[1.9, 1.6, -0.4]} speed={0.7} scale={0.6} still={still} />
    <Coin position={[-1.7, -1.6, 1.1]} speed={-1.3} scale={0.55} still={still} />
    {!still && <Sparkles count={70} scale={[8, 5, 3]} size={2.2} speed={0.35} color="#f5d68a" opacity={0.7} />}
  </Canvas>;
}
