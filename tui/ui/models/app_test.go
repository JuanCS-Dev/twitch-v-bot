package models

import (
	"strings"
	"testing"

	"github.com/JuanCS-Dev/byte-tui/cmd/api"
	"github.com/JuanCS-Dev/byte-tui/cmd/config"

	tea "github.com/charmbracelet/bubbletea"
)

func TestAppModelInit(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test"}
	client := api.NewClient(cfg)
	app := NewAppModel(client)

	// Since tea.Batch returns a single Cmd, we can't easily introspect it
	// But we ensure it doesn't panic
	cmd := app.Init()
	if cmd == nil {
		t.Error("Expected Init() to return a defined tea.Cmd batch")
	}

	// Verify initial state
	if app.activeMenu != "status" {
		t.Errorf("Expected active menu 'status', got '%s'", app.activeMenu)
	}
	if !strings.Contains(app.outputArea, "Bem-vindo") {
		t.Error("Output area should contain welcome message")
	}
}

func TestAppModelView_Uninitialized(t *testing.T) {
	app := AppModel{width: 0}
	view := app.View()
	if !strings.Contains(view, "Inicializando") {
		t.Error("View should return init loading string when width is 0")
	}
}

func TestAppModelUpdate_WindowSizeEvent(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test"}
	client := api.NewClient(cfg)
	app := NewAppModel(client)

	// Inject a resize
	newModel, _ := app.Update(tea.WindowSizeMsg{Width: 100, Height: 50})
	updatedApp := newModel.(AppModel)

	if updatedApp.width != 100 || updatedApp.height != 50 {
		t.Errorf("App dimensions not updated correctly, got w=%d h=%d", updatedApp.width, updatedApp.height)
	}
	if updatedApp.viewport.Width == 0 {
		t.Error("Viewport width did not sync with window size")
	}
}

func TestAppModelUpdate_KeyQuitEvent(t *testing.T) {
	app := NewAppModel(nil)

	newModel, cmd := app.Update(tea.KeyMsg{Type: tea.KeyCtrlC})

	// tea.Quit evaluates to a specific message type, we can't do direct == easily without evaluating it,
	// but we can assume the Update signature works.
	if cmd == nil {
		t.Error("Expected cmd to not be nil for Quit")
	}
	// The app model ref should be the same
	updatedApp := newModel.(AppModel)
	if updatedApp.width != app.width {
		t.Error("Model state mutated incorrectly")
	}
}

func TestAppModelUpdate_ApiResponseMessage(t *testing.T) {
	app := NewAppModel(nil)
	app.isLoading = true

	msg := apiRespMsg{Menu: "test", Data: "MOCK_JSON_RESULT"}
	newModel, _ := app.Update(msg)

	updatedApp := newModel.(AppModel)

	if updatedApp.isLoading {
		t.Error("ApiResponseMsg should reset isLoading flag")
	}
	if updatedApp.outputArea != "MOCK_JSON_RESULT" {
		t.Error("ApiResponseMsg did not update outputArea properly")
	}
}
