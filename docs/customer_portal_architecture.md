# Customer Portal Architecture

The customer-facing portal uses a hybrid architecture on purpose.

- Stock ERPNext portal routes remain the system of record for transaction and support flows:
  - `/quotations`
  - `/orders`
  - `/invoices`
  - `/issues`
- Thin app-owned read-only routes cover the custom account records ERPNext does not expose out of the box:
  - `/agreements`
  - `/business-agreements`
  - `/buildings`

Current boundaries:

- Editing and authoring are out of scope for this portal layer.
- Legacy `/portal` pages remain in the repo temporarily for rollback/reference, but they are not part of the supported customer experience.
- Permissions remain scoped through the existing `Customer Portal User` permission hooks for `Building`, `Service Agreement`, and `Service Agreement Addendum`.
