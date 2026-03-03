package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
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
	// Note: body is not closed here intentionally to let caller handle if they want raw

	if resp.StatusCode >= 400 {
		defer resp.Body.Close()
		var respBody map[string]interface{}
		json.NewDecoder(resp.Body).Decode(&respBody)
		detail := ""
		if d, ok := respBody["detail"].(string); ok {
			detail = d
		}
		if detail == "" {
			detail = resp.Status
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

	var data map[string]interface{}
	err = json.NewDecoder(resp.Body).Decode(&data)
	return data, err
}

func (c *Client) Post(path string, payload map[string]interface{}) (map[string]interface{}, error) {
	b, _ := json.Marshal(payload)
	resp, err := c.doRequest("POST", path, bytes.NewBuffer(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var data map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&data)
	return data, nil
}

func (c *Client) Put(path string, payload map[string]interface{}) (map[string]interface{}, error) {
	b, _ := json.Marshal(payload)
	resp, err := c.doRequest("PUT", path, bytes.NewBuffer(b))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var data map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&data)
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
