
type IconProps = { size?: number; strokeWidth?: number; className?: string };
const base = (size: number, strokeWidth: number) => ({ width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const });

export function ArrowUpRight({ size = 16, strokeWidth = 1.8 }: IconProps) { return <svg {...base(size, strokeWidth)}><path d="M7 17 17 7M7 7h10v10" /></svg>; }
export function ArrowRight({ size = 16, strokeWidth = 1.8 }: IconProps) { return <svg {...base(size, strokeWidth)}><path d="M4 12h15m-6-6 6 6-6 6" /></svg>; }
export function SunMoon({ size = 18 }: IconProps) { return <svg {...base(size, 1.6)}><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/></svg>; }
export function GlobeIcon({ size = 18 }: IconProps) { return <svg {...base(size, 1.6)}><circle cx="12" cy="12" r="9"/><path d="M3.5 9h17M3.5 15h17M12 3c2.4 2.5 3.5 5.5 3.5 9S14.4 18.5 12 21c-2.4-2.5-3.5-5.5-3.5-9S9.6 5.5 12 3Z"/></svg>; }
export function MessageIcon({ size = 18 }: IconProps) { return <svg {...base(size, 1.6)}><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-1.5 2v-6.2A7.5 7.5 0 1 1 20 11.5Z"/><path d="M8 11.5h8M8 8.5h5"/></svg>; }
export function MenuIcon({ size = 20 }: IconProps) { return <svg {...base(size, 1.7)}><path d="M4 7h16M4 12h16M4 17h16"/></svg>; }
export function CloseIcon({ size = 18 }: IconProps) { return <svg {...base(size, 1.8)}><path d="m6 6 12 12M18 6 6 18"/></svg>; }
export function LeafIcon({ size = 22 }: IconProps) { return <svg {...base(size, 1.55)}><path d="M19.5 4.5c-8.8-.4-14 3.3-14 9.1a5.8 5.8 0 0 0 5.8 5.8c5.8 0 9.5-5.2 9.1-14.9Z"/><path d="M4 21c2.7-5.1 6.4-8.4 12-11"/></svg>; }
export function SoilIcon({ size = 22 }: IconProps) { return <svg {...base(size, 1.55)}><path d="M3 7c3-2 5 2 8 0s5-2 10 0M3 12c3-2 5 2 8 0s5-2 10 0M3 17c3-2 5 2 8 0s5-2 10 0"/></svg>; }
export function WaterIcon({ size = 22 }: IconProps) { return <svg {...base(size, 1.55)}><path d="M12 3.2S5.5 10.4 5.5 14.2a6.5 6.5 0 0 0 13 0C18.5 10.4 12 3.2 12 3.2Z"/><path d="M9 15.5c.4 1.4 1.4 2.1 3 2.2"/></svg>; }
export function LayersIcon({ size = 22 }: IconProps) { return <svg {...base(size, 1.55)}><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></svg>; }
export function ChartIcon({ size = 22 }: IconProps) { return <svg {...base(size, 1.55)}><path d="M3 20V4M3 20h18"/><path d="m6 15 4-4 3 2 5-7"/></svg>; }
export function CheckIcon({ size = 16 }: IconProps) { return <svg {...base(size, 2)}><path d="m4 12 5 5L20 6"/></svg>; }
