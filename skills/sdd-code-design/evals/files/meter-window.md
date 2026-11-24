# Usage quote SDK

The production entry `readQuote(status, headers, bytes)` runs the shipped decoder and returns either a retry window in seconds or a terminal error. Header names are case-insensitive. HTTP 429 sends a retry window, and `X-Window-Unit` distinguishes seconds from minutes. A request ID and response date are used only for tracing.

Two candidate inputs are available. The internal SDK test builder constructs a typed quote and serializes it with the same model definitions used by the SDK decoder. A provider support engineer also supplied a sanitized exchange from the release under integration:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
X-Window-Unit: minutes
X-Request-Id: transient-7193
Date: Wed, 07 Jan 2026 12:00:00 GMT

{"retry_after":"2"}
```

The integration agreement says the string is a decimal quantity in the unit from the header. This CI job has no access to the provider network. A release draft contains the sentence “the SDK is compatible with what the provider serves today.”
