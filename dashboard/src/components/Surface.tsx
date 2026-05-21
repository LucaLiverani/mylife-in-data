import * as React from 'react';
import { cn } from '@/lib/utils';

interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  as?: 'div' | 'section' | 'article';
  /** Render an explicit semantic container; defaults to a styled div. */
  bare?: boolean;
}

/**
 * Flat-by-default rack surface, per DESIGN.md §4 Elevation.
 * Hairline border, rack-black background, no shadow at rest. Hover/focus state
 * lives on interactive children, not the surface itself.
 */
export const Surface = React.forwardRef<HTMLDivElement, SurfaceProps>(
  ({ as: Tag = 'div', bare = false, className, ...props }, ref) => (
    <Tag
      ref={ref}
      className={cn(
        !bare && 'rounded-md border border-signal-white/10 bg-rack-black/60 p-6',
        className,
      )}
      {...props}
    />
  ),
);
Surface.displayName = 'Surface';
