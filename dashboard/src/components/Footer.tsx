import { Github } from 'lucide-react';
import { REPO_URL, AUTHOR } from '@/lib/site';

/**
 * Site-wide footer. Calm rack surface, hairline top border, mono labels —
 * same chrome language as the nav. Carries the wordmark + tagline on the left
 * and the source link + authorship on the right.
 */
export function Footer() {
  return (
    <footer className="border-t border-signal-white/10 bg-rack-black/40">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span aria-hidden="true" className="grid grid-cols-2 gap-0.5">
              <span className="block size-1.5 rounded-[1px] bg-channel-green" />
              <span className="block size-1.5 rounded-[1px] bg-channel-red" />
              <span className="block size-1.5 rounded-[1px] bg-channel-violet" />
              <span className="block size-1.5 rounded-[1px] bg-channel-blue" />
            </span>
            <span className="font-mono text-xs uppercase tracking-widest text-signal-white">
              My Life in Data
            </span>
          </div>
          <p className="font-mono text-[11px] text-signal-white/40">
            Pretty charts, brutal honesty, optional self-improvement.
          </p>
        </div>

        <div className="flex items-center gap-6">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1.5 rounded-sm font-mono text-[11px] uppercase tracking-widest text-signal-white/60 transition-colors hover:text-signal-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-white"
          >
            <Github className="size-4" aria-hidden="true" />
            Source
          </a>
          <span className="font-mono text-[11px] uppercase tracking-widest text-signal-white/40">
            Built by {AUTHOR}
          </span>
        </div>
      </div>
    </footer>
  );
}
