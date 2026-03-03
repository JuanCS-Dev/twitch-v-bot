package main

import (
	"fmt"
	"os"

	"github.com/JuanCS-Dev/byte-tui/cmd/api"
	"github.com/JuanCS-Dev/byte-tui/cmd/config"
	"github.com/JuanCS-Dev/byte-tui/ui/models"

	tea "github.com/charmbracelet/bubbletea"
)

func main() {
	cfg := config.LoadConfig()
	client := api.NewClient(cfg)

	app := models.NewAppModel(client)

	// AltScreen hides the user's current terminal view and uses full screen
	p := tea.NewProgram(app, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Printf("Error starting Byte TUI: %v\n", err)
		os.Exit(1)
	}
}
