import React from 'react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { StatusCard } from '../components/StatusCard';
import { AnalyticsData, SentimentData } from '../types';

const mockActivityData: AnalyticsData[] = [
  { time: '18:00', messages: 45, commands: 12 },
  { time: '18:10', messages: 68, commands: 18 },
  { time: '18:20', messages: 120, commands: 35 },
  { time: '18:30', messages: 156, commands: 42 },
  { time: '18:40', messages: 134, commands: 28 },
  { time: '18:50', messages: 98, commands: 20 },
  { time: '19:00', messages: 189, commands: 55 },
];

const mockSentimentData: SentimentData[] = [
  { name: 'Positive', value: 65, fill: '#35D78D' }, // Charm Green
  { name: 'Neutral', value: 25, fill: '#8F8F9D' },  // Charm Subtext
  { name: 'Negative', value: 10, fill: '#FF5F5F' }, // Charm Red
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-charm-bg border border-charm-border p-3 rounded shadow-lg font-mono text-xs">
        <p className="text-charm-subtext mb-2">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ color: entry.color }} className="font-bold">
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-8 animate-fade-in h-full overflow-y-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between border-b border-charm-border pb-4">
        <div>
          <h2 className="text-3xl font-bold text-charm-text">Stats Overview</h2>
          <p className="text-charm-subtext mt-1 text-sm">Real-time telemetry and analytics.</p>
        </div>
        <div className="mt-4 md:mt-0 flex gap-3 text-xs font-mono">
            <span className="px-2 py-1 bg-charm-card border border-charm-border rounded text-charm-cyan">
                LATENCY: 45ms
            </span>
            <span className="px-2 py-1 bg-charm-card border border-charm-border rounded text-charm-pink">
                TOKENS: 4.2k
            </span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatusCard 
          title="Total Messages" 
          value="12.5k" 
          emoji="💬"
          trend="12%"
          trendUp={true}
          color="cyan"
        />
        <StatusCard 
          title="AI Responses" 
          value="3,204" 
          emoji="⚡"
          trend="8%"
          trendUp={true}
          color="pink"
        />
        <StatusCard 
          title="Active Chatters" 
          value="842" 
          emoji="👥"
          trend="2%"
          trendUp={false}
          color="purple"
        />
        <StatusCard 
          title="Mod Actions" 
          value="15" 
          emoji="🛡️"
          trend="0%"
          trendUp={true}
          color="green"
        />
      </div>

      {/* Main Charts Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Activity Chart */}
        <div className="lg:col-span-2 bg-charm-card border border-charm-border rounded p-6 relative">
          <div className="absolute top-0 left-0 px-2 py-1 bg-charm-border text-[10px] text-charm-subtext rounded-br">ACTIVITY_LOG</div>
          <h3 className="text-sm font-bold mb-6 text-charm-text mt-2">Chat vs Command Usage</h3>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockActivityData}>
                <defs>
                  <linearGradient id="colorMessages" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#A06CD5" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#A06CD5" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorCommands" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2AF2FF" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#2AF2FF" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#363646" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  stroke="#8F8F9D" 
                  tick={{fill: '#8F8F9D', fontSize: 10, fontFamily: 'monospace'}}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis 
                  stroke="#8F8F9D" 
                  tick={{fill: '#8F8F9D', fontSize: 10, fontFamily: 'monospace'}}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area 
                  type="step" 
                  dataKey="messages" 
                  stroke="#A06CD5" 
                  fillOpacity={1} 
                  fill="url(#colorMessages)" 
                  strokeWidth={2}
                />
                <Area 
                  type="step" 
                  dataKey="commands" 
                  stroke="#2AF2FF" 
                  fillOpacity={1} 
                  fill="url(#colorCommands)" 
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sentiment Chart */}
        <div className="bg-charm-card border border-charm-border rounded p-6 relative flex flex-col items-center justify-center">
          <div className="absolute top-0 left-0 px-2 py-1 bg-charm-border text-[10px] text-charm-subtext rounded-br">SENTIMENT_ANALYSIS</div>
          <h3 className="text-sm font-bold mb-6 text-charm-text w-full text-left mt-2">Vibe Check</h3>
          <div className="h-64 w-full relative">
             <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={mockSentimentData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={8}
                  dataKey="value"
                  stroke="none"
                >
                  {mockSentimentData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend 
                  verticalAlign="bottom" 
                  height={36} 
                  iconType="circle"
                  wrapperStyle={{ fontSize: '10px', fontFamily: 'monospace' }}
                />
              </PieChart>
            </ResponsiveContainer>
            {/* Center Text */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none pb-8">
               <div className="text-center">
                 <p className="text-3xl font-bold text-charm-green">85%</p>
                 <p className="text-[10px] text-charm-subtext uppercase tracking-widest">Chill</p>
               </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(Dashboard);