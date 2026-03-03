package api

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"reflect"
	"testing"

	"github.com/JuanCS-Dev/byte-tui/cmd/config"
)

// RoundTripFunc .
type RoundTripFunc func(req *http.Request) *http.Response

// RoundTrip .
func (f RoundTripFunc) RoundTrip(req *http.Request) (*http.Response, error) {
	return f(req), nil
}

// NewTestClient returns *http.Client with Transport replaced to avoid making real calls
func NewTestClient(fn RoundTripFunc) *http.Client {
	return &http.Client{
		Transport: RoundTripFunc(fn),
	}
}

func TestClientAuthenticationHeaders(t *testing.T) {
	cfg := config.Config{
		ApiUrl:     "http://test.com",
		AdminToken: "test-admin",
		HFToken:    "test-hf",
	}

	client := NewClient(cfg)

	// Inject mocked HTTP client
	client.HTTPClient = NewTestClient(func(req *http.Request) *http.Response {
		// Assert Headers Correctness
		if req.Header.Get("X-Byte-Admin-Token") != "test-admin" {
			t.Errorf("Expected X-Byte-Admin-Token to be 'test-admin', got '%s'", req.Header.Get("X-Byte-Admin-Token"))
		}
		if req.Header.Get("Authorization") != "Bearer test-hf" {
			t.Errorf("Expected Authorization to be 'Bearer test-hf', got '%s'", req.Header.Get("Authorization"))
		}

		// Fake response
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBufferString(`{"success": true}`)),
			Header:     make(http.Header),
		}
	})

	_, err := client.Get("/test")
	if err != nil {
		t.Fatal(err)
	}
}

func TestClientGet(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test.com"}
	client := NewClient(cfg)

	client.HTTPClient = NewTestClient(func(req *http.Request) *http.Response {
		if req.Method != "GET" {
			t.Errorf("Expected method GET, got %s", req.Method)
		}
		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBufferString(`{"data": "value"}`)),
			Header:     make(http.Header),
		}
	})

	res, err := client.Get("/some-path")
	if err != nil {
		t.Fatal(err)
	}

	expected := map[string]interface{}{"data": "value"}
	if !reflect.DeepEqual(res, expected) {
		t.Errorf("Expected %v, got %v", expected, res)
	}
}

func TestClientPost(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test.com"}
	client := NewClient(cfg)

	client.HTTPClient = NewTestClient(func(req *http.Request) *http.Response {
		if req.Method != "POST" {
			t.Errorf("Expected method POST, got %s", req.Method)
		}
		var payload map[string]interface{}
		json.NewDecoder(req.Body).Decode(&payload)
		if payload["input"] != "hello" {
			t.Errorf("Expected body {input: hello}, got %v", payload)
		}

		return &http.Response{
			StatusCode: 200,
			Body:       io.NopCloser(bytes.NewBufferString(`{"result": "ok"}`)),
			Header:     make(http.Header),
		}
	})

	res, err := client.Post("/send", map[string]interface{}{"input": "hello"})
	if err != nil {
		t.Fatal(err)
	}

	if res["result"] != "ok" {
		t.Errorf("Expected 'result': 'ok', got %v", res)
	}
}

func TestClientErrorHandling500(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test.com"}
	client := NewClient(cfg)

	client.HTTPClient = NewTestClient(func(req *http.Request) *http.Response {
		return &http.Response{
			StatusCode: 500,
			Status:     "500 Internal Server Error",
			Body:       io.NopCloser(bytes.NewBufferString(`{"detail": "Agent crashed"}`)),
			Header:     make(http.Header),
		}
	})

	_, err := client.Get("/crash")
	if err == nil {
		t.Fatal("Expected an error for 500 status code, got none")
	}

	apiErr, ok := err.(*APIError)
	if !ok {
		t.Fatalf("Expected error of type *APIError, got %T", err)
	}

	if apiErr.StatusCode != 500 {
		t.Errorf("Expected status code 500, got %d", apiErr.StatusCode)
	}
	if apiErr.Message != "Agent crashed" {
		t.Errorf("Expected message 'Agent crashed', got '%s'", apiErr.Message)
	}
}

func TestClientPutAndDelete(t *testing.T) {
	cfg := config.Config{ApiUrl: "http://test.com"}
	client := NewClient(cfg)

	client.HTTPClient = NewTestClient(func(req *http.Request) *http.Response {
		if req.Method == "PUT" || req.Method == "DELETE" {
			return &http.Response{
				StatusCode: 200,
				Body:       io.NopCloser(bytes.NewBufferString(`{"status": "mod_ok"}`)),
				Header:     make(http.Header),
			}
		}
		return &http.Response{StatusCode: 400, Body: io.NopCloser(bytes.NewBufferString(""))}
	})

	resPut, err := client.Put("/modify", map[string]interface{}{"val": 1})
	if err != nil || resPut["status"] != "mod_ok" {
		t.Errorf("Failed PUT test")
	}

	resDel, err := client.Delete("/remove")
	if err != nil || resDel["status"] != "mod_ok" {
		t.Errorf("Failed DELETE test")
	}
}
