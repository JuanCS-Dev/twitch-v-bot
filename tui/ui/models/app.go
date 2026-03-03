package models

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/JuanCS-Dev/byte-tui/cmd/api"
	"github.com/JuanCS-Dev/byte-tui/ui/styles"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type AppModel struct {
	client     *api.Client
	width      int
	height     int
	menuList   list.Model
	viewport   viewport.Model
	textInput  textinput.Model
	activeMenu string
	outputArea string
	headerStr  string
	isLoading  bool
}

// Custom items for Bubble Tea List
type item struct {
	title, desc string
	cmdId       string
}

func (i item) Title() string       { return i.title }
func (i item) Description() string { return i.desc }
func (i item) FilterValue() string { return i.title }

// Msg structs for tea.Cmd
type tickMsg time.Time
type apiRespMsg struct {
	Menu string
	Data string
}
type errMsg struct{ err error }

func NewAppModel(client *api.Client) AppModel {
	// Sidebar List
	items := []list.Item{
		item{title: "🟢 Status", desc: "View agent / health status", cmdId: "status"},
		item{title: "🎯 Goals", desc: "List active goals", cmdId: "goals"},
		item{title: "⚡ Actions", desc: "View action queue", cmdId: "actions"},
		item{title: "📺 Config", desc: "Channel Config", cmdId: "config"},
		item{title: "🧠 Memory", desc: "View Semantic Memory", cmdId: "memory"},
		item{title: "🎭 Persona", desc: "View Agent Persona Profile", cmdId: "persona"},
	}

	m := list.New(items, list.NewDefaultDelegate(), 30, 14)
	m.Title = "Main Menu"
	m.SetShowStatusBar(false)
	m.SetFilteringEnabled(false)

	// Input
	ti := textinput.New()
	ti.Placeholder = "Digite um comando para o agente ou mande no chat..."
	ti.Focus()
	ti.CharLimit = 256
	ti.Width = 60

	// Viewport
	vp := viewport.New(80, 20)
	vp.SetContent("Loading...")

	// Header Banner - custom ASCII art
	header := styles.Banner

	return AppModel{
		client:     client,
		menuList:   m,
		textInput:  ti,
		viewport:   vp,
		activeMenu: "status",
		headerStr:  header,
		outputArea: "Bem-vindo ao Byte Agent TUI.\nPressione `Enter` no menu à esquerda para carregar dados.\nOu digite no chat abaixo.",
	}
}

func (m AppModel) Init() tea.Cmd {
	return tea.Batch(
		textinput.Blink,
		m.fetchAPI("status"),
		doTick(),
	)
}

func doTick() tea.Cmd {
	return tea.Tick(time.Second*5, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

// Commands to fetch data async
func (m AppModel) fetchAPI(cmdId string) tea.Cmd {
	return func() tea.Msg {
		var path string
		switch cmdId {
		case "status":
			path = "/health"
		case "goals":
			path = "/api/control-plane"
		case "actions":
			path = "/api/action-queue"
		case "config":
			path = "/api/channel-config"
		case "memory":
			path = "/api/semantic-memory"
		case "persona":
			path = "/api/persona-profile"
		default:
			return apiRespMsg{Menu: cmdId, Data: "Unknown command"}
		}

		data, err := m.client.Get(path)
		if err != nil {
			return apiRespMsg{Menu: cmdId, Data: fmt.Sprintf("Error: %v", err)}
		}

		// Humanize Status response
		if cmdId == "status" {
			if data["status"] == "AGENT_ONLINE" {
				return apiRespMsg{Menu: cmdId, Data: "✅ AGENTE ONLINE\n\nTodos os sistemas operacionais.\nAguardando interações via Twitch/API."}
			}
		}

		// Fallback to formatted JSON for complex objects, but readable
		jsonBytes, _ := json.MarshalIndent(data, "", "  ")
		return apiRespMsg{Menu: cmdId, Data: string(jsonBytes)}
	}
}

func (m AppModel) postChatAPI(text string) tea.Cmd {
	return func() tea.Msg {
		if strings.TrimSpace(text) == "" {
			return nil
		}
		data, err := m.client.Post("/api/chat/send", map[string]interface{}{
			"text": text,
		})
		if err != nil {
			return apiRespMsg{Menu: "chat", Data: fmt.Sprintf("Chat Error: %v", err)}
		}
		jsonBytes, _ := json.MarshalIndent(data, "", "  ")
		return apiRespMsg{Menu: "chat", Data: "Message Sent!\n\nResponse:\n" + string(jsonBytes)}
	}
}

func (m AppModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmds []tea.Cmd
	var cmd tea.Cmd

	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			return m, tea.Quit
		case "up", "down", "k", "j":
			m.menuList, cmd = m.menuList.Update(msg)
			cmds = append(cmds, cmd)
		case "enter":
			// If input is focused and has text, send chat
			if m.textInput.Focused() && m.textInput.Value() != "" {
				val := m.textInput.Value()
				m.textInput.SetValue("")
				m.isLoading = true
				m.outputArea = "Sending prompt: " + val + "...\n"
				m.viewport.SetContent(m.outputArea)
				cmds = append(cmds, m.postChatAPI(val))
			} else {
				// Otherwise, trigger the selected menu item
				if i, ok := m.menuList.SelectedItem().(item); ok {
					m.activeMenu = i.cmdId
					m.isLoading = true
					m.outputArea = "Fetching " + i.title + "..."
					m.viewport.SetContent(m.outputArea)
					cmds = append(cmds, m.fetchAPI(i.cmdId))
				}
			}
		}

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.viewport.Width = msg.Width - m.menuList.Width() - 10
		m.viewport.Height = msg.Height - 15 - 5 // Header + Footer height subtracted
		m.viewport.SetContent(m.outputArea)

	case apiRespMsg:
		m.isLoading = false
		m.outputArea = msg.Data
		m.viewport.SetContent(m.outputArea)

	case tickMsg:
		// Optional: We could background refresh the status
		cmds = append(cmds, doTick())
	}

	m.textInput, cmd = m.textInput.Update(msg)
	cmds = append(cmds, cmd)

	return m, tea.Batch(cmds...)
}

func (m AppModel) View() string {
	if m.width == 0 {
		return "Inicializando..."
	}

	// 1. Header
	header := styles.HeaderStyle.
		Width(m.width).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(styles.ColorPrimary).
		Render(lipgloss.NewStyle().Foreground(styles.ColorSecondary).Render(m.headerStr))

	// 2. Sidebar
	sidebar := styles.BaseBox.
		Height(m.viewport.Height).
		Render(m.menuList.View())

	// 3. Viewport (Content)
	contentBox := styles.ActiveBox.
		Width(m.width - lipgloss.Width(sidebar) - 4).
		Height(m.viewport.Height).
		Render(m.viewport.View())

	mainArea := lipgloss.JoinHorizontal(lipgloss.Top, sidebar, contentBox)

	// 4. Input Footer
	loadingStr := ""
	if m.isLoading {
		loadingStr = lipgloss.NewStyle().Foreground(styles.ColorPrimary).Render(" [⏳ Processando...]")
	}
	inputBox := styles.DimBox.
		Width(m.width - 2).
		Render(m.textInput.View() + loadingStr)

	// Join all
	return lipgloss.JoinVertical(
		lipgloss.Left,
		header,
		mainArea,
		inputBox,
	)
}
