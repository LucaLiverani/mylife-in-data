import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { cn } from '@/lib/utils';

interface EventRowProps {
  channel: Channel;
  primary: string;
  secondary: string;
  /** Right-column primary value (e.g. relative time, channel-coloured). */
  rightTop: string;
  /** Right-column secondary value (e.g. absolute timestamp, dimmed). */
  rightBottom: string;
  /** 40×40 thumbnail image (overrides leftIcon). */
  leftImage?: string;
  /** 16×16 inline icon (rendered in channel color). */
  leftIcon?: React.ReactNode;
}

/**
 * Shared list-item row for "Recent" surfaces (Home recent panels, Spotify
 * Recently Played, YouTube Recent Videos, Maps Last Activity).
 *
 *   ┌─────────────────────────────────────────────────────┐
 *   │ ▢  Primary line                          right-top   │
 *   │    Secondary line                        right-bot   │
 *   └─────────────────────────────────────────────────────┘
 *
 * No side-stripe affordance — DESIGN.md §6.
 * Channel identity carried via icon color and right-top text color.
 */
export function EventRow({
  channel,
  primary,
  secondary,
  rightTop,
  rightBottom,
  leftImage,
  leftIcon,
}: EventRowProps) {
  const channelText = CHANNEL_CLASS.text[channel];
  return (
    <div className="flex items-center gap-3 border-b border-signal-white/5 px-4 py-3 last:border-b-0 transition-colors duration-150 ease-snap hover:bg-signal-white/[0.03] sm:px-6">
      {leftImage ? (
        <img
          src={leftImage}
          alt=""
          loading="lazy"
          decoding="async"
          className="size-10 shrink-0 rounded-sm object-cover"
        />
      ) : leftIcon ? (
        <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-sm', channelText)}>
          {leftIcon}
        </span>
      ) : null}
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-signal-white">{primary}</div>
        <div className="truncate text-xs text-signal-white/60">{secondary}</div>
      </div>
      <div className="shrink-0 whitespace-nowrap text-right">
        <div className={cn('font-mono text-xs font-medium', channelText)}>{rightTop}</div>
        <div className="font-mono text-[10px] text-signal-white/60">{rightBottom}</div>
      </div>
    </div>
  );
}
