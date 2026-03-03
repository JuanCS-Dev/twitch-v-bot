package styles

import (
	"strings"
	"testing"
)

func TestCombineVertical(t *testing.T) {
	str1 := "Line1"
	str2 := "Line2"

	res := CombineVertical(str1, str2)

	// lipgloss.JoinVertical will combine with newlines
	if !strings.Contains(res, "Line1") || !strings.Contains(res, "Line2") {
		t.Errorf("CombineVertical failed. Result: %s", res)
	}
}

func TestCombineHorizontal(t *testing.T) {
	str1 := "Block1"
	str2 := "Block2"

	res := CombineHorizontal(str1, str2)

	if !strings.Contains(res, "Block1") || !strings.Contains(res, "Block2") {
		t.Errorf("CombineHorizontal failed. Result: %s", res)
	}
}

func TestStyleDefinitions(t *testing.T) {
	// Simple check that styles compile and return proper render loops
	if BaseBox.Render("test") == "" {
		t.Error("BaseBox render failed")
	}
	if Title.Render("test") == "" {
		t.Error("Title render failed")
	}
	if HeaderStyle.Render("test") == "" {
		t.Error("HeaderStyle render failed")
	}
	if SuccessText.Render("ok") == "" {
		t.Error("SuccessText render failed")
	}
}
