# Building SOP Stress Test Runbook

## Summary
- Use the shell harness for fast local/CI regression, flake detection, and large-payload smoke coverage.
- Use Chrome MCP on stage for full portal checklist CRUD, scoped-access checks, and SSR history/proof rendering.
- Treat the shell suite as the gate before any live browser pass.

## Shell Commands
- Baseline SOP suite:
  ```bash
  python scripts/run_building_sop_stress.py -- -q
  ```
- Ten-loop flake pass:
  ```bash
  python scripts/run_building_sop_stress.py --loops 10 -- -q
  ```
- Include dispatch-side SSR snapshot coverage:
  ```bash
  python scripts/run_building_sop_stress.py --include-dispatch --loops 3 -- -q
  ```
- Narrow to one file and one subset:
  ```bash
  python scripts/run_building_sop_stress.py --tests pikt_inc/tests/test_customer_portal.py -- -k building_sop -q
  ```

## Shell Acceptance
- `pikt_inc/tests/test_building_sop.py`, `pikt_inc/tests/test_customer_portal.py`, and `pikt_inc/tests/test_page_views.py` pass once.
- A `--loops 10` run completes with zero flakes.
- Large in-memory SOP coverage passes:
  - 50-item normalization
  - 100-item normalization
  - repeated version creation
  - 100-row SSR snapshot refresh
- No unexpected slowdown trend appears across repeated runs.

## Stage Fixture Matrix
- Use a unique prefix for every browser pass, for example `SOP Stress <timestamp>`.
- Seed these stage records before opening Chrome:
  - one in-scope portal user/customer/building for checklist CRUD
  - one out-of-scope customer/building for denial checks
  - one empty-checklist building
  - one building with an existing SOP
  - one SSR-backed building with:
    - one legacy visit with no checklist snapshot
    - one visit with checklist snapshot and proof
    - one visit with checklist snapshot and exception note
- Prepare SSR history and proof rows through Desk/admin setup rather than generic child-table API mutation.

## Chrome MCP Scenario Order
- Open the in-scope building at `/portal/locations?building=...`.
- Desktop viewport pass:
  - confirm the checklist editor initializes on first load
  - create 1 item, save, confirm success, confirm version bump
  - add a second item, save, reload, confirm exact persisted titles/descriptions/proof flags
  - edit an existing item title and description, toggle `requires_photo_proof`, save, reload, confirm persistence
  - reorder item 2 above item 1, save, reload, confirm order is preserved
  - remove one saved item while keeping another, save, reload, confirm the remaining row and version bump
  - remove all items, save, confirm `No checklist items yet` and `0 items`
- Mobile-sized viewport pass (`390x844`):
  - confirm the editor is usable
  - confirm add, edit, save, and success-state rendering still work
- Behavioral checks:
  - submit controls disable while saving
  - only one success message is shown
  - duplicate click does not create duplicate rows or duplicate versions from one submit
  - blank-title row is blocked client-side
  - a failed save attempt does not leave the page unusable
- Scope/security checks:
  - out-of-scope `?building=` deep-link does not expose the target building
  - out-of-scope POST to `update_customer_portal_building_sop` returns denial
  - proof download succeeds for the in-scope user and fails for the out-of-scope user
- History/proof checks:
  - checklist-enabled visits render item status, exception note, and proof links
  - proof downloads the expected file
  - legacy visits without checklist snapshots render the no-checklist state cleanly

## Cleanup
- If you reuse a smoke building, restore its `Building.current_sop` pointer and any location-field edits changed during the run.
- Delete disposable SOP versions, SSRs, proof files, and test buildings with an admin-capable account.
- If cleanup is blocked by permissions, record the remaining document names in the run notes.

## Pass / Fail Checklist
- Shell baseline passes.
- Shell repeated-loop run passes with zero flakes.
- Full browser checklist CRUD passes on stage.
- Out-of-scope route and POST denial checks pass.
- Proof download scope checks pass.
- SSR history renders correctly for checklist and non-checklist visits.
- No raw server error reaches the browser.
- Cleanup is complete, or residue is explicitly documented.
