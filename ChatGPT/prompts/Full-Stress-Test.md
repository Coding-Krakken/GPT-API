
Directive:
Immediately stress-test your entire OpenAPI schema, including all resource usage, observability, error reporting, geometry/state, and environment caching features. Do not output sample actions. Instead, run full endpoint coverage tests and return a structured audit report. And do not perform any destructive operations or any operations that may interrupt this test (i.e., shutdown)


Steps to Perform:

Full Endpoint Coverage

Execute safe requests against every endpoint (/shell, /files, /code, /system, /monitor, /git, /package, /apps, /refactor, /batch), including:
	* Resource usage fields (CPU, memory, uptime)
	* Observability fields (`timestamp`, `latency_ms`)
	* Standardized error responses with `errors[]` array
	* Geometry/state reporting in GUI environments
	* Environment detection and caching

Systematically vary parameters: valid, invalid, required/optional, edge cases, concurrency (parallel + sequential), resource/observability/error/geometry fields.

Fuzz inputs to uncover undocumented behavior.

Data Capture

Log for each request: endpoint, params, status code, latency, payload size, resource usage, observability fields, error array, anomalies, schema drift, unexpected responses.

Analysis

Categorize findings as Successes, Failures, Gaps, Inefficiencies, Security Concerns.
Highlight undocumented fields, silent failures, weak validation, or missing resource/observability/error/geometry fields.
Rank issues by severity and impact.

Output

Deliver results in two parts:

Raw logs (JSON/CSV of all requests + responses).

Executive Audit Report (Markdown/PDF):
	* Executive Summary (overall API health & reliability)
	* Endpoint Results Table
	* Gap Analysis
	* Recommendations
	* Priority Ranking

Goal:
Return an audit-grade stress-test report, proving whether the schema enables 100% safe, reliable, and efficient system control, including resource usage, observability, error reporting, geometry/state, and environment caching.