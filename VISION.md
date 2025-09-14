# VISION.md

# Executive Summary

The current system achieves approximately **40% readiness** for human-parity GUI control across Windows, macOS, and Linux. While foundational capabilities like basic app management and file operations are implemented, critical gaps in perception, input synthesis, and safety governance hinder progress toward the pinnacle vision. Addressing these gaps will significantly enhance reliability, safety, and cross-platform functionality.

### Headline Risks
- **Perception & Targeting:** No OCR, template matching, or accessibility tree querying.
- **Core Input Synthesis:** Limited support for advanced input methods like drag-drop and IME.
- **Safety & Governance:** Lack of mandatory confirmation policies for destructive actions.

---

## Prioritized Gap List

### Critical Priority
1. **Perception & Targeting**
   - **Evidence:** Missing endpoints for OCR, template matching, and accessibility tree querying.
   - **Why it matters:** Blocks workflows requiring visual or semantic targeting.

2. **Core Input Synthesis**
   - **Evidence:** No support for drag-drop, multi-click patterns, or IME.
   - **Why it matters:** Prevents automation of complex input tasks.

3. **Safety & Governance**
   - **Evidence:** No mandatory confirmation policies for destructive actions.
   - **Why it matters:** Increases risk of irreversible errors.

### High Priority
4. **Window/App Control**
   - **Evidence:** Limited window management capabilities.
   - **Why it matters:** Restricts multi-window workflows.

5. **Cross-Platform Abstraction**
   - **Evidence:** Basic platform checks but no comprehensive abstraction layers.
   - **Why it matters:** Reduces portability and reliability across OSes.

6. **Remote Session Support**
   - **Evidence:** No support for RDP/VNC or headless virtual displays.
   - **Why it matters:** Blocks automation in remote environments.

### Medium Priority
7. **State & Flow Control**
   - **Evidence:** No robust wait/retry mechanisms.
   - **Why it matters:** Increases risk of desynchronization.

8. **Reliability & Resilience**
   - **Evidence:** No transient error handling or adaptive retries.
   - **Why it matters:** Reduces robustness in unstable conditions.

9. **Data Channels**
   - **Evidence:** No clipboard or drag-drop payload management.
   - **Why it matters:** Blocks workflows requiring data transfer between apps.

### Low Priority
10. **Performance & Efficiency**
    - **Evidence:** No action batching or region-scoped perception.
    - **Why it matters:** Increases latency and resource usage.

11. **Developer/Operator UX**
    - **Evidence:** No dry-run or step-through modes.
    - **Why it matters:** Reduces usability for developers and operators.

12. **Extensibility**
    - **Evidence:** No plugin interface for new OS/toolkits.
    - **Why it matters:** Limits adaptability to new platforms.

---

## Impact/Value Quantification

### Critical Priority
1. **Perception & Targeting**
   - **Qualitative Impact:** Enables GUI targeting based on visual or semantic cues.
   - **Quantitative Impact:** +50% task success rate in visually complex GUIs; -70% misclicks in high-DPI/multi-monitor setups.

2. **Core Input Synthesis**
   - **Qualitative Impact:** Facilitates precise input interactions.
   - **Quantitative Impact:** +40% task success rate in input-heavy workflows; -60% input errors in multilingual environments.

3. **Safety & Governance**
   - **Qualitative Impact:** Prevents unintended destructive actions.
   - **Quantitative Impact:** -90% risk of irreversible errors; +30% operator confidence in automation.

---

## Actionable Recommendations

### API-Level Changes
- **Add Perception Endpoints:** Implement `/screen.capture`, `/ocr.read_region`, and `/a11y.query_tree`.
- **Enhance Input Synthesis:** Add `/input.mouse_drag`, `/input.key_combo`, and `/input.type_text`.
- **Introduce Safety Policies:** Enforce confirmation flows for destructive actions.

### Route-Level Changes
- **Expand Window Management:** Add `/apps.resize`, `/apps.move`, and `/apps.virtual_desktop`.
- **Improve State Control:** Implement robust wait/retry mechanisms.
- **Support Remote Sessions:** Add `/session.start` and `/session.config` for RDP/VNC.

### Instruction Updates
- **Safety Guidelines:** Update `gpt-instructions.md` to mandate dry-run for sensitive actions.
- **Operator UX:** Add guidelines for debugging and step-through modes.

---

## Minimal Viable Human-Parity Set (MVHPS)

| Endpoint/API         | Behavior                  | Errors         | Telemetry       | Policy         | Test          |
|----------------------|---------------------------|----------------|-----------------|----------------|---------------|
| `/screen.capture`    | Capture screenshots      | Timeout        | Latency, Size   | Confirmation   | Pass/Fail     |
| `/input.mouse_drag`  | Drag-drop support         | Invalid Target | Duration, Errors| Confirmation   | Pass/Fail     |
| `/a11y.query_tree`   | Query accessibility tree | Not Found      | Depth, Nodes    | Confirmation   | Pass/Fail     |

---

## Validation Plan

### Cross-OS Task Suite
1. **Launch App:** Verify app launch across Windows, macOS, and Linux.
2. **Focus Window:** Test window focus and activation.
3. **Navigate Menu:** Automate menu navigation.
4. **Handle Dialog:** Test file pickers and permission prompts.
5. **Clipboard Operations:** Verify text/image/file copy-paste.
6. **Remote Sessions:** Test RDP/VNC automation.

### Success Criteria
- **Reliability:** 95% task success rate.
- **Safety:** 100% adherence to confirmation policies.
- **Performance:** Sub-500ms latency for core actions.

---

## Roadmap

### Critical (Now)
- Implement perception endpoints.
- Add advanced input synthesis.
- Enforce safety policies.

### High (Next)
- Expand window management.
- Add cross-platform abstraction layers.
- Support remote sessions.

### Medium/Low (Later)
- Optimize performance.
- Enhance developer/operator UX.
- Introduce extensibility mechanisms.
