Directive:
Immediately stress-test your entire OpenAPI schema. Do not output sample actions. Instead, run full endpoint coverage tests and return a structured audit report. And do not perform any destructive operations or any operations that may interrupt this test (i.e., shutdown)

Steps to Perform:

Full Endpoint Coverage

Execute safe requests against every endpoint (/shell, /files, /code, /system, /monitor, /git, /package, /apps, /refactor, /batch).

Systematically vary parameters: valid, invalid, required/optional, edge cases, concurrency (parallel + sequential).

Fuzz inputs to uncover undocumented behavior.

Data Capture

Log for each request: endpoint, params, status code, latency, payload size, anomalies, schema drift, unexpected responses.

Analysis

Categorize findings as Successes, Failures, Gaps, Inefficiencies, Security Concerns.

Highlight undocumented fields, silent failures, or weak validation.

Rank issues by severity and impact.

Output

Deliver results in two parts:

Raw logs (JSON/CSV of all requests + responses).

Executive Audit Report (Markdown/PDF):

Executive Summary (overall API health & reliability)

Endpoint Results Table

Gap Analysis

Recommendations

Priority Ranking

Goal:
Return an audit-grade stress-test report, proving whether the schema enables 100% safe, reliable, and efficient system control.