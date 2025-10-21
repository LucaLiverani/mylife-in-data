'use client';

import { Card } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { Search, Map, TrendingUp, TrendingDown } from 'lucide-react';
import Link from 'next/link';

interface ServiceCardProps {
  title: string;
  iconName: 'music' | 'youtube' | 'search' | 'map';
  stats: Array<{ label: string; value: string; trend?: number }>;
  color: string;
  href: string;
}

const iconMap = {
  music: () => (
    <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
    </svg>
  ),
  youtube: () => (
    <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
    </svg>
  ),
  search: Search,
  map: Map,
};

export function ServiceCard({ title, iconName, stats, color, href }: ServiceCardProps) {
  const Icon = iconMap[iconName];
  return (
    <Link href={href}>
      <motion.div
        whileHover={{ scale: 1.02, y: -4 }}
        whileTap={{ scale: 0.98 }}
        transition={{ duration: 0.2 }}
      >
        <Card
          className="p-6 bg-white/5 backdrop-blur-sm border-white/10 hover:border-white/20 transition-all duration-300 cursor-pointer group"
          style={{
            boxShadow: '0 0 0 rgba(0,0,0,0.3)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = `0 20px 60px ${color}60, 0 0 40px ${color}40`;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = '0 0 0 rgba(0,0,0,0.3)';
          }}
        >
          <div className="flex flex-col">
            {/* Icon and Title */}
            <div className="flex items-center gap-4 mb-4">
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform"
                style={{ backgroundColor: color }}
              >
                <Icon />
              </div>
              <h3 className="text-xl font-bold text-white">{title}</h3>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4">
              {stats.slice(0, 2).map((stat, i) => (
                <div key={i} className="flex flex-col">
                  <div
                    className="text-2xl font-semibold font-mono mb-1"
                    style={{ color }}
                  >
                    {stat.value}
                  </div>
                  <div className="text-xs text-white/60 mb-2">{stat.label}</div>
                  {stat.trend !== undefined && (
                    <div className="flex items-center gap-1">
                      {stat.trend >= 0 ? (
                        <TrendingUp className="w-4 h-4 text-green-500" />
                      ) : (
                        <TrendingDown className="w-4 h-4 text-red-500" />
                      )}
                      <span
                        className={`text-xs font-semibold ${
                          stat.trend >= 0 ? 'text-green-500' : 'text-red-500'
                        }`}
                      >
                        {Math.abs(stat.trend)}%
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Card>
      </motion.div>
    </Link>
  );
}
