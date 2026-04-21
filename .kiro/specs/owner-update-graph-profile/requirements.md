# Requirements Document

## Introduction

This feature adds owner profile information to the Graph Explorer's address side panel and implements duplicate address detection when adding new owner entities.

The feature covers two enhancements:

1. **Duplicate Address Detection**: When an analyst submits the "Add / Update Owner" form with an address that already belongs to another owner, the system displays a confirmation dialog before allowing the reassignment.

2. **Owner Profile in Graph Panel**: The existing address side panel in the Graph Explorer displays owner information (name, entity type, list category) when an address is linked to an owner record.

## Glossary

- **Owner_Profile**: A record in the `owner_list` table representing a named entity (individual, exchange, merchant, etc.) associated with one or more blockchain addresses.
- **Address_Panel**: The slide-in side panel in the Graph Explorer (`AddressPanel` component in `GraphExplorer.jsx`) that appears when a user clicks an address node. Currently displays transaction statistics and Etherscan links.
- **Owner_List_Modal**: The modal form in `Clusters.jsx` (`OwnerListModal` component) used to add or update owner records. Labeled "Add / Update Owner" in the UI.
- **Duplicate_Address**: A blockchain address that already exists in the `owner_list_addresses` table and is linked to an existing owner. The `address` column has a UNIQUE constraint.
- **Confirmation_Dialog**: A modal dialog that presents the user with a warning and requires explicit confirmation before reassigning an address to a different owner.
- **Graph_Explorer**: The full-screen transaction network visualization page (`GraphExplorer.jsx`) that renders address nodes and transaction edges using React Flow.
- **Owner_API**: The backend REST API in `crypto-aml-tracker/backend-py/routes/clusters.py` responsible for creating, reading, and updating owner records and their associated addresses.
- **Risk_Level**: A classification field on a wallet cluster (`normal`, `medium`, `high`) indicating the assessed risk of the associated entity. Stored in the `wallet_clusters` table.
- **Entity_Type**: A classification field on an owner record (e.g., `individual`, `organization`) describing the nature of the entity. Stored in the `owner_list` table.
- **List_Category**: A classification field on an owner record (e.g., `watchlist`, `sanction`, `exchange`, `merchant`) describing the owner's category. Stored in the `owner_list` table.

---

## Requirements

### Requirement 1: Duplicate Address Detection on New Entity Creation

**User Story:** As an analyst, I want to be warned when an address I'm adding already belongs to another owner, so that I can make an informed decision before reassigning it.

#### Acceptance Criteria

1. WHEN an analyst submits the Owner_List_Modal with at least one address that is already a Duplicate_Address, THE Owner_API SHALL return a 409 status code with a response body identifying each conflicting address and the name of its current owner.
2. WHEN the Owner_List_Modal receives a 409 response from the Owner_API, THE Owner_List_Modal SHALL display a Confirmation_Dialog before allowing the submission to proceed.
3. THE Confirmation_Dialog SHALL display the message "One or more addresses you entered are already assigned to an existing owner. Do you want to reassign them to this new entity?" with Confirm and Cancel buttons.
4. WHEN the analyst confirms the reassignment in the Confirmation_Dialog, THE Owner_List_Modal SHALL resubmit the request to the Owner_API with an explicit `force_override: true` flag.
5. WHEN the Owner_API receives a request with `force_override: true` and a Duplicate_Address, THE Owner_API SHALL reassign the address to the new owner and return a 200 status code.
6. WHEN the analyst cancels the Confirmation_Dialog, THE Owner_List_Modal SHALL dismiss the dialog and return the analyst to the form without submitting the request.
7. IF all submitted addresses are new (not Duplicate_Addresses), THEN THE Owner_API SHALL create the owner record and address associations without triggering a 409 response.

---

### Requirement 2: Owner Info Section in Graph Address Panel

**User Story:** As an analyst, I want to see basic owner information when I click on an address node in the graph, so that I can identify who controls an address without leaving the graph view.

#### Acceptance Criteria

1. WHEN an analyst clicks an address node in the Graph_Explorer, THE Address_Panel SHALL display a compact owner section showing the owner's `full_name`, `entity_type`, and `list_category`.
2. WHEN the Address_Panel is opened for an address that has no linked Owner_Profile, THE Address_Panel SHALL display "Unassigned" in the owner section.
3. WHEN the Address_Panel is loading owner data, THE Address_Panel SHALL display a loading indicator in the owner section until the data is available.
4. IF the Owner_API returns an error when fetching owner data for an address, THEN THE Address_Panel SHALL display an "Owner data unavailable" message in the owner section without hiding the existing transaction statistics.
5. THE Address_Panel SHALL preserve all existing content (stats grid, Etherscan links, recent transactions list) and add the owner section without removing or rearranging existing elements.

---

### Requirement 3: Owner Profile API Endpoint for Address Lookup

**User Story:** As a frontend developer, I want a dedicated API endpoint to look up owner profile data by blockchain address, so that the Graph Explorer can fetch ownership information efficiently.

#### Acceptance Criteria

1. THE Owner_API SHALL expose a GET endpoint at `/api/clusters/owner-by-address/{address}` that accepts a blockchain address as a path parameter.
2. WHEN the endpoint receives a valid address that is linked to an Owner_Profile, THE Owner_API SHALL return a JSON object containing `owner_id`, `full_name`, `entity_type`, `list_category`, and `risk_level`.
3. WHEN the endpoint receives an address that is not linked to any Owner_Profile, THE Owner_API SHALL return a 200 status code with a JSON body of `{"owner": null}`.
4. IF the endpoint receives a request while the MySQL connection is unavailable, THEN THE Owner_API SHALL return a 503 status code with a descriptive error message.
5. THE Owner_API SHALL resolve the owner profile by joining `owner_list_addresses` to `owner_list`, and joining `addresses` to `wallet_clusters` to retrieve the `risk_level` associated with the address's cluster.
6. WHEN the endpoint is called with the same address multiple times, THE Owner_API SHALL return consistent results as long as the underlying data has not changed (idempotent read).
