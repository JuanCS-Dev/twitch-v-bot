package styles

import (
	"github.com/charmbracelet/lipgloss"
)

var (
	// Colors
	ColorPrimary   = lipgloss.Color("#FF5F87") // Byte Pink
	ColorSecondary = lipgloss.Color("#00FFFF") // Cyan
	ColorSuccess   = lipgloss.Color("#00FF00")
	ColorError     = lipgloss.Color("#FF0000")
	ColorDim       = lipgloss.Color("#555555")
	ColorText      = lipgloss.Color("#FFFFFF")
	ColorBgDark    = lipgloss.Color("#111111")

	// ═══════════════════════════════════════════════════════════════════
	//                        BYTE BANNER ART (v2 Blocky)
	// ═══════════════════════════════════════════════════════════════════
	Banner = `
 ██████╗ ██╗   ██╗ ████████╗ ███████╗
 ██╔══██╗╚██╗ ██╔╝ ╚══██╔══╝ ██╔════╝
 ██████╔╝ ╚████╔╝     ██║    █████╗
 ██╔══██╗  ╚██╔╝      ██║    ██╔══╝
 ██████╔╝   ██║       ██║    ███████╗
 ╚═════╝    ╚═╝       ╚═╝    ╚══════╝

        ╔═══════════════════════════════════════════════════╗
        ║  🤖 Byte Agent TUI Control Interface             ║
        ║  ─────────────────────────────────────────────    ║
        ║  ↑/↓ Navigate  │  Enter Select  │  Esc Back    ║
        ║  a Approve     │  r Reject      │  q Quit       ║
        ╚═══════════════════════════════════════════════════╝`

	BannerSmall = `
╔═══════════════════════════════════════════════════════════╗
║  BYTE  -  Twitch Bot Control                              ║
╠══════════════════════════════════════════════════════════╣
║  ↑/↓ Navigate  │  Enter Select  │  Esc Back  │  q Quit  ║
╚═══════════════════════════════════════════════════════════╝`

	BannerMinimal = " BYTE - Control "

	// Box styles
	BaseBox = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(ColorPrimary).
		Padding(0, 1)

	DimBox = BaseBox.Copy().
		BorderForeground(ColorDim)

	ActiveBox = BaseBox.Copy().
			BorderForeground(ColorSecondary).
			Border(lipgloss.DoubleBorder())

	// Text styles
	Title = lipgloss.NewStyle().
		Bold(true).
		Foreground(ColorPrimary)

	Subtitle = lipgloss.NewStyle().
			Foreground(ColorSecondary)

	SuccessText = lipgloss.NewStyle().Foreground(ColorSuccess)
	ErrorText   = lipgloss.NewStyle().Foreground(ColorError).Bold(true)
	DimText     = lipgloss.NewStyle().Foreground(ColorDim)

	// Layout parts
	HeaderStyle = lipgloss.NewStyle().
			Align(lipgloss.Center).
			Padding(1, 0).
			MarginBottom(1)
)

func CombineVertical(styles ...string) string {
	return lipgloss.JoinVertical(lipgloss.Left, styles...)
}

func CombineHorizontal(styles ...string) string {
	return lipgloss.JoinHorizontal(lipgloss.Top, styles...)
}
