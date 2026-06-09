import { motion } from 'framer-motion';
import { CHANNEL_CLASS, type Channel } from '@/lib/channels';
import { formatKpi, type KpiKind } from '@/lib/format';

interface KPIMetricProps {
  label: string;
  /** Raw value (preferred) or pre-formatted string. Formatter normalizes both. */
  value: number | string;
  /** Selects the formatter (`count` → 4,325 ; `hours` → 253h ; `percent` → 12.4% ; `text` → as-is). */
  kind?: KpiKind;
  channel?: Channel;
  trend?: { value: string; isPositive: boolean };
}

export function KPIMetric({ label, value, kind = 'count', channel = 'spotify', trend }: KPIMetricProps) {
  const valueColor = CHANNEL_CLASS.text[channel];
  const display = formatKpi(value, kind);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="rounded-md border border-signal-white/10 bg-rack-black/60 p-5">
        <p className="font-mono text-xs uppercase tracking-wider text-signal-white/60">{label}</p>
        <div className="mt-2 flex items-baseline justify-between">
          <p className={`min-w-0 truncate font-mono text-2xl font-bold tabular-nums sm:text-3xl ${valueColor}`}>{display}</p>
          {trend && (
            <span
              className={`font-mono text-sm font-medium ${
                trend.isPositive ? 'text-trace-up' : 'text-trace-down'
              }`}
            >
              {trend.isPositive ? '+' : ''}{trend.value}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
