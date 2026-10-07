# ConMan v2 — Step 7: Seating Preferences & Planning

Step 7 changes seating from a single final assignment into a staged workflow:

```text
Vendor registration
→ organizer approval
→ seating preferences
→ automatic plan variants
→ organizer manual review
→ final seating
```

## Vendor preferences

After a Booking becomes `APPROVED`, ConMan prepares an individual seating-preference record.

The event has a separate switch:

```text
seating_preferences_open
```

When it is enabled, an approved vendor can open:

```text
/preferences
```

and identify their application by Booking code + vendor e-mail, or use the invitation link copied by an organizer.

The vendor can specify:

- several preferred zones with priority 1–5;
- several preferred tables with priority 1–5;
- whether other zones/tables are acceptable;
- vendors they prefer to sit near;
- vendors they prefer not to sit near;
- hard `MUST_NEAR` / `MUST_NOT_NEAR` constraints;
- free-form notes.

Preferences can be saved as `DRAFT` and later submitted as `SUBMITTED`.

Only submitted preferences affect automatic planning.

## Plan versions

Automatic planning never writes directly to final `TableAssignment`.

Each generated alternative is stored as:

```text
SeatingPlan
└── SeatingPlanAssignment[]
```

A plan contains:

- score 0–100;
- number of hard conflicts;
- number of unassigned vendors;
- independent table/slot assignments;
- per-booking explanation of why a position was selected.

This allows multiple alternatives to coexist without changing the live seating.

## Automatic solver

The initial solver is a deterministic/randomized heuristic rather than an external optimization engine.

It considers:

- FULL vs HALF slot capacity;
- table preferences;
- zone preferences;
- allow/disallow fallback tables/zones;
- table coordinates;
- near / avoid relationships;
- hard adjacency constraints.

Several attempts are generated internally and the best distinct variants are persisted.

Default proximity distance is 220 layout pixels and can be changed through the planning API.

## Manual review

The organizer opens a generated plan in:

```text
Планирование → Ручная корректировка
```

and can:

- move a vendor to another A/B slot;
- remove a vendor from a plan;
- resolve conflicts;
- inspect “Почему здесь” explanations;
- see unassigned vendors;
- finalize the selected plan.

A DRAFT plan with conflicts or unassigned vendors cannot be finalized normally.

## Finalization

When a plan is finalized:

1. existing final `TableAssignment` rows for the event are replaced;
2. `SeatingPlanAssignment` rows are copied into final `TableAssignment`;
3. assigned bookings receive `SeatingStatus = FINALIZED`;
4. other plans for the event are archived;
5. the selected plan becomes `FINALIZED`.

The existing “Рассадка” page remains the operational view of final seating and can still be used for last manual adjustments.

## New migration

```text
0005_checkin_badges
  ↓
0006_seating_planning
```

New tables:

```text
seating_preferences
seating_table_preferences
seating_zone_preferences
seating_adjacency_preferences
seating_plans
seating_plan_assignments
```

New event field:

```text
events.seating_preferences_open
```

## Public API

```text
POST /api/public/preferences/access
GET  /api/public/preferences/{token}
PUT  /api/public/preferences/{token}
```

## Organizer API

```text
GET    /api/planning
POST   /api/planning/preferences/prepare
POST   /api/planning/generate
GET    /api/planning/plans/{plan_id}
POST   /api/planning/plans/{plan_id}/assign
POST   /api/planning/plans/{plan_id}/unassign
POST   /api/planning/plans/{plan_id}/finalize
DELETE /api/planning/plans/{plan_id}
```

## Suggested test scenario

1. Create/select an event with zones and tables.
2. Approve several vendor applications.
3. Open seating preference collection for the event.
4. In Planning → Preferences, click “Подготовить ссылки” for older approved bookings.
5. Copy a vendor preference link.
6. Submit several table/zone choices and near/avoid relationships.
7. Submit preferences.
8. Generate three automatic variants.
9. Compare score/conflicts/unassigned values.
10. Open one plan and inspect “Почему здесь”.
11. Move several vendors manually.
12. Resolve all hard conflicts and unassigned vendors.
13. Finalize the plan.
14. Open regular “Рассадка” and verify that the finalized assignments are now the live seating.
