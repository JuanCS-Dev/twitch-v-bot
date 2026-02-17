import React from 'react';

interface StatusCardProps {
  title: string;
  value: string | number;
  emoji: string;
  trend?: string;
  trendUp?: boolean;
  color?: 'pink' | 'cyan' | 'purple' | 'green';
}

export const StatusCard: React.FC<StatusCardProps> = React.memo(({ title, value, emoji, trend, trendUp, color = 'pink' }) => {
  const borderColor = 
    color === 'cyan' ? 'border-charm-cyan' : 
    color === 'purple' ? 'border-charm-purple' : 
    color === 'green' ? 'border-charm-green' : 
    'border-charm-pink';
    
  const glowClass = 
    color === 'cyan' ? 'hover:shadow-glow-cyan' : 
    color === 'pink' ? 'hover:shadow-glow-pink' : '';

  return (
    <div className={`
      bg-charm-card border border-charm-border p-5 rounded-md relative overflow-hidden group transition-all duration-300 hover:-translate-y-1 hover:border-opacity-50
      hover:border-${color === 'pink' ? 'charm-pink' : 'charm-cyan'} ${glowClass}
    `}>
      <div className={`absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity text-6xl select-none`}>
        {emoji}
      </div>
      
      <div className="relative z-10">
        <h4 className="text-charm-subtext text-xs uppercase font-bold tracking-widest mb-2">{title}</h4>
        <div className="flex items-baseline gap-2">
           <span className="text-3xl font-bold text-charm-text">{value}</span>
        </div>
        
        {trend && (
          <div className="mt-3 flex items-center text-xs font-mono">
            <span className={`${trendUp ? 'text-charm-green' : 'text-charm-red'}`}>
              {trendUp ? '▲' : '▼'} {trend}
            </span>
            <span className="text-charm-subtext ml-2 opacity-60">/ hour</span>
          </div>
        )}
      </div>
      
      {/* Decorative corner */}
      <div className={`absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 ${borderColor} opacity-0 group-hover:opacity-100 transition-opacity rounded-br`}></div>
    </div>
  );
});