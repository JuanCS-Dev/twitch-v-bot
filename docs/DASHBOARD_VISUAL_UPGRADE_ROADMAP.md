# Byte Dashboard: Visual & UX Upgrade Roadmap (2026)

**Data:** 25/02/2026
**Visão:** Transformar o dashboard utilitário atual em uma central de comando de elite ("Command Center"), mesclando estética cyberpunk/neon com UX profissional de alta legibilidade. O objetivo é causar impacto visual ("wow factor") através de **extremo refinamento visual, simetria absoluta, microanimações intencionais e tipografia de mestre**, mantendo a performance impecável do Vanilla JS/CSS. Não haverá espaço para desalinhamentos de 1px ou animações "duras".

---

## 1. Identidade Visual, Branding e Tipografia (O "Byte" Feel)

A identidade de uma IA autônoma não se faz apenas com cores, mas com a precisão matemática da sua apresentação.

### 1.1 Paleta de Cores (Cyber-Tactical)
Migrar de um tema escuro genérico para um "Deep Space" com sotaques neon perfeitamente equilibrados.
*   **Backgrounds:** `#09090B` (Base), `#121216` (Surface), `#1C1C22` (Elevated).
*   **Accent Primário:** Neon Cyan/Teal (`#00F0FF`) — Representa o "cérebro" da IA, autonomia ativa. Usar glows ultra-suaves (opacidades 5% e 10%) para evitar ofuscamento.
*   **Status Semânticos:**
    *   OK/Heatlh: `#39FF14` (Neon Green)
    *   Warn: `#FFD700` (Cyber Yellow)
    *   Error/Risk: `#FF003C` (Laser Red)

### 1.2 Mestria Tipográfica e Simetria
A tipografia será o diferencial entre um projeto amador e uma interface de elite de 2026.
*   **Display / Headers:** `Space Grotesk` ou `Outfit`. Escala modular rigorosa (ex: base 1.200 ratio).
*   **Logs / Monospace:** `JetBrains Mono` com ligatures ativadas. Os logs devem alinhar matematicamente.
*   **Espaçamento e Simetria:** Adoção estrita de um grid de 4px ou 8px (tokens `--spacing-1` a `--spacing-8`). Zero margens arbitrárias. Todo card, botão e gap deve respeitar a escala exata para criar harmonia absoluta na tela.

---

## 2. Refinamento Visual Máximo: Cards e Design System

Os componentes base (`.card`, `.panel`) devem exalar qualidade premium.

### 2.1 Cards de Qualidade Extrema
*   **Estética "Glass" e Profundidade:** Combinar `backdrop-filter: blur(12px)` na `.topbar` com `box-shadow` em multi-camadas (sombras de 1px para definição + sombras de 12px para profundidade ambiente).
*   **Bordas Inteligentes:** Substituir bordas sólidas pesadas por bordas semitransparentes (`rgba(255,255,255,0.08)`) com backgrounds em degradê radial sutis que reagem ao hover (`background-image: radial-gradient(...)`).
*   **Refino no Detalhe:** O `border-radius` externo de um card deve ser matematicamente alinhado com o `border-radius` interno de seus filhos (Nested Radius Formula: `Outer - Padding = Inner`).

---

## 3. Motion Choreography (Microanimações Intencionais)

O dashboard atual é estático. A interface deve parecer "viva" e orgânica, refletindo o processamento em tempo real da IA, mas cada animação deve ter um propósito (Coreography, não distração).

### 3.1 Transições de Estado de Elite (2026 Standard)
*   **`@starting-style` nativo:** Animar a entrada e saída de novos logs no `hudMessagesList` e `analyticsLogsContainer` com transições suaves de altura e opacidade (slide-in com fade-in).
*   **Spring Physics Simuladas:** Abolir os `ease-out` básicos. Utilizar `cubic-bezier` customizados (ex: `cubic-bezier(0.175, 0.885, 0.32, 1.275)`) em todo botão, hover de card e modal para criar um efeito de "peso e inércia" profissional.

### 3.2 Feedback Visual e "Breathing"
*   Quando o `AutonomyRuntime` processar um tick, os botões relacionados não devem apenas piscar, devem "respirar" (pulse animation com transição de opacidade da borda e sombra).
*   O chip de conexão (`#connectionState`) terá um "breathing dot" (um pseudo-elemento com animação de `scale` e `opacity` infinita) para passar a sensação de um pulso orgânico da IA.

---

## 4. Upgrades de UX e Data Viz (Data Density)

### 4.1 Painel de Inteligência Visual
*   **Sentiment Engine:** Usar barras de progresso CSS modernas (estilizadas via pseudo-elementos) com animações de largura (`width`) transitionadas para mostrar o ratio Positivo/Negativo em tempo real.
*   **Autonomy Budget:** Mostrar o "Budget" como um donut chart circular simples (SVG inserido no JS), animando o `stroke-dashoffset` ao ser atualizado.

### 4.2 Control Plane (Ergonomia Tátil)
*   Substituir inputs de checkbox genéricos por Toggle Switches desenhados à mão no CSS, com a "bolinha" usando a curva bezier elástica descrita acima.
*   Virtualização na DOM: Focar em performance mantendo no máximo 100 itens renderizados no DOM dos logs para evitar layout thrashing durante microanimações pesadas.

### 4.3 Responsividade Adaptativa (Desktop-First)
O streamer opera a central de comando primordialmente via desktop (OBS, múltiplos monitores), mas frequentemente utiliza um tablet ou celular como tela de apoio secundária (ex: para ler a fila de riscos ou stats rápidos).
*   **Grid Fluido:** O layout deve utilizar CSS Grid com `auto-fit` e `minmax()` para colapsar graciosamente de um grid multi-colunas para uma coluna única em telas menores, sem media queries arbitrárias sempre que possível.
*   **Alvos de Toque (Touch Targets):** Em viewports menores (mobile/tablet), os botões e os novos Toggle Switches devem garantir um alvo mínimo de 44x44px (padrão Apple/Material) para evitar miss-clicks pelo streamer no calor da live.
*   **Tipografia Fluida:** O uso de `clamp()` (ex: `font-size: clamp(1rem, 2vw, 1.25rem);`) garantirá que a hierarquia tipográfica se mantenha legível em um iPhone sem quebrar os cards complexos desenhados para um monitor 4K.

### 4.4 Redução de Carga Cognitiva e Layout Intuitivo
O dashboard atual sofre de "Data Dump" (exposição massiva de variáveis úteis apenas para desenvolvedores), tornando a curva de aprendizado hostil para operadores e streamers.
*   **Progressive Disclosure:** Esconder configurações profundas do *Control Plane* e do *Intelligence Overview* atrás de um accordion ou modal ("Advanced Settings"). Mostrar por padrão apenas o que requer atenção ou ação imediata.
*   **Agrupamento Semântico (Chunking):** Mover controles relacionados para "ilhas" de contexto. Por exemplo, controles de HUD devem estar agrupados com o HUD, e não perdidos em um "Control Plane" genérico.
*   **Destaque Visual Baseado em Ação (Action-Driven UI):** A "Fila de Riscos" (Action Queue) deve dominar o peso visual da tela (tamanho, contraste, animação de atenção) quando houver itens pendentes, e "sumir" graciosamente quando vazia, direcionando a atenção do operador organicamente sem precisar ler blocos de texto.
*   **Iconografia Funcional:** Substituir *labels* textuais longas por ícones consistentes (Lucide React style, implementados em SVG) para ações repetitivas (Aprovar, Rejeitar, Ignorar), acelerando o reconhecimento em live.

---

## 5. Estratégia de Implementação (Faseada e Segura)

*   **Fase 1: Fundação Tipográfica e Simetria (✅ CONCLUÍDO)**
    *   Atualizar `tokens.css` com as novas cores, sistema de fontes (Space Grotesk + JetBrains) e forçar a escala de 8px global.
    *   Atualizar `base.css` com tipografia fluida e reset.
*   **Fase 2: Refinamento dos Cards e Componentes (✅ CONCLUÍDO)**
    *   Refatorar `.card`, `.panel` e `.btn` em `components.css`. Aplicar a fórmula de nested radius e as multi-sombras.
*   **Fase 3: Coreografia de Motion e Alinhamentos Finais (✅ CONCLUÍDO)**
    *   Adicionar as microanimações `@starting-style` nas listas dinâmicas e o `cubic-bezier` global.
    *   *Adendo de Refino Tático:* Correção de `align-items: start` para altura dinâmica de cards, espaçamento estrutural com `display: contents`, e botão `.btn-sm` no Controle de Canais.
*   **Fase 4: Upgrades de UX (Charts e Toggles) (✅ CONCLUÍDO)**
    *   Substituir KVs por SVGs dinâmicos e refinar os inputs do Control Plane.

---
*Plano arquitetado sob os princípios Frontend Elite 2026. A regra de ouro é: "O detalhe não é o detalhe, o detalhe é o design". Foco em tipografia impecável, animações físicas e impacto visual absoluto sem degradar a performance.*
