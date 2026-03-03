package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/JuanCS-Dev/byte-tui/cmd/config"
)

type APIError struct {
	StatusCode int
	Message    string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("API Error %d: %s", e.StatusCode, e.Message)
}

type Client struct {
	Cfg        config.Config
	HTTPClient *http.Client
}

func NewClient(cfg config.Config) *Client {
	return &Client{
		Cfg: cfg,
		HTTPClient: &http.Client{
			Timeout: 15 * time.Second,
		},
	}
}

func (c *Client) doRequest(method, path string, body io.Reader) (*http.Response, error) {
	req, err := http.NewRequest(method, c.Cfg.ApiUrl+path, body)
	if err != nil {
		return nil, err
	}

	req.Header.Set("X-Byte-Admin-Token", c.Cfg.AdminToken)
	if c.Cfg.HFToken != "" {
		req.Header.Set("Authorization", "Bearer "+c.Cfg.HFToken)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var respBody map[string]interface{}
		json.Unmarshal(bodyBytes, &respBody)

		detail := ""
		if d, ok := respBody["detail"].(string); ok {
			detail = d
		} else if m, ok := respBody["message"].(string); ok {
			detail = m
		}

		if detail == "" {
			detail = fmt.Sprintf("HTTP %d: %s", resp.StatusCode, string(bodyBytes))
		}

		return nil, &APIError{StatusCode: resp.StatusCode, Message: detail}
	}
	return resp, nil
}

func (c *Client) Get(path string) (map[string]interface{}, error) {
	resp, err := c.doRequest("GET", path, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	// Read entire body first to avoid stream exhaustion issues when decoding
	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}
	bodyStr := strings.TrimSpace(string(bodyBytes))

	// Handle /health endpoint which returns plain text
	if bodyStr == "AGENT_ONLINE" {
		return map[string]interface{}{"ok": true, "status": "AGENT_ONLINE"}, nil
	}

	// Try to decode as JSON
	var data map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &data); err != nil {
		// Return error with a snippet of the non-JSON content
		maxLen := 100
		if len(bodyStr) < maxLen {
			maxLen = len(bodyStr)
		}
		return nil, fmt.Errorf("invalid JSON response: %s", bodyStr[:maxLen])
	}
	return data, nil
}

func (c *Client) Post(path string, payload map[string]interface{}) (map[string]interface{}, error) {
	b, _ := json.Marshal(payload)
	resp, err := c.doRequest("POST", path, bytes.NewBuffer(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	var data map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &data); err != nil {
		return nil, fmt.Errorf("invalid JSON response: %s", strings.TrimSpace(string(bodyBytes)))
	}
	return data, nil
}

func (c *Client) Put(path string, payload map[string]interface{}) (map[string]interface{}, error) {
	b, _ := json.Marshal(payload)
	resp, err := c.doRequest("PUT", path, bytes.NewBuffer(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %v", err)
	}

	var data map[string]interface{}
	if err := json.Unmarshal(bodyBytes, &data); err != nil {
		return nil, fmt.Errorf("invalid JSON response: %s", strings.TrimSpace(string(bodyBytes)))
	}
	return data, nil
}

func (c *Client) Delete(path string) (map[string]interface{}, error) {
	resp, err := c.doRequest("DELETE", path, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var data map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&data)
	return data, nil
}
