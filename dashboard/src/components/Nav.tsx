import { useState, useEffect } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  label: string;
  channel: Channel | null; // null for utility routes (e.g. /system, /now)
}

const ITEMS: NavItem[] = [
  { to: '/spotify',  label: 'Spotify',  channel: 'spotify'  },
  { to: '/youtube',  label: 'YouTube',  channel: 'youtube'  },
  { to: '/maps',     label: 'Maps',     channel: 'maps'     },
  { to: '/google',   label: 'Calendar', channel: 'calendar' },
];

const UTILS: NavItem[] = [
  { to: '/now',    label: 'Now',    channel: null },
  { to: '/system', label: 'System', channel: null },
];

/**
 * Persistent top-bar nav per DESIGN.md §5.
 * - Wordmark left, channel chips center, utility links right.
 * - Active route uses channel-color underline (never full background fill).
 * - Mobile: collapses to a slide-over with channels stacked vertically.
 */
export function Nav() {
  const location = useLocation();
  const [open, setOpen] = useState(false);

  // Close slide-over when route changes
  useEffect(() => setOpen(false), [location.pathname]);

  // Lock body scroll while slide-over is open
  useEffect(() => {
    if (open) {
      const original = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = original; };
    }
  }, [open]);

  return (
    <header className="sticky top-0 z-40 border-b border-signal-white/10 bg-rack-black/85 backdrop-blur-[2px]">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Link
          to="/"
          aria-label="My Life in Data — home"
          className="flex items-center gap-2 rounded-sm font-mono text-xs uppercase tracking-widest text-signal-white transition-colors hover:text-signal-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white"
        >
          <span aria-hidden="true" className="grid grid-cols-2 gap-0.5">
            <span className="block size-1.5 rounded-[1px] bg-channel-green" />
            <span className="block size-1.5 rounded-[1px] bg-channel-red" />
            <span className="block size-1.5 rounded-[1px] bg-channel-violet" />
            <span className="block size-1.5 rounded-[1px] bg-channel-blue" />
          </span>
          <span>My Life in Data</span>
        </Link>

        {/* Desktop channel chips */}
        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Channels">
          {ITEMS.map((item) => (
            <NavChip key={item.to} item={item} />
          ))}
        </nav>

        <div className="ml-auto hidden items-center gap-2 md:flex">
          {UTILS.map((item) => (
            <UtilLink key={item.to} item={item} />
          ))}
        </div>

        {/* Mobile menu trigger */}
        <button
          type="button"
          className="ml-auto inline-flex size-9 items-center justify-center rounded-sm border border-signal-white/10 text-signal-white/80 transition-colors hover:border-signal-white/30 hover:text-signal-white md:hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          aria-controls="mobile-nav"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="size-4" aria-hidden="true" /> : <Menu className="size-4" aria-hidden="true" />}
        </button>
      </div>

      {/* Mobile slide-over */}
      <div
        id="mobile-nav"
        className={cn(
          'fixed inset-x-0 top-14 bottom-0 z-30 origin-top transform overflow-y-auto bg-rack-black/95 backdrop-blur-sm transition-transform duration-200 ease-snap md:hidden',
          open ? 'translate-y-0' : '-translate-y-full pointer-events-none',
        )}
        aria-hidden={!open}
      >
        <nav className="mx-auto flex max-w-7xl flex-col gap-1 px-4 py-6" aria-label="Channels">
          {ITEMS.map((item) => (
            <NavChip key={item.to} item={item} stacked />
          ))}
          <div className="my-3 h-px bg-signal-white/10" />
          {UTILS.map((item) => (
            <UtilLink key={item.to} item={item} stacked />
          ))}
        </nav>
      </div>
    </header>
  );
}

function NavChip({ item, stacked = false }: { item: NavItem; stacked?: boolean }) {
  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) =>
        cn(
          'group relative rounded-sm px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
          item.channel ? CHANNEL_CLASS.focusRing[item.channel] : 'focus-visible:outline-signal-white',
          stacked && 'flex items-center justify-between',
          isActive ? 'text-signal-white' : 'text-signal-white/60 hover:text-signal-white',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span className="flex items-center gap-2">
            {item.channel && (
              <span
                className={cn(
                  'block size-1.5 rounded-[1px]',
                  isActive ? CHANNEL_CLASS.bg[item.channel] : 'bg-signal-white/25',
                )}
                aria-hidden="true"
              />
            )}
            {item.label}
          </span>
          {isActive && item.channel && !stacked && (
            <span
              className={cn('absolute inset-x-2 -bottom-px h-0.5 rounded-sm', CHANNEL_CLASS.bg[item.channel])}
              aria-hidden="true"
            />
          )}
        </>
      )}
    </NavLink>
  );
}

function UtilLink({ item, stacked = false }: { item: NavItem; stacked?: boolean }) {
  return (
    <NavLink
      to={item.to}
      end
      className={({ isActive }) =>
        cn(
          'rounded-sm px-2 py-1 font-mono text-[11px] uppercase tracking-widest transition-colors',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white',
          stacked && 'flex items-center justify-between',
          isActive ? 'text-signal-white' : 'text-signal-white/40 hover:text-signal-white/80',
        )
      }
    >
      {item.label}
    </NavLink>
  );
}
