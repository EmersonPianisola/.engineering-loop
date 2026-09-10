# Example Work Item

## Business Goal
Build an inventory analysis dashboard that helps users make informed product decisions.

## Problem Statement
Users currently have access to basic stock numbers but lack insight into what those numbers mean for their business. They need to understand: what happened with each product in a period, how purchases match sales, and what decisions to make about restocking or discontinuing.

## Acceptance Criteria
1. Dashboard shows inventory movement (in/out) per product for a given period
2. Purchase quantities reconcile with sales + stock changes
3. Discrepancies are flagged with severity indicators
4. Users can filter by product, category, date range
5. Export functionality for reports

## Complexity Classification
- **Size:** Medium (multiple components, data reconciliation logic)
- **UI:** Yes (dashboard, charts, filters)
- **Tags:** ["analytics", "reconciliation", "dashboard"]

## Dependencies
- Database with inventory, sales, and purchase records
- Authentication system (existing)

## Out of Scope
- Real-time inventory tracking
- Supplier integration
- Mobile app
