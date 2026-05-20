import { Card } from '@/components/ui/card';
import { motion } from 'framer-motion';

interface KPIMetricProps {
  label: string;
  value: string;
  color?: string;
  trend?: {
    value: string;
    isPositive: boolean;
  };
}

export function KPIMetric({ label, value, color = '#1DB954', trend }: KPIMetricProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card className="p-6 bg-white/5 backdrop-blur-sm border-white/10 hover:border-white/20 hover:-translate-y-1 transition-all">
        <div className="space-y-2">
          <p className="text-sm text-white/60">{label}</p>
          <div className="flex items-baseline justify-between">
            <p
              className="text-3xl font-bold font-mono"
              style={{ color }}
            >
              {value}
            </p>
            {trend && (
              <span
                className={`text-sm font-medium ${
                  trend.isPositive ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {trend.isPositive ? '+' : ''}{trend.value}
              </span>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
