import React from 'react';
import { Terminal, Search, Shield, Zap, Image, Volume2 } from 'lucide-react';

const commands = [
  {
    category: "IA & Conversa",
    icon: <Zap className="w-4 h-4" />,
    color: "text-charm-pink",
    borderColor: "border-charm-pink",
    items: [
      { cmd: "!bot <msg>", desc: "Fala diretamente com a IA Gemini. Responde rápido.", permission: "Todos" },
      { cmd: "!historia <tema>", desc: "Gera uma história curta e criativa sobre o tema.", permission: "Subs" },
      { cmd: "!traduzir <texto>", desc: "Traduz o texto para Português PT-BR.", permission: "Todos" }
    ]
  },
  {
    category: "Multimodal (Img/Áudio)",
    icon: <Image className="w-4 h-4" />,
    color: "text-charm-purple",
    borderColor: "border-charm-purple",
    items: [
      { cmd: "!imaginar <prompt>", desc: "Gera uma imagem quadrada (1:1). (NLP: 'Desenhe...')", permission: "Todos" },
      { cmd: "!falar <texto>", desc: "Gera áudio falado. (NLP: 'Fale...', 'Diga...')", permission: "Todos" },
    ]
  },
  {
    category: "Pesquisa (Grounding)",
    icon: <Search className="w-4 h-4" />,
    color: "text-charm-cyan",
    borderColor: "border-charm-cyan",
    items: [
      { cmd: "!pesquisa <termo>", desc: "Busca informações atualizadas no Google.", permission: "Todos" },
      { cmd: "!wiki <termo>", desc: "Resumo rápido de um tópico específico.", permission: "Todos" },
      { cmd: "!clima <cidade>", desc: "Mostra a previsão do tempo atual via Search.", permission: "Todos" }
    ]
  },
  {
    category: "Sistema & Mod",
    icon: <Shield className="w-4 h-4" />,
    color: "text-charm-green",
    borderColor: "border-charm-green",
    items: [
      { cmd: "!limpar", desc: "Limpa o contexto da conversa da IA (Reset).", permission: "Mods" },
      { cmd: "!config", desc: "Mostra a configuração atual (temp/modelo).", permission: "Mods" },
      { cmd: "!status", desc: "Verifica latência e uptime do bot.", permission: "Todos" }
    ]
  }
];

const Help: React.FC = () => {
  return (
    <div className="space-y-8 animate-fade-in pb-10">
       {/* Header */}
       <div className="border-b border-charm-border pb-4">
          <h2 className="text-2xl font-bold text-charm-text">Manual de Comandos</h2>
          <p className="text-charm-subtext mt-1 text-xs font-mono">Referência de sintaxe v2.0 - Prefix: (!)</p>
       </div>

       {/* Command Grid */}
       <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {commands.map((group, idx) => (
             <div key={idx} className={`bg-charm-card border border-charm-border rounded-lg p-5 hover:border-opacity-50 transition-all hover:shadow-lg group relative overflow-hidden`}>
                <div className={`flex items-center gap-2 mb-4 ${group.color}`}>
                   {group.icon}
                   <h3 className="font-bold text-sm tracking-wide uppercase">{group.category}</h3>
                </div>

                <div className="space-y-4 relative z-10">
                   {group.items.map((item, i) => (
                      <div key={i} className="group/item">
                         <div className="flex justify-between items-baseline mb-1">
                            <code className={`text-xs font-bold bg-charm-bg px-2 py-0.5 rounded border border-charm-border ${group.color} bg-opacity-10 select-all`}>
                               {item.cmd}
                            </code>
                            <span className="text-[10px] text-charm-subtext uppercase border border-charm-border px-1 rounded bg-charm-bg">
                               {item.permission}
                            </span>
                         </div>
                         <p className="text-xs text-charm-subtext pl-1 border-l-2 border-charm-border group-hover/item:border-charm-text transition-colors">
                            {item.desc}
                         </p>
                      </div>
                   ))}
                </div>
                
                {/* Decoration */}
                <div className={`absolute -right-6 -bottom-6 w-24 h-24 bg-gradient-to-tl from-${group.color.split('-')[2]} to-transparent opacity-5 rounded-full pointer-events-none`}></div>
             </div>
          ))}
       </div>

       {/* FAQ / Notes */}
       <div className="bg-charm-bg border border-charm-border border-dashed rounded p-6">
           <div className="flex items-start gap-4">
              <div className="p-2 bg-charm-purple/10 rounded text-charm-purple border border-charm-purple/20">
                 <Terminal className="w-6 h-6" />
              </div>
              <div>
                 <h3 className="text-charm-text font-bold mb-2">Nota sobre Multimodal (Áudio/Imagem)</h3>
                 <p className="text-charm-subtext text-xs leading-relaxed mb-2">
                    Os comandos <span className="text-charm-purple font-bold">!imaginar</span> e <span className="text-charm-purple font-bold">!falar</span> utilizam modelos especializados (Gemini 2.5). 
                 </p>
                 <ul className="list-disc list-inside text-xs text-charm-subtext space-y-1 mb-2">
                    <li>Áudio: Gera arquivo WAV (24kHz) que pode ser reproduzido diretamente.</li>
                    <li>NLP: Você pode dizer "Fale olá" ou "Desenhe um gato" sem usar o prefixo (!).</li>
                 </ul>
              </div>
           </div>
       </div>
    </div>
  );
};

export default React.memo(Help);