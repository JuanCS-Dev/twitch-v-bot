import React from 'react';
import { Save } from 'lucide-react';
import { BotConfig } from '../types';

interface SettingsProps {
  config: BotConfig;
  setConfig: (c: BotConfig) => void;
}

const Settings: React.FC<SettingsProps> = ({ config, setConfig }) => {
  
  const handleSystemPromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setConfig({ ...config, systemPrompt: e.target.value });
  };

  const handleTempChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setConfig({ ...config, temperature: parseFloat(e.target.value) });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in pb-10">
      <div className="flex justify-between items-center border-b border-charm-border pb-4">
        <div>
           <h2 className="text-2xl font-bold text-charm-text">Configuration</h2>
           <p className="text-charm-subtext mt-1 text-xs font-mono">/etc/gemini/config.json</p>
        </div>
        <button className="flex items-center gap-2 bg-charm-pink hover:bg-charm-purple text-charm-bg px-4 py-2 rounded font-bold transition-all hover:shadow-glow-pink">
          <Save className="w-4 h-4" />
          <span>SAVE CHANGES</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Core Behavior */}
        <div className="md:col-span-2 space-y-6">
            <div className="bg-charm-card border border-charm-border rounded p-6">
                <div className="flex items-center gap-2 mb-6 text-charm-cyan">
                    <span>⚙️</span>
                    <h3 className="font-bold">CORE_BEHAVIOR</h3>
                </div>

                <div className="space-y-6">
                <div className="group">
                    <label className="block text-xs font-bold text-charm-subtext mb-2 group-focus-within:text-charm-pink transition-colors">
                    SYSTEM_INSTRUCTION
                    </label>
                    <textarea
                    value={config.systemPrompt}
                    onChange={handleSystemPromptChange}
                    rows={6}
                    className="w-full bg-charm-bg border border-charm-border rounded p-3 text-charm-text placeholder-charm-subtext focus:outline-none focus:border-charm-pink focus:ring-1 focus:ring-charm-pink font-mono text-sm leading-relaxed"
                    placeholder="Define bot persona..."
                    />
                </div>

                <div>
                    <label className="flex justify-between text-xs font-bold text-charm-subtext mb-4">
                    <span>THINKING_LEVEL</span>
                    <span className="text-charm-cyan">{config.thinkingLevel}</span>
                    </label>
                    <div className="grid grid-cols-3 gap-3">
                    {['MINIMAL', 'BALANCED', 'DEEP'].map((level) => (
                        <button
                        key={level}
                        onClick={() => setConfig({...config, thinkingLevel: level as any})}
                        className={`
                            px-3 py-2 rounded border text-xs font-bold transition-all
                            ${config.thinkingLevel === level 
                            ? 'bg-charm-cyan/10 text-charm-cyan border-charm-cyan shadow-glow-cyan' 
                            : 'bg-charm-bg text-charm-subtext border-charm-border hover:border-charm-text'}
                        `}
                        >
                        {level}
                        </button>
                    ))}
                    </div>
                </div>
                </div>
            </div>
            
            <div className="bg-charm-card border border-charm-border rounded p-6">
                <div className="flex items-center gap-2 mb-6 text-charm-red">
                    <span>🛡️</span>
                    <h3 className="font-bold">MODERATION_FILTER</h3>
                </div>
                <div>
                    <label className="block text-xs font-bold text-charm-subtext mb-2">
                    BLOCKED_TOKENS
                    </label>
                    <input
                        type="text"
                        value={config.blockedWords.join(', ')}
                        onChange={(e) => setConfig({...config, blockedWords: e.target.value.split(',').map(s => s.trim())})}
                        className="w-full bg-charm-bg border border-charm-border rounded px-3 py-2 text-charm-text focus:outline-none focus:border-charm-red focus:ring-1 focus:ring-charm-red font-mono text-sm"
                    />
                    <p className="mt-2 text-[10px] text-charm-subtext opacity-70">Separate words with commas.</p>
                </div>
            </div>
        </div>

        {/* Sidebar settings */}
        <div className="space-y-6">
             <div className="bg-charm-card border border-charm-border rounded p-6">
                <h3 className="font-bold text-charm-purple mb-4">PARAMETERS</h3>
                
                <div className="space-y-4">
                     <div>
                        <label className="flex justify-between text-xs font-bold text-charm-subtext mb-2">
                            <span>TEMPERATURE</span>
                            <span className="text-charm-purple">{config.temperature}</span>
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.1"
                            value={config.temperature}
                            onChange={handleTempChange}
                            className="w-full h-1 bg-charm-bg rounded-lg appearance-none cursor-pointer accent-charm-purple"
                        />
                        <div className="flex justify-between mt-2 text-[10px] text-charm-subtext">
                            <span>Strict</span>
                            <span>Wild</span>
                        </div>
                    </div>
                    
                    <div className="pt-4 border-t border-charm-border">
                        <label className="flex items-center justify-between text-xs font-bold text-charm-subtext mb-2">
                            <span>BOT_ENABLED</span>
                            <div 
                                onClick={() => setConfig({...config, isEnabled: !config.isEnabled})}
                                className={`w-8 h-4 rounded-full relative cursor-pointer transition-colors ${config.isEnabled ? 'bg-charm-green' : 'bg-charm-subtext'}`}
                            >
                                <div className={`absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all ${config.isEnabled ? 'left-4.5' : 'left-0.5'}`}></div>
                            </div>
                        </label>
                    </div>
                </div>
             </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(Settings);