import React from 'react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isMobileMenuOpen: boolean;
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab, isMobileMenuOpen }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Overview', icon: '📊', desc: 'Stats' },
    { id: 'playground', label: 'Playground', icon: '🧪', desc: 'Test' },
    { id: 'logs', label: 'Ticker', icon: '📠', desc: 'Logs' },
    { id: 'settings', label: 'Config', icon: '⚙️', desc: 'Edit' },
    { id: 'help', label: 'Manual', icon: '❓', desc: 'Help' },
  ];

  return (
    <aside 
      className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-charm-bg border-r border-charm-border transform transition-transform duration-300 ease-in-out
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        md:relative md:translate-x-0 font-mono
      `}
    >
      <div className="flex flex-col h-full">
        <div className="h-16 border-b border-charm-border flex items-center px-6">
          <span className="text-charm-pink text-xl font-bold">Gemini</span>
          <span className="text-charm-text text-xl">MCP</span>
          <span className="text-charm-subtext ml-2 text-xs border border-charm-border px-1 rounded">v2.0</span>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {menuItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`
                  w-full text-left px-4 py-3 rounded-md transition-all duration-200 flex items-center justify-between group
                  ${isActive 
                    ? 'bg-charm-card text-charm-pink border border-charm-pink shadow-glow-pink' 
                    : 'text-charm-subtext hover:text-charm-text hover:bg-charm-hover border border-transparent'}
                `}
              >
                <div className="flex items-center">
                  <span className="mr-3 text-lg group-hover:scale-110 transition-transform">{item.icon}</span>
                  <span className="font-medium tracking-tight">{item.label}</span>
                </div>
                {isActive && <span className="text-xs animate-pulse">●</span>}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-charm-border">
           <div className="bg-charm-card border border-charm-border p-3 rounded text-xs space-y-2">
              <div className="flex justify-between">
                 <span className="text-charm-subtext">STATUS</span>
                 <span className="text-charm-green font-bold flex items-center gap-1">
                   ONLINE ⚡
                 </span>
              </div>
              <div className="w-full bg-charm-bg h-1 rounded overflow-hidden">
                 <div className="bg-charm-cyan h-full w-[45%]"></div>
              </div>
              <div className="flex justify-between text-[10px] text-charm-subtext">
                <span>MEM: 45%</span>
                <span>CPU: 12%</span>
              </div>
           </div>
        </div>
      </div>
    </aside>
  );
};

export default React.memo(Sidebar);