package acquire

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

func Client(origin string) *http.Client {
	allowed, _ := url.Parse(origin)
	return &http.Client{
		Timeout: 30 * time.Second,
		CheckRedirect: func(request *http.Request, _ []*http.Request) error {
			if request.URL.Scheme != "https" || request.URL.Host != allowed.Host {
				return fmt.Errorf("redirect left required NIST HTTPS origin")
			}
			return nil
		},
	}
}

func Fetch(client *http.Client, resource string) ([]byte, error) {
	request, err := http.NewRequest(http.MethodGet, resource, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Accept", "application/json, text/plain;q=0.9")
	request.Header.Set("User-Agent", "nist-beacon-audit/1.0")
	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", resource, err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GET %s: HTTP %d", resource, response.StatusCode)
	}
	const maximumResponseBytes = 2 << 20
	limited := io.LimitReader(response.Body, maximumResponseBytes)
	data, err := io.ReadAll(limited)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", resource, err)
	}
	if len(data) == 0 {
		return nil, fmt.Errorf("GET %s: empty response", resource)
	}
	return data, nil
}
