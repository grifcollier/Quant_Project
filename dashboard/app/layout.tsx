import type { Metadata } from 'next';
import './globals.css';
import NavLinks from './components/NavLinks';

export const metadata: Metadata = {
  title: 'Quant Dashboard',
  description: 'Live trade monitoring',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen text-zinc-100 antialiased">
        <header className="border-b border-zinc-800 px-6 py-3 flex items-center gap-6 sticky top-0 bg-[#09090f]/95 backdrop-blur-sm z-10">
          <span className="text-emerald-400 font-semibold tracking-tight">
            Quant Dashboard
          </span>
          <NavLinks />
        </header>
        <main className="px-6 py-8 max-w-7xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
