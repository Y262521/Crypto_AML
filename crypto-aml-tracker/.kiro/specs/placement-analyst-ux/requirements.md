# Requirements Document

## Introduction

This feature delivers three interconnected analyst-facing improvements to the Placement page of the crypto AML tracker:

1. **UI Redundancy Removal** — The Placement page header currently contains a standalone `datetime-local` calendar widget that duplicates date-filtering functionality already present in the FilterBar. This widget will be removed; the header will contain only the page title and subtitle.

2. **Analyst Input System** — The FilterBar on the Placement page will be upgraded to expose all server-supported filter parameters: date range (already partially present), a new risk-level filter (low / medium / high / POI) that maps to `min_confidence` thresholds, the existing behavior/algorithm selector, and the existing entity search. The backend placement API will gain a `risk_level` query parameter that translates to the appropriate `min_confidence` range.

3. **POI Simulation Mode** — A toggle on the Placement page will activate a simulation panel. When an analyst selects an entity from the table, the panel lets them inject behaviors and labels, submit to `POST /api/risk/simulate`, and view the simulated risk outcome without writing to the database. The backend `SimulateRequest` model and the `simulate_risk` engine function will be extended to accept `simulate_behaviors[]` and `simulate_labels[]` alongside the existing `override` dict.

---

## Glossary

- **Placement_Page**: The React page component (`Placement.jsx`) that displays placement-stage AML alerts.
- **FilterBar**: The shared React component (`FilterBar.jsx`) that renders filter controls below the summary cards on the Placement page.
- **Header**: The dark-gradient banner at the top of the Placement_Page containing the page title and subtitle.
- **Datetime_Widget**: The standalone `datetime-local` `<input>` element currently rendered in the top-right corner of the Header.
- **Risk_Level**: A categorical filter value — one of `low`, `medium`, `high`, or `POI` — that maps to a `min_confidence` range used by the placement API.
- **Confidence_Range**: The numeric interval `[min, max)` of `confidence_score` values associated with each Risk_Level: low = 0.0–0.4, medium = 0.4–0.7, high = 0.7–0.9, POI = 0.9–1.0.
- **Behavior_Selector**: The single-select dropdown in the FilterBar that filters placement alerts by a specific behavior type (e.g., `structuring`, `smurfing`, `micro_funding`).
- **Entity_Search**: The free-text input in the FilterBar that filters placement alerts by entity ID or address substring.
- **POI_Simulation_Mode**: An analyst-only mode on the Placement_Page, activated by a toggle, that enables entity selection and risk simulation without database writes.
- **Simulation_Panel**: The slide-in panel rendered when POI_Simulation_Mode is active and an entity is selected, containing behavior/label injection controls and simulation results.
- **Simulate_Behaviors**: A list of behavior type strings (e.g., `loop_detection`, `coordinated_cashout`) that the analyst injects into a simulation request.
- **Simulate_Labels**: A list of label strings (e.g., `mixer`, `scam`, `sanctioned`) that the analyst injects into a simulation request.
- **Risk_Engine**: The Python module `aml_pipeline.risk.engine` that computes and simulates risk scores.
- **Simulate_Endpoint**: `POST /api/risk/simulate` — the FastAPI route that calls the Risk_Engine simulation function and returns results without writing to the database.
- **SimulateRequest**: The Pydantic model accepted by the Simulate_Endpoint.
- **Risk_Delta**: The numeric difference between the simulated risk score and the current risk score for an entity.
- **Would_Be_POI**: A boolean flag returned by the Simulate_Endpoint indicating whether the simulated risk score meets or exceeds the POI entry threshold (0.80).

---

## Requirements

### Requirement 1: Remove Header Datetime Widget

**User Story:** As an analyst, I want the Placement page header to show only the title and subtitle, so that the interface is uncluttered and date filtering is consolidated in one place.

#### Acceptance Criteria

1. THE Placement_Page SHALL render the Header without the Datetime_Widget.
2. THE Header SHALL contain only the page title ("🛡 Placement Stage Review") and the subtitle text.
3. WHEN the Placement_Page loads, THE Placement_Page SHALL NOT render any `datetime-local` input element inside the Header.
4. THE FilterBar SHALL remain the sole location for date-range filtering on the Placement_Page.

---

### Requirement 2: Consolidate Date Filtering into FilterBar

**User Story:** As an analyst, I want all date filtering to live in the FilterBar, so that I have a single, consistent place to control what data is shown.

#### Acceptance Criteria

1. THE FilterBar SHALL render a "From" date picker and a "To" date picker as the date-range filter controls.
2. WHEN an analyst sets a date in the "From" date picker, THE Placement_Page SHALL pass the selected value as `date_from` to the placement API on the next fetch.
3. WHEN an analyst sets a date in the "To" date picker, THE Placement_Page SHALL pass the selected value as `date_to` to the placement API on the next fetch.
4. WHEN an analyst clears all filters, THE FilterBar SHALL reset both date pickers to empty values.
5. THE Placement_Page SHALL persist the `dateFrom` and `dateTo` filter values in session storage alongside the other filter state.

---

### Requirement 3: Risk Level Filter in FilterBar

**User Story:** As an analyst, I want to filter placement alerts by risk level category, so that I can quickly focus on entities in a specific confidence band without manually entering numeric thresholds.

#### Acceptance Criteria

1. THE FilterBar SHALL render a risk-level selector with the options: All, low, medium, high, POI.
2. WHEN an analyst selects "low", THE Placement_Page SHALL request placement alerts with `min_confidence` = 0.0 and `max_confidence` = 0.4 from the backend.
3. WHEN an analyst selects "medium", THE Placement_Page SHALL request placement alerts with `min_confidence` = 0.4 and `max_confidence` = 0.7 from the backend.
4. WHEN an analyst selects "high", THE Placement_Page SHALL request placement alerts with `min_confidence` = 0.7 and `max_confidence` = 0.9 from the backend.
5. WHEN an analyst selects "POI", THE Placement_Page SHALL request placement alerts with `min_confidence` = 0.9 and `max_confidence` = 1.0 from the backend.
6. WHEN an analyst selects "All", THE Placement_Page SHALL request placement alerts with no confidence-range restriction.
7. THE placement API (`GET /api/placement/`) SHALL accept a `risk_level` query parameter with values: `low`, `medium`, `high`, `poi`.
8. WHEN the placement API receives `risk_level` = `low`, THE Placement_API SHALL filter results to entities with `confidence_score` >= 0.0 and `confidence_score` < 0.4.
9. WHEN the placement API receives `risk_level` = `medium`, THE Placement_API SHALL filter results to entities with `confidence_score` >= 0.4 and `confidence_score` < 0.7.
10. WHEN the placement API receives `risk_level` = `high`, THE Placement_API SHALL filter results to entities with `confidence_score` >= 0.7 and `confidence_score` < 0.9.
11. WHEN the placement API receives `risk_level` = `poi`, THE Placement_API SHALL filter results to entities with `confidence_score` >= 0.9 and `confidence_score` <= 1.0.
12. WHEN the placement API receives both `risk_level` and `min_confidence`, THE Placement_API SHALL apply the `risk_level` bounds and ignore the standalone `min_confidence` parameter.
13. WHEN an analyst clears all filters, THE FilterBar SHALL reset the risk-level selector to "All".

---

### Requirement 4: Behavior Selector and Entity Search Remain in FilterBar

**User Story:** As an analyst, I want the behavior selector and entity search to remain in the FilterBar alongside the new controls, so that all filter controls are co-located.

#### Acceptance Criteria

1. THE FilterBar SHALL render the Behavior_Selector as a single-select dropdown populated with all behavior types discovered from the current alert set plus the known behaviors: `structuring`, `smurfing`, `micro_funding`.
2. WHEN an analyst selects a behavior from the Behavior_Selector, THE Placement_Page SHALL pass the selected value as the `behavior` parameter to the placement API on the next fetch.
3. THE FilterBar SHALL render the Entity_Search as a free-text input.
4. WHEN an analyst types in the Entity_Search input, THE Placement_Page SHALL pass the trimmed value as the `search` parameter to the placement API after a 150 ms debounce.
5. WHEN an analyst clears all filters, THE FilterBar SHALL reset the Behavior_Selector to "All" and the Entity_Search to an empty string.

---

### Requirement 5: POI Simulation Mode Toggle

**User Story:** As an analyst, I want a toggle to activate POI Simulation Mode on the Placement page, so that I can enter a dedicated simulation workflow without affecting the normal alert view.

#### Acceptance Criteria

1. THE Placement_Page SHALL render a "POI Simulation Mode" toggle control above the alert table.
2. WHEN the toggle is off, THE Placement_Page SHALL display the alert table in its normal read-only state.
3. WHEN an analyst activates the toggle, THE Placement_Page SHALL display a visible indicator that POI Simulation Mode is active.
4. WHEN POI Simulation Mode is active, THE Placement_Page SHALL render each alert row as selectable.
5. WHEN an analyst deactivates the toggle, THE Placement_Page SHALL close any open Simulation_Panel and deselect any selected entity.
6. THE Placement_Page SHALL NOT modify any database record as a result of toggling POI Simulation Mode.

---

### Requirement 6: Entity Selection in POI Simulation Mode

**User Story:** As an analyst, I want to select an entity from the alert table while in POI Simulation Mode, so that I can open the simulation panel for that entity.

#### Acceptance Criteria

1. WHILE POI Simulation Mode is active, WHEN an analyst clicks an alert row, THE Placement_Page SHALL open the Simulation_Panel for the selected entity.
2. WHILE POI Simulation Mode is active, THE Placement_Page SHALL visually highlight the selected alert row.
3. WHEN an analyst selects a different alert row, THE Placement_Page SHALL replace the Simulation_Panel content with the newly selected entity's data.
4. WHEN an analyst closes the Simulation_Panel, THE Placement_Page SHALL deselect the current entity without deactivating POI Simulation Mode.

---

### Requirement 7: Simulation Panel — Behavior and Label Injection

**User Story:** As an analyst, I want to choose behaviors and labels to inject into a simulation, so that I can model how a risk score would change under hypothetical conditions.

#### Acceptance Criteria

1. THE Simulation_Panel SHALL display the selected entity's current risk score and current `would_be_poi` status before any simulation is submitted.
2. THE Simulation_Panel SHALL render a multi-select control for Simulate_Behaviors with the options: `loop_detection`, `coordinated_cashout`, `peeling_chain`, `structuring`, `smurfing`, `micro_funding`.
3. THE Simulation_Panel SHALL render a multi-select control for Simulate_Labels with the options: `mixer`, `scam`, `sanctioned`.
4. WHEN an analyst submits the simulation, THE Simulation_Panel SHALL send a POST request to `/api/risk/simulate` with `entity_id`, `simulate_behaviors`, `simulate_labels`, and `user_id`.
5. THE Simulation_Panel SHALL disable the submit button while a simulation request is in flight.
6. IF the simulation request returns an error, THEN THE Simulation_Panel SHALL display the error message and re-enable the submit button.

---

### Requirement 8: Simulation Panel — Results Display

**User Story:** As an analyst, I want to see the simulated risk score, POI status, and risk delta after submitting a simulation, so that I can assess the impact of the injected conditions.

#### Acceptance Criteria

1. WHEN the Simulate_Endpoint returns a successful response, THE Simulation_Panel SHALL display the `simulated_risk_score` value.
2. WHEN the Simulate_Endpoint returns a successful response, THE Simulation_Panel SHALL display the `would_be_poi` value as "YES" or "NO".
3. WHEN the Simulate_Endpoint returns a successful response, THE Simulation_Panel SHALL display the `risk_delta` value with a sign indicator (+ or −).
4. WHEN `risk_delta` is positive, THE Simulation_Panel SHALL render the delta value in a visually distinct danger color.
5. WHEN `risk_delta` is negative or zero, THE Simulation_Panel SHALL render the delta value in a neutral or positive color.
6. THE Simulation_Panel SHALL clearly label all displayed values so an analyst can distinguish simulated results from current values.

---

### Requirement 9: Simulate Endpoint — Behavior and Label Extension

**User Story:** As an analyst, I want the simulate endpoint to accept injected behaviors and labels, so that the simulation reflects the hypothetical conditions I specify.

#### Acceptance Criteria

1. THE SimulateRequest SHALL accept an optional `simulate_behaviors` field containing a list of behavior type strings.
2. THE SimulateRequest SHALL accept an optional `simulate_labels` field containing a list of label strings.
3. WHEN `simulate_behaviors` is provided, THE Simulate_Endpoint SHALL pass each behavior to the Risk_Engine so that the behavior component of the risk breakdown is increased by the corresponding weight from `BEHAVIOR_WEIGHTS`.
4. WHEN `simulate_labels` is provided, THE Simulate_Endpoint SHALL pass each label to the Risk_Engine so that the label component of the risk breakdown is set to the maximum weight among the provided labels using `LABEL_WEIGHTS`.
5. WHEN both `simulate_behaviors` and `simulate_labels` are provided, THE Simulate_Endpoint SHALL apply both sets of overrides before computing the simulated score.
6. WHEN neither `simulate_behaviors` nor `simulate_labels` is provided, THE Simulate_Endpoint SHALL behave identically to its current behavior using only the `override` dict.
7. THE Simulate_Endpoint SHALL return `simulated_risk_score`, `would_be_poi`, and `risk_delta` in the response body.
8. THE Simulate_Endpoint SHALL NOT write any data to the database during simulation.
9. THE Simulate_Endpoint SHALL record a simulation audit log entry including `entity_id`, `simulate_behaviors`, `simulate_labels`, `current_risk_score`, `simulated_risk_score`, and `user_id`.

---

### Requirement 10: Risk Engine — Multi-Behavior and Multi-Label Simulation

**User Story:** As a risk engineer, I want the simulate_risk function to accept lists of behaviors and labels, so that the simulation engine can model compound injection scenarios.

#### Acceptance Criteria

1. THE Risk_Engine `simulate_risk` function SHALL accept an optional `simulate_behaviors` list in the override dict.
2. WHEN `simulate_behaviors` is provided, THE Risk_Engine SHALL accumulate the behavior score by summing the `BEHAVIOR_WEIGHTS` for each behavior in the list, clamped to [0.0, 1.0].
3. THE Risk_Engine `simulate_risk` function SHALL accept an optional `simulate_labels` list in the override dict.
4. WHEN `simulate_labels` is provided, THE Risk_Engine SHALL set the label score to the maximum `LABEL_WEIGHTS` value among all labels in the list.
5. WHEN both `simulate_behaviors` and `simulate_labels` are provided, THE Risk_Engine SHALL apply the label override first, then the behavior accumulation, before computing the final simulated score.
6. THE Risk_Engine `simulate_risk` function SHALL return `would_be_poi` as `True` when the simulated score is >= 0.80 (the `POI_ENTER` threshold).
7. FOR ALL valid combinations of `simulate_behaviors` and `simulate_labels`, the `simulate_risk` function SHALL return a `new_risk_score` in the range [0.0, 1.0] (round-trip invariant: score is always clamped).
