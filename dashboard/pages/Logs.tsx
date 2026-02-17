import React, { useEffect, useState, useRef } from 'react';
import { Pause, Play } from 'lucide-react';

interface LogEntry {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  module: string;
  message: string;
}

const LogItem = React.memo(({ log }: { log: LogEntry }) => (
  <div className="flex gap-2 hover:bg-white/5 py-0.5 px-1 rounded transition-colors group">
    <span className="text-charm-subtext opacity-50 w-20 flex-shrink-0 select-none">{log.timestamp}</span>
    <span className={`w-10 font-bold flex-shrink-0 text-center ${
      log.level === 'INFO' ? 'text-charm-green bg-charm-green/10 rounded-sm' :
      log.level === 'WARN' ? 'text-charm-yellow bg-charm-yellow/10 rounded-sm' : 'text-charm-red bg-charm-red/10 rounded-sm animate-pulse'
    }`}>
      {log.level}
    </span>
    <span className="text-charm-purple w-20 flex-shrink-0 truncate group-hover:text-charm-pink transition-colors">@{log.module}</span>
    <span className="text-charm-text">{log.message}</span>
  </div>
));

const Logs: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Simulate incoming logs
  useEffect(() => {
    if (isPaused) return;

    const interval = setInterval(() => {
      const types: ('INFO' | 'WARN' | 'ERROR')[] = ['INFO', 'INFO', 'INFO', 'WARN', 'INFO', 'ERROR'];
      const modules = ['bot.py', 'gateway', 'gemini_api', 'audit'];
      const messages = [
        'Connecting to Twitch IRC...',
        'Generated response [token_usage: 45]',
        'Heartbeat acknowledged',
        'User command !help parsed',
        'Rate limit approaching (45/60)',
        'Connection dropped, retrying...'
      ];

      const newLog: LogEntry = {
        id: Date.now(),
        timestamp: new Date().toISOString().split('T')[1].replace('Z', ''),
        level: types[Math.floor(Math.random() * types.length)],
        module: modules[Math.floor(Math.random() * modules.length)],
        message: messages[Math.floor(Math.random() * messages.length)]
      };

      setLogs(prev => {
        const next = [...prev, newLog];
        return next.slice(-100); // Keep last 100
      });
      
      // Auto scroll
      if (logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
      }

    }, 800);

    return () => clearInterval(interval);
  }, [isPaused]);

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-[#0c0c0e] border border-charm-border rounded-lg overflow-hidden shadow-2xl font-mono text-xs">
      <div className="p-2 border-b border-charm-border flex justify-between items-center bg-charm-card">
        <div className="flex items-center gap-2 px-2">
          <div className="flex gap-1.5">
             <div className="w-2.5 h-2.5 rounded-full bg-charm-red"></div>
             <div className="w-2.5 h-2.5 rounded-full bg-charm-yellow"></div>
             <div className="w-2.5 h-2.5 rounded-full bg-charm-green"></div>
          </div>
          <span className="ml-3 text-charm-subtext font-bold">tail -f /var/log/gemini-bot.log</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setIsPaused(!isPaused)}
            className="p-1 hover:bg-charm-hover rounded text-charm-text transition-colors"
          >
            {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
          </button>
        </div>
      </div>

      <div 
        ref={logContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-1 bg-[#0c0c0e]"
      >
        {logs.map((log) => (
          <LogItem key={log.id} log={log} />
        ))}
        {logs.length === 0 && (
          <div className="text-charm-subtext opacity-50 italic">_waiting for input stream...</div>
        )}
      </div>
    </div>
  );
};

export default React.memo(Logs);