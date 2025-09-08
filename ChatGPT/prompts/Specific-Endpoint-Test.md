
# **Directive:**

Immediately and without delay, execute a **full stress-test and audit** of the `{{ENDPOINT}}` endpoint in your OpenAPI schema, including all resource usage, observability, error reporting, geometry/state, and environment caching features.
Do **not** acknowledge, confirm, explain, or output sample calls.
Do **not** ask questions or seek clarification.
Do **not** provide proposals.
Proceed directly to execution and deliver results.

---


## **Execution Requirements**

* Your very first action will be to create a test file to perform all operations against.
* Run **all supported operations and variations** of the `{{ENDPOINT}}` endpoint, including:
   * Resource usage fields (CPU, memory, uptime)
   * Observability fields (`timestamp`, `latency_ms`)
   * Standardized error responses with `errors[]` array
   * Geometry/state reporting in GUI environments
   * Environment detection and caching
* DO NOT use the bulk/ endpoint to perform any of these operations.
* Systematically test valid, invalid, missing, optional, edge-case, and maximum payload parameters.
* Apply concurrency tests (parallel + sequential).
* Perform fuzzing to uncover undocumented or weakly validated behavior.
* Simulate context-heavy workflows, including chained requests and cross-endpoint dependencies.
* Ensure **100% safe and non-destructive testing** (no shutdowns, no overwrites of critical files).
* The execution must cover **all supported operations and variations** of the `{{ENDPOINT}}` endpoint while ensuring tests are **100% safe, non-destructive, and continuity-preserving** (e.g., no shutdowns, no critical file overwrites, no harmful state changes).

---

## **Steps to Perform**


### 1. Endpoint Coverage

* Fully exercise the `{{ENDPOINT}}` endpoint with **all supported methods and variations**.
* Systematically vary parameters across:
   * Valid inputs
   * Invalid/malformed inputs
   * Missing/optional fields
   * Boundary/edge cases
   * Maximum payloads
   * Concurrency scenarios (parallel + sequential)
   * Resource usage and observability fields
   * Error array and schema compliance
   * Geometry/state in GUI and headless modes
   * Environment caching and detection
* Apply fuzzing to expose undocumented or weakly validated behavior.
* Simulate context-heavy workflows (chained requests, cross-endpoint dependencies).

---


### 2. Instruction & Schema Validation

* Compare actual responses with the OpenAPI schema definition.
* Detect schema drift, undocumented fields, or inconsistencies, especially for resource usage, observability, error array, and geometry/state fields.
* Verify that custom GPT instructions enforce correct usage.
* Test whether unsafe or inefficient behaviors (e.g., overwriting files, looping inefficiency, missing context, missing observability or resource fields) are prevented.

---


### 3. Data Capture

For **every request**, capture structured metadata:
* Endpoint + parameters
* Payload size
* Status codes
* Latency measurements
* Resource usage fields (if present)
* Observability fields (`timestamp`, `latency_ms`)
* Error array (if present)
* Concurrency results
* Anomalies, schema drift, unexpected responses

---


### 4. Analysis

* Categorize findings into: **Successes, Failures, Gaps, Inefficiencies, Security Concerns**.
* Confirm responses align with expected schema and safety standards, including resource usage, observability, error array, and geometry/state.
* Highlight optimization opportunities (context gathering efficiency, concurrency handling, safety enforcement, environment caching).
* Rank issues by **severity + potential system impact**.

---

## **Output Deliverables**

1. **Raw Logs (JSON/CSV)**

   * Full request/response metadata (latency, anomalies, schema drift, etc.).

2. **Executive Audit Report (Markdown/PDF)**

   * Executive Summary (endpoint health, reliability, schema conformance)
   * Results Table (inputs vs outputs, observed anomalies)
   * Gap Analysis (features, docs, efficiency)
   * Recommendations (clear, actionable improvements for functionality, safety, schema, and instruction design)
   * Priority Ranking (ordered by severity and urgency)

---

# **Goal**

Deliver an **audit-grade stress-test report** for the `{{ENDPOINT}}` endpoint, proving whether the current design achieves **100% safe, reliable, efficient, and instruction-aligned system control**, meeting or exceeding the standard of the most advanced agentic AI systems today.

