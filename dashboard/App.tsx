import React, { useState, useCallback } from 'react';
import { Menu, Terminal } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Playground from './pages/Playground';
import Settings from './pages/Settings';
import Logs from './pages/Logs';
import Help from './pages/Help';
import { BotConfig } from './types';

// Default Config
const DEFAULT_CONFIG: BotConfig = {
  systemPrompt: "Você é um bot da Twitch brasileiro, energético e 'zueiro'. Responda SEMPRE em Português do Brasil. Use gírias de streamer como 'tankar', 'F no chat', 'cringe', 'base', 'intar', 'GG', 'arrasta pra cima'. Mantenha as respostas curtas (máx 3 frases). Se precisar buscar informações, use seus dados, mas fale como um gamer. Não use markdown complexo, apenas texto simples.",
  temperature: 0.8,
  blockedWords: ["banido", "troll", "bot lixo"],
  isEnabled: true,
  thinkingLevel: 'MINIMAL'
};

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [config, setConfig] = useState<BotConfig>(DEFAULT_CONFIG);

  const toggleMobileMenu = useCallback(() => {
    setIsMobileMenuOpen(prev => !prev);
  }, []);

  const handleSetActiveTab = useCallback((tab: string) => {
    setActiveTab(tab);
    setIsMobileMenuOpen(false); // Close mobile menu on navigate
  }, []);

  const handleSetConfig = useCallback((newConfig: BotConfig) => {
      setConfig(newConfig);
  }, []);

  return (
    <div className="flex h-screen bg-charm-bg overflow-hidden text-charm-text font-mono selection:bg-charm-pink selection:text-white">
      
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={handleSetActiveTab} 
        isMobileMenuOpen={isMobileMenuOpen}
      />

      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Subtle background pattern */}
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none" style={{
            backgroundImage: 'radial-gradient(#363646 1px, transparent 1px)',
            backgroundSize: '24px 24px'
        }}></div>

        {/* Top Header */}
        <header className="h-16 border-b border-charm-border flex items-center justify-between px-6 bg-charm-bg/80 backdrop-blur-sm z-10">
          <button 
            onClick={toggleMobileMenu}
            className="md:hidden text-charm-subtext hover:text-charm-text"
          >
            <Menu className="w-6 h-6" />
          </button>

          <div className="flex items-center gap-2 text-sm text-charm-subtext">
             <Terminal className="w-4 h-4" />
             <span className="hidden sm:inline">root@gemini-bot:~/mcp</span>
          </div>

          <div className="flex items-center space-x-4">
             <div className="hidden md:flex items-center bg-charm-card border border-charm-border px-3 py-1 rounded text-xs">
                <span className="w-2 h-2 rounded-full bg-charm-green mr-2 animate-pulse"></span>
                <span className="text-charm-subtext">gemini-3-flash</span>
             </div>
             
             <div className="flex items-center gap-3">
               <span className="text-sm font-bold text-charm-purple">StreamerBot</span>
               <div className="w-8 h-8 bg-charm-purple text-charm-bg font-bold rounded flex items-center justify-center">
                 SB
               </div>
             </div>
          </div>
        </header>

        {/* Main Content Area - Keep Alive Strategy */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-8 relative z-0">
           <div className={activeTab === 'dashboard' ? 'block h-full' : 'hidden'}>
               <Dashboard />
           </div>
           
           <div className={activeTab === 'playground' ? 'block h-full' : 'hidden'}>
               {/* Pass isVisible to handle scrolling optimization */}
               <Playground config={config} isVisible={activeTab === 'playground'} />
           </div>

           <div className={activeTab === 'settings' ? 'block h-full' : 'hidden'}>
               <Settings config={config} setConfig={handleSetConfig} />
           </div>
           
           <div className={activeTab === 'logs' ? 'block h-full' : 'hidden'}>
               <Logs />
           </div>

           <div className={activeTab === 'help' ? 'block h-full' : 'hidden'}>
               <Help />
           </div>
        </main>
      </div>
      
      {/* Overlay for mobile menu */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/80 z-40 md:hidden backdrop-blur-sm"
          onClick={() => setIsMobileMenuOpen(false)}
        ></div>
      )}
    </div>
  );
};

export default App;