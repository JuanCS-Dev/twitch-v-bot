package config

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	ApiUrl     string
	AdminToken string
	HFToken    string
}

func parseByteRC() map[string]string {
	res := make(map[string]string)
	home, err := os.UserHomeDir()
	if err != nil {
		return res
	}

	rcPath := filepath.Join(home, ".byterc")
	file, err := os.Open(rcPath)
	if err != nil {
		return res
	}
	defer file.Close()

	if strings.HasSuffix(rcPath, ".json") { // fallback if json was used manually
		bytes, err := os.ReadFile(rcPath)
		if err == nil {
			var parsed map[string]interface{}
			if err := json.Unmarshal(bytes, &parsed); err == nil {
				if v, ok := parsed["default"].(map[string]interface{}); ok {
					if url, o := v["url"].(string); o {
						res["url"] = url
					}
					if tok, o := v["token"].(string); o {
						res["token"] = tok
					}
					if hf, o := v["hf_token"].(string); o {
						res["hf_token"] = hf
					}
				}
			}
			return res
		}
	}

	// Default INI parser format as dictated by Python cli
	scanner := bufio.NewScanner(file)
	var currentSection string
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			currentSection = line[1 : len(line)-1]
			continue
		}
		if currentSection == "default" {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				val := strings.TrimSpace(parts[1])
				res[key] = val
			}
		}
	}
	return res
}

func LoadConfig() Config {
	c := Config{
		ApiUrl: "http://localhost:7860", // default
	}

	rc := parseByteRC()
	if v, ok := rc["url"]; ok {
		c.ApiUrl = v
	}
	if v, ok := rc["token"]; ok {
		c.AdminToken = v
	}
	if v, ok := rc["hf_token"]; ok {
		c.HFToken = v
	}

	if env := os.Getenv("BYTE_API_URL"); env != "" {
		c.ApiUrl = env
	}
	if env := strings.TrimSpace(os.Getenv("BYTE_DASHBOARD_ADMIN_TOKEN")); env != "" {
		c.AdminToken = env
	}
	if env := strings.TrimSpace(os.Getenv("BYTE_ADMIN_TOKEN")); env != "" {
		c.AdminToken = env
	}
	if env := strings.TrimSpace(os.Getenv("HF_TOKEN")); env != "" {
		c.HFToken = env
	}

	// Remove trailing slash
	c.ApiUrl = strings.TrimRight(c.ApiUrl, "/")

	return c
}
