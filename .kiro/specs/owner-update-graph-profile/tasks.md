# Implementation Plan: owner-update-graph-profile

## Overview

Implement two enhancements to the crypto-AML tracker:
1. Duplicate address detection with a confirmation dialog before reassignment.
2. Owner profile section in the Graph Explorer address side panel, backed by a new lookup endpoint.

The changes span three layers: a new FastAPI route, a modified `create_owner_list_entry` function, and two React component updates.

## Tasks

- [x] 1. Add `GET /owner-by-address/{address}` endpoint to the backend
  - Add the route to `crypto-aml-tracker/backend-py/routes/clusters.py`
  - Join `owner_list_addresses → owner_list` and `addresses → wallet_clusters` to retrieve `owner_id`, `full_name`, `entity_type`, `list_category`, and `risk_level`
  - Return `{ "owner": null }` (200) when the address is not found
  - Reuse the existing `_require_mysql()` guard for 503 responses
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 1.1 Write unit tests for the new endpoint
    - `test_get_owner_by_address_found` — seed owner + address, assert all five fields
    - `test_get_owner_by_address_not_found` — unknown address, assert `{ "owner": null }`
    - `test_get_owner_by_address_503` — mock `get_pool()` returning `None`, assert 503
    - _Requirements: 3.2, 3.3, 3.4_

  - [ ]* 1.2 Write property test for owner lookup (Property 5 & 6)
    - **Property 5: Owner lookup returns all required fields**
    - **Property 6: Owner lookup is idempotent**
    - **Validates: Requirements 3.2, 3.5, 3.6**

- [x] 2. Implement duplicate address detection in `POST /owner-list`
  - [x] 2.1 Add `force_override: bool = Field(default=False)` to `OwnerListCreateRequest` in `clusters.py`
    - _Requirements: 1.4, 1.5_

  - [x] 2.2 Update the `POST /owner-list` route handler to detect conflicts before calling `create_owner_list_entry`
    - Query `owner_list_addresses` for any submitted address that already exists
    - If conflicts found and `force_override` is `False`, return 409 with `{ "detail": "duplicate_addresses", "conflicts": [{address, current_owner_name}] }`
    - If `force_override` is `True`, pass through to `create_owner_list_entry`
    - _Requirements: 1.1, 1.5, 1.7_

  - [x] 2.3 Update `create_owner_list_entry` in `AML/src/aml_pipeline/clustering/owner_registry.py` to accept and handle `force_override`
    - When `force_override=True` and duplicate addresses exist, delete the old `owner_list_addresses` rows before inserting new ones
    - _Requirements: 1.5_

  - [ ]* 2.4 Write unit tests for duplicate detection
    - `test_post_owner_list_409_on_duplicate` — seed duplicate, POST without `force_override`, assert 409 with correct conflict list
    - `test_post_owner_list_200_with_force_override` — seed duplicate, POST with `force_override: true`, assert 200 and address reassigned
    - `test_post_owner_list_200_no_duplicates` — all-new addresses, assert 200
    - _Requirements: 1.1, 1.5, 1.7_

  - [ ]* 2.5 Write property test for duplicate detection (Property 1 & 2)
    - **Property 1: Duplicate address detection is exhaustive**
    - **Property 2: Force-override reassigns all submitted addresses**
    - **Validates: Requirements 1.1, 1.5, 1.7**

- [x] 3. Checkpoint — Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add `getOwnerByAddress` to the frontend service layer
  - Add `getOwnerByAddress(address)` export to `crypto-aml-tracker/src/services/transactionService.js`
  - Update `createOwnerListEntry` to return `{ _status: 409, ...body }` on a 409 response instead of throwing, so callers can branch on the conflict case; all other non-OK statuses continue to throw
  - _Requirements: 1.2, 3.1_

- [x] 5. Add owner info section to `AddressPanel` in `GraphExplorer.jsx`
  - Import `getOwnerByAddress` from the service layer
  - Add `ownerInfo` and `ownerError` state variables inside `AddressPanel`
  - Add a `useEffect` that calls `getOwnerByAddress(address)` whenever `address` changes; reset state on each call
  - Insert the owner section between the header and the stats grid
  - Render loading indicator when `ownerInfo === null && !ownerError`
  - Render "Unassigned" when `ownerInfo.owner === null`
  - Render name (bold), entity type pill, and list category pill when owner is found
  - Render "Owner data unavailable" (muted red) on error, without hiding existing stats
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 5.1 Write unit tests for `AddressPanel` owner section
    - `test_address_panel_loading_state` — mock pending promise, assert loading indicator
    - `test_address_panel_unassigned` — mock `{ owner: null }`, assert "Unassigned"
    - `test_address_panel_owner_found` — mock owner data, assert name, entity type, list category visible
    - `test_address_panel_error_state` — mock rejection, assert error message and stats still visible
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 5.2 Write property test for owner panel display (Property 3 & 4)
    - **Property 3: Owner panel displays all required fields**
    - **Property 4: Existing panel content is preserved**
    - **Validates: Requirements 2.1, 2.5**

- [x] 6. Add confirmation dialog for duplicate address reassignment in `Clusters.jsx`
  - Add `conflictData` state variable to the `Clusters` component (null = no conflict)
  - Update `handleOwnerSubmit` to detect `_status: 409` from `createOwnerListEntry` and set `conflictData` with the conflicts array
  - Add `handleConfirmOverride` that resubmits with `force_override: true` and clears `conflictData` on success
  - Add `handleCancelOverride` that clears `conflictData` without resubmitting
  - Update `OwnerListModal` to accept `conflictData`, `onConfirmOverride`, and `onCancelOverride` props
  - Render a `ConfirmationDialog` inside `OwnerListModal` when `conflictData` is non-null, overlaid on the form
  - The dialog must display: "One or more addresses you entered are already assigned to an existing owner. Do you want to reassign them to this new entity?" with Confirm and Cancel buttons
  - _Requirements: 1.2, 1.3, 1.4, 1.6_

  - [ ]* 6.1 Write unit tests for the confirmation dialog flow
    - `test_confirmation_dialog_shown_on_409` — mock service returning 409, submit form, assert dialog visible
    - `test_confirmation_dialog_message` — assert exact dialog text and button labels
    - `test_confirm_resubmits_with_force_override` — click Confirm, assert second call includes `force_override: true`
    - `test_cancel_dismisses_dialog` — click Cancel, assert dialog gone, no second API call
    - _Requirements: 1.2, 1.3, 1.4, 1.6_

- [x] 7. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
