# Plano de Implementação: Byte Agent TUI (Go + Charm)

Este documento descreve a arquitetura e as etapas de desenvolvimento de uma Terminal User Interface (TUI) interativa e moderna para o **Byte Agent**, construída inteiramente em Go usando o ecossistema [Charmbracelet](https://charm.sh/).

**Objetivo Central:** Fornecer monitoramento ao vivo, interação dinâmica via chat e controle operacional COMPLETO sobre a instância gerenciada do agente, espelhando perfeitamente os 43 comandos da nova `bytecli` em uma experiência fluida, contínua e bonita (sem overengineering e sem bater cabeça).

---

## 🏗 Arquitetura (O "Caminho Feliz" com Charm)

A interface será guiada pelo The Elm Architecture (TEA) fornecida pela biblioteca `Bubble Tea`. Evitaremos complexidade adotando um painel clássico e funcional.

### 1. Dependências Core
- **`charm.land/bubbletea/v2`**: Motor de estado, loop de eventos (teclado) e renderização assíncrona (Cursed Renderer ultrarrápido).
- **`charm.land/lipgloss/v2`**: Estilização fluida e semântica de terminal (Cores vivas, bordas arredondadas, painéis de vidro flexíveis).
- **`charm.land/bubbles/v2`**: Componentes prontos que nos salvam tempo (`textinput` para o chat, `list` para selecionar comandos, `viewport` para logs e histórico).
- **`net/http` + Goroutines**: Cliente assíncrono espelhando exatamente a lógica de `cli.client` do Python (lendo `BYTE_API_URL`, `BYTE_ADMIN_TOKEN`, `BYTE_DASHBOARD_ADMIN_TOKEN` ou `HF_TOKEN`). Nenhuma trava na interface enquanto uma requisição remota é feita.

### 2. Visão do Layout Base (Wireframe TUI)
O terminal ocupará toda a tela dividida em 3 zonas estáticas (usando `lipgloss.JoinVertical` e `JoinHorizontal`):

```text
╭─────────────────────────────────────────────────────────────╮
│ 🚀 BYTE AGENT [ONLINE] | ❤ Sentiment: 8.5 | 💰 Rev: $120.0  │ <- HEADER (Monitoramento Rápido + Banner Charm)
╰─────────────────────────────────────────────────────────────╯
╭───────────────────────────┬─────────────────────────────────╮
│ [ MAIN MENU ]             │ [ CHAT / ACTION HISTORY ]       │ <- CORPO PRINCIPAL
│ > 🟢 Status               │ [Agent]: Iniciando nova goal... │
│   🕹️ Controle            │ [User]: !ajuda                  │
│   🎯 Goals (5 ativos)     │ [Agent/Ação]: Aprovada!         │
│   🧠 Memória              │ [Agent]: Obrigado pelo sub!     │
│   ⚡ Fila de Ações (2💬)   │                                 │
│   📺 Config Canal         │                                 │
│                           │                                 │
│ [ INFO PANEL ]            │                                 │
│ CPU: 12% | RAM: 140MB     │                                 │
╰───────────────────────────┴─────────────────────────────────╯
╭─────────────────────────────────────────────────────────────╮
│ 💬 Enviar prompt/comando para a IA...  [ Enter = Enviar ]   │ <- FOOTER (Input interativo constante)
╰─────────────────────────────────────────────────────────────╯
```

---

## 🛠️ Fases de Implementação

### Fase 1: Setup e Infraestrutura Base (O Alicerce)
- **Golang Module**: `go mod init github.com/JuanCS-Dev/byte-tui`
- **Config Loader**: Replicar a mesma hierarquia da CLI. Ler `~/.byterc`, depois Variáveis de Ambiente (`BYTE_API_URL`, `BYTE_ADMIN_TOKEN`, `BYTE_DASHBOARD_ADMIN_TOKEN`, `HF_TOKEN`), depois Flags locais do Go.
- **Client Assíncrono (`/pkg/api`)**: Módulo Go para conversar com as APIs RESTful do painel. **Crítico:** Todas as requisições à API devem gerar "*Commands*" (mensagens no padrão Bubble Tea) para não freezar a TUI (goroutines disparando mensagens para a `Update function`).

### Fase 2: Layout Estático e O Banner Lipgloss
- **Estilos Globais (`/ui/styles`)**: Definir as cores vibrantes do Byte (usando Lipgloss `Color("#FF5F87")`, etc.), formatos de caixas com padding e margens.
- **Banner ASCII**: Usar a consolidade biblioteca de mercado `github.com/common-nighthawk/go-figure` para gerar o banner com a palavra "Byte" logo no topo, sem tentar inventar a roda com strings hardcoded. Esse output será encapsulado em um componente Lipgloss para coloração.
- **Header Component (`/ui/components/header`)**: A faixa superior chamativa contendo o banner e indicadores. Implementar um _Tick Component_ (um loop que faz requests minúsculos a cada 5 segundos para a rota `/health` e atualiza a bolinha Verde/Vermelha).

### Fase 3: Navegação Principal (`/ui/components/sidebar`)
- Implementar lista navegável (`bubbles/list`) contendo os blocos operacionais: `Dashboard`, `Ações Pendentes`, `Goals`, `Painel de Controle`.
- Ao apertar `Enter` num item, o foco principal muda a aba para renderizar as views correspondentes.

### Fase 4: O Coração - Área de Interação e Console (`/ui/components/viewport`)
- O lado direito grandão será o `bubbles/viewport`.
- Em background, uma corrotina puxa `/api/observability/history` e `/api/action-queue` de forma intervalada e formata as mensagens numa stream rolável, como se fosse um console do terminal mesmo colorido.

### Fase 5: Input Persistente (Chat e Comandos da Linha Inferior)
- Implementar `bubbles/textinput` permanentemente focado ou facilmente chamável com `i` (Vim-style).
- Sempre que você pressionar `Enter`: envia os conteúdos do Input direto para a rota `/api/chat/send` (que já existe e engatilha o pipeline inteiro do bot via POST) e limpa o campo. Um *spinner* (componente Bubble) vai girar até a API dar o OK, mostrando o prompt enviado no log superior.

### Fase 6: Modal Actions / Janelas Livres
- E as aprovações pendentes? Se o Menu estiver em `Ações Pendentes`, a área direita muda e renderiza uma lista para você apertar `A` (Approve) ou `R` (Reject) sobre a ação atual (isso chama a API: `/api/action-queue/{id}/decision`).
- Modais rápidos se sobrepondo (camada z-index flex) caso os forms de edição (`Goals`, `Playbooks`) precisem ser exibidos sem quebrar o grid (um simples form de text-fields empilhados centralizado na tela).

---

## 🔑 Pontos Fortes Desta Arquitetura
1. **Zero Lixo de UI (Sem Webview):** É 100% nativa, super rápida (roda direto pelo terminal onde estiver programando no _Neovim_ ou no M2).
2. **Reaproveitamento Imediato:** Como a CLI já mastigou as rotas e padronizou as payloads (`json`), o cliente em Go apenas consome e injeta no BubbleTea TEA model. Autenticação e Proxy do HF token estarão intactos.
3. **Escalável:** Os componentes Lipgloss (`View() string`) são modulares. Criar uma nova dashboard "Sentiment" se resume a montar um layout CSS e jogar numa condicional `switch case`.

---

**Status deste Documento:** PRONTO PARA EXECUÇÃO. Quando desejar a implementação, procederemos à inicialização do diretório e escrita do `main.go` no padrão Bubble Tea.
