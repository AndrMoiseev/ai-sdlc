# Media export integration note

Clients request assets captured since a date chosen by the operator. One export reads a frozen catalogue snapshot. Pages display only `assetId`, `title` and `capturedOn`. Assets can share a capture day and asset IDs have no relationship to physical storage order.

The currently proposed SDK saves the final displayed asset's ID after a page has been durably processed. On reconnect it sends `capturedSince` and this ID to start the next page. Another proposal adds sorting columns to each displayed asset so both the web SDK and a command-line client can rebuild the resume request. Storage initially merges two ordered partitions. A third partition and a new internal tie-breaker are planned. Clients may disconnect between any two pages. The service can reconstruct its next position within the frozen snapshot and can report exhaustion explicitly.

Operators must retain the ability to choose a different `capturedSince` to begin a fresh export. The release has no requirement to seek to, or let users edit, an internal partition position. No existing resume protocol has shipped.
