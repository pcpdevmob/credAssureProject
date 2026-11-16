type Scale = Record<number, string>;
export const ink: Scale; export const brand: Scale; export const gold: Scale; export const rose: Scale;
export const dark: { ink: Scale; brand: Scale; gold: Scale; rose: Scale; surface: Record<string, string>; state: Record<string, string> };
export const surface: { canvas: string; card: string; line: string; sunken: string };
export const state: Record<string, string>;
export const CHART: { primary: string; primarySoft: string; secondary: string; secondarySoft: string; tertiary: string; tertiarySoft: string; muted: string; grid: string; axis: string; positive: string; negative: string; warn: string; series: string[] };
