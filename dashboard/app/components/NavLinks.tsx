'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/',          label: 'Overview'  },
  { href: '/positions', label: 'Positions' },
  { href: '/orders',    label: 'Orders'    },
  { href: '/pnl',       label: 'P&L'       },
  { href: '/returns',   label: 'Returns'   },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1">
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
            pathname === l.href
              ? 'bg-zinc-800 text-zinc-100 font-medium'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50'
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
