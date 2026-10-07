import math
import random
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    Booking,
    Event,
    LayoutTable,
    LayoutZone,
    SeatingAdjacencyPreference,
    SeatingPlan,
    SeatingPlanAssignment,
    SeatingPreference,
    SeatingTablePreference,
    SeatingZonePreference,
    TableAssignment,
    Vendor,
)
from app.services.codes import next_code
from app.services.core import booking_dict, current_event_id, event_dict
from app.services.seating import table_dict, zone_dict


ELIGIBLE_BOOKING_STATUSES = [
    "APPROVED",
    "AWAITING_PAYMENT",
    "CONFIRMED",
]

HARD_ADJACENCY_TYPES = {
    "MUST_NEAR",
    "MUST_NOT_NEAR",
}


def _preference_load_options():
    return [
        selectinload(SeatingPreference.table_preferences),
        selectinload(SeatingPreference.zone_preferences),
        selectinload(SeatingPreference.adjacency_preferences),
        selectinload(SeatingPreference.booking).selectinload(Booking.vendor),
    ]


def _booking_with_preference_options():
    return [
        selectinload(Booking.vendor),
        selectinload(Booking.seating_preference).selectinload(
            SeatingPreference.table_preferences
        ),
        selectinload(Booking.seating_preference).selectinload(
            SeatingPreference.zone_preferences
        ),
        selectinload(Booking.seating_preference).selectinload(
            SeatingPreference.adjacency_preferences
        ),
    ]


def preference_dict(preference: SeatingPreference) -> dict:
    return {
        "id": str(preference.id),
        "code": preference.code,
        "event_id": str(preference.event_id),
        "booking_id": str(preference.booking_id),
        "status": preference.status,
        "allow_other_tables": preference.allow_other_tables,
        "allow_other_zones": preference.allow_other_zones,
        "notes": preference.notes,
        "submitted_at": preference.submitted_at,
        "table_preferences": [
            {
                "table_id": str(item.table_id),
                "priority": item.priority,
            }
            for item in sorted(
                preference.table_preferences,
                key=lambda item: (-item.priority, str(item.table_id)),
            )
        ],
        "zone_preferences": [
            {
                "zone_id": str(item.zone_id),
                "priority": item.priority,
            }
            for item in sorted(
                preference.zone_preferences,
                key=lambda item: (-item.priority, str(item.zone_id)),
            )
        ],
        "adjacency_preferences": [
            {
                "target_booking_id": str(item.target_booking_id),
                "preference_type": item.preference_type,
                "weight": item.weight,
                "notes": item.notes,
            }
            for item in sorted(
                preference.adjacency_preferences,
                key=lambda item: (
                    item.preference_type,
                    -item.weight,
                    str(item.target_booking_id),
                ),
            )
        ],
    }


def ensure_preference(
    db: Session,
    booking: Booking,
) -> SeatingPreference:
    preference = db.scalar(
        select(SeatingPreference)
        .where(SeatingPreference.booking_id == booking.id)
        .options(*_preference_load_options())
    )
    if preference:
        return preference

    preference = SeatingPreference(
        code=next_code(db, "SPF"),
        event_id=booking.event_id,
        booking_id=booking.id,
        access_token=secrets.token_urlsafe(48),
        status="DRAFT",
        allow_other_tables=True,
        allow_other_zones=True,
    )
    db.add(preference)

    if booking.seating_status in {
        "UNASSIGNED",
        "PREFERENCES_PENDING",
    }:
        booking.seating_status = "PREFERENCES_PENDING"

    db.flush()
    return preference


def prepare_preferences_for_event(
    db: Session,
    event_id: UUID,
) -> list[SeatingPreference]:
    bookings = db.scalars(
        select(Booking)
        .where(
            Booking.event_id == event_id,
            Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
        )
        .options(selectinload(Booking.seating_preference))
        .order_by(Booking.code)
    ).all()

    result = []
    for booking in bookings:
        if booking.seating_preference:
            result.append(booking.seating_preference)
        else:
            result.append(ensure_preference(db, booking))

    db.flush()
    return result


def get_preference_by_token(
    db: Session,
    token: str,
) -> SeatingPreference:
    preference = db.scalar(
        select(SeatingPreference)
        .where(SeatingPreference.access_token == token)
        .options(*_preference_load_options())
    )
    if not preference:
        raise HTTPException(
            status_code=404,
            detail="Preference link not found",
        )
    return preference


def _assert_public_preferences_available(
    db: Session,
    preference: SeatingPreference,
) -> tuple[Booking, Event]:
    booking = db.scalar(
        select(Booking)
        .where(Booking.id == preference.booking_id)
        .options(selectinload(Booking.vendor))
    )
    event = db.get(Event, preference.event_id)

    if not booking or not event:
        raise HTTPException(
            status_code=404,
            detail="Booking or event not found",
        )

    if booking.booking_status not in ELIGIBLE_BOOKING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seating preferences are available only for approved vendors",
        )

    if not event.seating_preferences_open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seating preferences are closed for this event",
        )

    return booking, event


def public_preference_access(
    db: Session,
    booking_code: str,
    email: str,
) -> dict:
    booking = db.scalar(
        select(Booking)
        .join(Vendor, Vendor.id == Booking.vendor_id)
        .where(
            func.upper(Booking.code) == booking_code.strip().upper(),
            func.lower(Vendor.email) == email.strip().lower(),
        )
        .options(
            selectinload(Booking.vendor),
            selectinload(Booking.seating_preference),
        )
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking code or vendor e-mail is incorrect",
        )

    if booking.booking_status not in ELIGIBLE_BOOKING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="The application has not been approved for seating preferences",
        )

    event = db.get(Event, booking.event_id)
    if not event or not event.seating_preferences_open:
        raise HTTPException(
            status_code=409,
            detail="Seating preferences are closed for this event",
        )

    preference = (
        booking.seating_preference
        or ensure_preference(db, booking)
    )
    db.commit()

    return {
        "token": preference.access_token,
        "data": public_preference_payload(
            db,
            preference.access_token,
        ),
    }


def public_preference_payload(
    db: Session,
    token: str,
) -> dict:
    preference = get_preference_by_token(db, token)
    booking, event = _assert_public_preferences_available(
        db,
        preference,
    )

    zones = db.scalars(
        select(LayoutZone)
        .where(
            LayoutZone.event_id == event.id,
            LayoutZone.active.is_(True),
        )
        .order_by(LayoutZone.sort_order, LayoutZone.zone_name)
    ).all()

    tables = db.scalars(
        select(LayoutTable)
        .where(
            LayoutTable.event_id == event.id,
            LayoutTable.active.is_(True),
        )
        .order_by(LayoutTable.table_number, LayoutTable.sort_order)
    ).all()

    peers = db.scalars(
        select(Booking)
        .where(
            Booking.event_id == event.id,
            Booking.id != booking.id,
            Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
        )
        .options(selectinload(Booking.vendor))
        .order_by(Booking.code)
    ).all()

    zone_names = {
        zone.id: zone.zone_name
        for zone in zones
    }

    table_rows = []
    for table in tables:
        row = table_dict(table)
        row["zone_name"] = (
            zone_names.get(table.zone_id)
            if table.zone_id
            else None
        )
        table_rows.append(row)

    return {
        "event": event_dict(event),
        "booking": {
            "id": str(booking.id),
            "code": booking.code,
            "booking_type": booking.booking_type,
            "booking_status": booking.booking_status,
            "vendor_name": (
                booking.vendor.vendor_name
                if booking.vendor
                else booking.code
            ),
        },
        "preference": preference_dict(preference),
        "zones": [zone_dict(zone) for zone in zones],
        "tables": table_rows,
        "vendors": [
            {
                "booking_id": str(item.id),
                "booking_code": item.code,
                "vendor_name": (
                    item.vendor.vendor_name
                    if item.vendor
                    else item.code
                ),
            }
            for item in peers
        ],
    }


def save_public_preference(
    db: Session,
    token: str,
    payload,
) -> dict:
    preference = get_preference_by_token(db, token)
    booking, event = _assert_public_preferences_available(
        db,
        preference,
    )

    table_ids = {
        item.table_id
        for item in payload.table_preferences
    }
    zone_ids = {
        item.zone_id
        for item in payload.zone_preferences
    }
    target_booking_ids = {
        item.target_booking_id
        for item in payload.adjacency_preferences
    }

    if booking.id in target_booking_ids:
        raise HTTPException(
            status_code=422,
            detail="A vendor cannot select itself as a neighbor",
        )

    valid_tables = set(
        db.scalars(
            select(LayoutTable.id).where(
                LayoutTable.event_id == event.id,
                LayoutTable.id.in_(table_ids) if table_ids else False,
            )
        ).all()
    ) if table_ids else set()

    if valid_tables != table_ids:
        raise HTTPException(
            status_code=409,
            detail="One or more selected tables belong to another event",
        )

    valid_zones = set(
        db.scalars(
            select(LayoutZone.id).where(
                LayoutZone.event_id == event.id,
                LayoutZone.id.in_(zone_ids) if zone_ids else False,
            )
        ).all()
    ) if zone_ids else set()

    if valid_zones != zone_ids:
        raise HTTPException(
            status_code=409,
            detail="One or more selected zones belong to another event",
        )

    valid_targets = set(
        db.scalars(
            select(Booking.id).where(
                Booking.event_id == event.id,
                Booking.id.in_(target_booking_ids)
                if target_booking_ids
                else False,
                Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
            )
        ).all()
    ) if target_booking_ids else set()

    if valid_targets != target_booking_ids:
        raise HTTPException(
            status_code=409,
            detail="One or more selected vendors are not eligible for this event",
        )

    preference.table_preferences.clear()
    preference.zone_preferences.clear()
    preference.adjacency_preferences.clear()
    db.flush()

    for item in payload.table_preferences:
        preference.table_preferences.append(
            SeatingTablePreference(
                table_id=item.table_id,
                priority=item.priority,
            )
        )

    for item in payload.zone_preferences:
        preference.zone_preferences.append(
            SeatingZonePreference(
                zone_id=item.zone_id,
                priority=item.priority,
            )
        )

    for item in payload.adjacency_preferences:
        preference.adjacency_preferences.append(
            SeatingAdjacencyPreference(
                target_booking_id=item.target_booking_id,
                preference_type=item.preference_type,
                weight=item.weight,
                notes=item.notes,
            )
        )

    preference.allow_other_tables = payload.allow_other_tables
    preference.allow_other_zones = payload.allow_other_zones
    preference.notes = payload.notes

    if payload.submit:
        preference.status = "SUBMITTED"
        preference.submitted_at = datetime.now(UTC)
        booking.seating_status = "PREFERENCES_SUBMITTED"
    else:
        preference.status = "DRAFT"
        preference.submitted_at = None
        if booking.seating_status not in {"ASSIGNED", "FINALIZED"}:
            booking.seating_status = "PREFERENCES_PENDING"

    db.flush()
    db.commit()

    return public_preference_payload(db, token)


def planning_overview(
    db: Session,
    event_id: UUID | None,
) -> dict:
    event_id = event_id or current_event_id(db)
    if not event_id:
        return {
            "event": None,
            "summary": {
                "eligible": 0,
                "submitted": 0,
                "pending": 0,
                "plans": 0,
            },
            "bookings": [],
            "plans": [],
        }

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    bookings = db.scalars(
        select(Booking)
        .where(
            Booking.event_id == event_id,
            Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
        )
        .options(*_booking_with_preference_options())
        .order_by(Booking.code)
    ).all()

    plans = db.scalars(
        select(SeatingPlan)
        .where(SeatingPlan.event_id == event_id)
        .order_by(
            SeatingPlan.created_at.desc(),
            SeatingPlan.code.desc(),
        )
    ).all()

    rows = []
    submitted = 0
    for booking in bookings:
        preference = booking.seating_preference
        if preference and preference.status == "SUBMITTED":
            submitted += 1

        rows.append({
            "booking_id": str(booking.id),
            "booking_code": booking.code,
            "booking_type": booking.booking_type,
            "booking_status": booking.booking_status,
            "seating_status": booking.seating_status,
            "vendor_name": (
                booking.vendor.vendor_name
                if booking.vendor
                else booking.code
            ),
            "vendor_email": (
                booking.vendor.email
                if booking.vendor
                else ""
            ),
            "preference": (
                preference_dict(preference)
                if preference
                else None
            ),
            "preference_token": (
                preference.access_token
                if preference
                else None
            ),
        })

    return {
        "event": event_dict(event),
        "summary": {
            "eligible": len(bookings),
            "submitted": submitted,
            "pending": len(bookings) - submitted,
            "plans": len(plans),
        },
        "bookings": rows,
        "plans": [
            plan_summary_dict(plan)
            for plan in plans
        ],
    }


def plan_summary_dict(plan: SeatingPlan) -> dict:
    return {
        "id": str(plan.id),
        "code": plan.code,
        "event_id": str(plan.event_id),
        "plan_name": plan.plan_name,
        "plan_type": plan.plan_type,
        "status": plan.status,
        "score": float(plan.score or 0),
        "conflicts_count": plan.conflicts_count,
        "unassigned_count": plan.unassigned_count,
        "notes": plan.notes,
        "finalized_at": plan.finalized_at,
        "created_at": plan.created_at,
    }


def _load_plan(
    db: Session,
    plan_id: UUID,
) -> SeatingPlan:
    plan = db.scalar(
        select(SeatingPlan)
        .where(SeatingPlan.id == plan_id)
        .options(
            selectinload(SeatingPlan.assignments)
            .selectinload(SeatingPlanAssignment.booking)
            .selectinload(Booking.vendor),
            selectinload(SeatingPlan.assignments)
            .selectinload(SeatingPlanAssignment.table),
        )
    )
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Seating plan not found",
        )
    return plan


def plan_detail(
    db: Session,
    plan_id: UUID,
) -> dict:
    plan = _load_plan(db, plan_id)

    bookings = db.scalars(
        select(Booking)
        .where(
            Booking.event_id == plan.event_id,
            Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
        )
        .options(selectinload(Booking.vendor))
        .order_by(Booking.code)
    ).all()

    tables = db.scalars(
        select(LayoutTable)
        .where(
            LayoutTable.event_id == plan.event_id,
            LayoutTable.active.is_(True),
        )
        .order_by(LayoutTable.table_number)
    ).all()

    zones = db.scalars(
        select(LayoutZone)
        .where(
            LayoutZone.event_id == plan.event_id,
            LayoutZone.active.is_(True),
        )
        .order_by(LayoutZone.sort_order, LayoutZone.zone_name)
    ).all()

    assignments = sorted(
        plan.assignments,
        key=lambda item: (
            item.table.table_number if item.table else 999999,
            item.start_slot,
        ),
    )

    return {
        "plan": plan_summary_dict(plan),
        "assignments": [
            {
                "id": str(item.id),
                "code": item.code,
                "plan_id": str(item.plan_id),
                "event_id": str(item.event_id),
                "booking_id": str(item.booking_id),
                "table_id": str(item.table_id),
                "start_slot": item.start_slot,
                "slot_count": item.slot_count,
                "score": float(item.score or 0),
                "explanation": item.explanation or {},
                "booking": {
                    "id": str(item.booking.id),
                    "code": item.booking.code,
                    "booking_type": item.booking.booking_type,
                    "vendor_name": (
                        item.booking.vendor.vendor_name
                        if item.booking.vendor
                        else item.booking.code
                    ),
                }
                if item.booking
                else None,
                "table": table_dict(item.table) if item.table else None,
            }
            for item in assignments
        ],
        "bookings": [
            {
                "id": str(booking.id),
                "code": booking.code,
                "booking_type": booking.booking_type,
                "vendor_name": (
                    booking.vendor.vendor_name
                    if booking.vendor
                    else booking.code
                ),
            }
            for booking in bookings
        ],
        "tables": [table_dict(table) for table in tables],
        "zones": [zone_dict(zone) for zone in zones],
    }


def _table_center(table: LayoutTable) -> tuple[float, float]:
    return (
        table.x + table.width / 2,
        table.y + table.height / 2,
    )


def _near(
    first: LayoutTable,
    second: LayoutTable,
    near_distance: float,
) -> bool:
    ax, ay = _table_center(first)
    bx, by = _table_center(second)
    return math.hypot(ax - bx, ay - by) <= near_distance


def _candidate_positions(
    booking: Booking,
    tables: list[LayoutTable],
    preference: SeatingPreference | None,
) -> list[tuple[LayoutTable, int, int, float]]:
    slot_count = 2 if booking.booking_type == "FULL" else 1
    table_priorities = {
        item.table_id: item.priority
        for item in (
            preference.table_preferences
            if preference
            else []
        )
    }
    zone_priorities = {
        item.zone_id: item.priority
        for item in (
            preference.zone_preferences
            if preference
            else []
        )
    }

    result = []
    for table in tables:
        if table.capacity_slots < slot_count:
            continue

        if (
            preference
            and not preference.allow_other_tables
            and table_priorities
            and table.id not in table_priorities
        ):
            continue

        if (
            preference
            and not preference.allow_other_zones
            and zone_priorities
            and table.zone_id not in zone_priorities
        ):
            continue

        base = 0.0
        if table_priorities:
            base += table_priorities.get(table.id, 0) * 25.0
        if zone_priorities and table.zone_id:
            base += zone_priorities.get(table.zone_id, 0) * 12.0

        starts = [1] if slot_count == 2 else list(
            range(1, table.capacity_slots + 1)
        )
        for start_slot in starts:
            result.append(
                (
                    table,
                    start_slot,
                    slot_count,
                    base,
                )
            )

    return result


def _slots(
    table_id: UUID,
    start_slot: int,
    slot_count: int,
) -> set[tuple[UUID, int]]:
    return {
        (table_id, slot)
        for slot in range(
            start_slot,
            start_slot + slot_count,
        )
    }


def _adjacency_dynamic_score(
    booking_id: UUID,
    candidate_table: LayoutTable,
    solution: dict[UUID, dict],
    table_by_id: dict[UUID, LayoutTable],
    adjacency_by_source: dict[UUID, list[SeatingAdjacencyPreference]],
    adjacency_by_target: dict[UUID, list[tuple[UUID, SeatingAdjacencyPreference]]],
    near_distance: float,
) -> float:
    score = 0.0

    relations: list[tuple[UUID, SeatingAdjacencyPreference]] = []
    relations.extend(
        (
            relation.target_booking_id,
            relation,
        )
        for relation in adjacency_by_source.get(
            booking_id,
            [],
        )
    )
    relations.extend(
        adjacency_by_target.get(
            booking_id,
            [],
        )
    )

    for other_id, relation in relations:
        other = solution.get(other_id)
        if not other:
            continue

        other_table = table_by_id.get(
            other["table_id"]
        )
        if not other_table:
            continue

        is_near = _near(
            candidate_table,
            other_table,
            near_distance,
        )
        weight = relation.weight

        if relation.preference_type == "MUST_NEAR":
            score += (
                weight * 55.0
                if is_near
                else -weight * 220.0
            )
        elif relation.preference_type == "PREFER_NEAR":
            score += (
                weight * 20.0
                if is_near
                else -weight * 3.0
            )
        elif relation.preference_type == "AVOID_NEAR":
            score += (
                -weight * 20.0
                if is_near
                else weight * 4.0
            )
        elif relation.preference_type == "MUST_NOT_NEAR":
            score += (
                -weight * 260.0
                if is_near
                else weight * 45.0
            )

    return score


def _evaluate_solution(
    bookings: list[Booking],
    tables: list[LayoutTable],
    solution: dict[UUID, dict],
    preferences: dict[UUID, SeatingPreference],
    near_distance: float,
) -> dict:
    table_by_id = {
        table.id: table
        for table in tables
    }
    booking_by_id = {
        booking.id: booking
        for booking in bookings
    }

    components: list[float] = []
    conflicts = 0
    explanations: dict[UUID, list[str]] = {
        booking.id: []
        for booking in bookings
    }

    for booking in bookings:
        placement = solution.get(booking.id)
        preference = preferences.get(booking.id)

        if not placement:
            explanations[booking.id].append(
                "Не удалось подобрать свободное место."
            )
            continue

        table = table_by_id[placement["table_id"]]

        if preference and preference.table_preferences:
            priorities = {
                item.table_id: item.priority
                for item in preference.table_preferences
            }
            maximum = max(priorities.values())
            selected = priorities.get(table.id, 0)
            ratio = (
                selected / maximum
                if selected
                else 0.30
            )
            components.append(ratio * 100)
            if selected:
                explanations[booking.id].append(
                    f"Выбран желаемый стол с приоритетом {selected}/5."
                )
            else:
                explanations[booking.id].append(
                    "Выбран допустимый стол вне списка предпочтительных."
                )

        if preference and preference.zone_preferences:
            priorities = {
                item.zone_id: item.priority
                for item in preference.zone_preferences
            }
            maximum = max(priorities.values())
            selected = (
                priorities.get(table.zone_id, 0)
                if table.zone_id
                else 0
            )
            ratio = (
                selected / maximum
                if selected
                else 0.30
            )
            components.append(ratio * 100)
            if selected:
                explanations[booking.id].append(
                    f"Выбрана желаемая зона с приоритетом {selected}/5."
                )
            else:
                explanations[booking.id].append(
                    "Выбрана допустимая зона вне списка предпочтительных."
                )

    seen_relations: set[tuple[UUID, UUID, str]] = set()
    for source_id, preference in preferences.items():
        source_placement = solution.get(source_id)

        for relation in preference.adjacency_preferences:
            target_id = relation.target_booking_id
            key = (
                source_id,
                target_id,
                relation.preference_type,
            )
            if key in seen_relations:
                continue
            seen_relations.add(key)

            target_placement = solution.get(target_id)

            if not source_placement or not target_placement:
                if relation.preference_type in HARD_ADJACENCY_TYPES:
                    conflicts += 1
                    components.append(0)
                else:
                    components.append(50)
                continue

            source_table = table_by_id[
                source_placement["table_id"]
            ]
            target_table = table_by_id[
                target_placement["table_id"]
            ]
            is_near = _near(
                source_table,
                target_table,
                near_distance,
            )

            target_name = (
                booking_by_id[target_id].vendor.vendor_name
                if target_id in booking_by_id
                and booking_by_id[target_id].vendor
                else "выбранного вендора"
            )

            if relation.preference_type == "MUST_NEAR":
                ok = is_near
                components.append(100 if ok else 0)
                if not ok:
                    conflicts += 1
                explanations[source_id].append(
                    (
                        f"Жёсткое пожелание рядом с {target_name} выполнено."
                        if ok
                        else f"КОНФЛИКТ: требуется место рядом с {target_name}."
                    )
                )
            elif relation.preference_type == "PREFER_NEAR":
                components.append(100 if is_near else 25)
                explanations[source_id].append(
                    (
                        f"Пожелание сидеть рядом с {target_name} выполнено."
                        if is_near
                        else f"Не удалось посадить рядом с {target_name}."
                    )
                )
            elif relation.preference_type == "AVOID_NEAR":
                ok = not is_near
                components.append(100 if ok else 25)
                explanations[source_id].append(
                    (
                        f"Пожелание не сидеть рядом с {target_name} выполнено."
                        if ok
                        else f"Нежелательное соседство с {target_name}."
                    )
                )
            elif relation.preference_type == "MUST_NOT_NEAR":
                ok = not is_near
                components.append(100 if ok else 0)
                if not ok:
                    conflicts += 1
                explanations[source_id].append(
                    (
                        f"Жёсткое ограничение не сидеть рядом с {target_name} выполнено."
                        if ok
                        else f"КОНФЛИКТ: нельзя размещать рядом с {target_name}."
                    )
                )

    assigned = len(solution)
    total = len(bookings)
    unassigned = max(total - assigned, 0)

    completeness = (
        assigned / total * 100
        if total
        else 100.0
    )
    preference_score = (
        sum(components) / len(components)
        if components
        else 100.0
    )
    score = max(
        0.0,
        min(
            100.0,
            completeness * 0.55
            + preference_score * 0.45,
        ),
    )

    return {
        "score": round(score, 2),
        "conflicts_count": conflicts,
        "unassigned_count": unassigned,
        "explanations": explanations,
    }


def _build_attempt(
    bookings: list[Booking],
    tables: list[LayoutTable],
    preferences: dict[UUID, SeatingPreference],
    near_distance: float,
    seed: str,
) -> dict:
    rng = random.Random(seed)
    table_by_id = {
        table.id: table
        for table in tables
    }

    adjacency_by_source: dict[
        UUID,
        list[SeatingAdjacencyPreference],
    ] = {}
    adjacency_by_target: dict[
        UUID,
        list[tuple[UUID, SeatingAdjacencyPreference]],
    ] = {}

    for booking_id, preference in preferences.items():
        adjacency_by_source[booking_id] = list(
            preference.adjacency_preferences
        )
        for relation in preference.adjacency_preferences:
            adjacency_by_target.setdefault(
                relation.target_booking_id,
                [],
            ).append(
                (
                    booking_id,
                    relation,
                )
            )

    candidates = {
        booking.id: _candidate_positions(
            booking,
            tables,
            preferences.get(booking.id),
        )
        for booking in bookings
    }

    ordered = sorted(
        bookings,
        key=lambda booking: (
            len(candidates[booking.id]),
            0 if booking.booking_type == "FULL" else 1,
            -(
                len(adjacency_by_source.get(booking.id, []))
                + len(adjacency_by_target.get(booking.id, []))
            ),
            rng.random(),
        ),
    )

    occupied: set[tuple[UUID, int]] = set()
    solution: dict[UUID, dict] = {}

    for booking in ordered:
        ranked = []

        for table, start_slot, slot_count, base in candidates[booking.id]:
            needed = _slots(
                table.id,
                start_slot,
                slot_count,
            )
            if needed & occupied:
                continue

            dynamic = _adjacency_dynamic_score(
                booking.id,
                table,
                solution,
                table_by_id,
                adjacency_by_source,
                adjacency_by_target,
                near_distance,
            )
            diversity = rng.random() * 28.0
            ranked.append(
                (
                    base + dynamic + diversity,
                    table,
                    start_slot,
                    slot_count,
                )
            )

        if not ranked:
            continue

        ranked.sort(
            key=lambda item: item[0],
            reverse=True,
        )
        top = ranked[: min(5, len(ranked))]
        choice_index = min(
            int((rng.random() ** 3) * len(top)),
            len(top) - 1,
        )
        chosen_score, table, start_slot, slot_count = top[
            choice_index
        ]

        occupied |= _slots(
            table.id,
            start_slot,
            slot_count,
        )
        solution[booking.id] = {
            "table_id": table.id,
            "start_slot": start_slot,
            "slot_count": slot_count,
            "placement_score": chosen_score,
        }

    evaluation = _evaluate_solution(
        bookings,
        tables,
        solution,
        preferences,
        near_distance,
    )

    return {
        "solution": solution,
        **evaluation,
    }


def generate_plans(
    db: Session,
    event_id: UUID,
    actor_id: UUID,
    variants: int,
    attempts_per_variant: int,
    near_distance: float,
) -> list[dict]:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    bookings = list(
        db.scalars(
            select(Booking)
            .where(
                Booking.event_id == event_id,
                Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
            )
            .options(*_booking_with_preference_options())
            .order_by(Booking.code)
        ).all()
    )
    if not bookings:
        raise HTTPException(
            status_code=409,
            detail="There are no approved bookings to plan",
        )

    tables = list(
        db.scalars(
            select(LayoutTable)
            .where(
                LayoutTable.event_id == event_id,
                LayoutTable.active.is_(True),
            )
            .order_by(LayoutTable.table_number)
        ).all()
    )
    if not tables:
        raise HTTPException(
            status_code=409,
            detail="There are no active tables for this event",
        )

    preferences = {
        booking.id: booking.seating_preference
        for booking in bookings
        if (
            booking.seating_preference
            and booking.seating_preference.status == "SUBMITTED"
        )
    }

    attempts = max(
        variants * attempts_per_variant,
        variants,
    )
    candidates_by_signature: dict[str, dict] = {}

    for index in range(attempts):
        attempt = _build_attempt(
            bookings,
            tables,
            preferences,
            near_distance,
            seed=f"{event_id}:{index}:{attempts}",
        )

        signature = "|".join(
            f"{booking_id}:{placement['table_id']}:{placement['start_slot']}"
            for booking_id, placement in sorted(
                attempt["solution"].items(),
                key=lambda item: str(item[0]),
            )
        )

        previous = candidates_by_signature.get(signature)
        key = (
            attempt["conflicts_count"],
            attempt["unassigned_count"],
            -attempt["score"],
        )
        if (
            previous is None
            or key
            < (
                previous["conflicts_count"],
                previous["unassigned_count"],
                -previous["score"],
            )
        ):
            candidates_by_signature[signature] = attempt

    selected = sorted(
        candidates_by_signature.values(),
        key=lambda item: (
            item["conflicts_count"],
            item["unassigned_count"],
            -item["score"],
        ),
    )[:variants]

    created: list[SeatingPlan] = []
    for variant_index, candidate in enumerate(
        selected,
        start=1,
    ):
        plan = SeatingPlan(
            code=next_code(db, "PLN"),
            event_id=event_id,
            plan_name=f"Автовариант {variant_index}",
            plan_type="AUTO",
            status="DRAFT",
            score=Decimal(str(candidate["score"])),
            conflicts_count=candidate["conflicts_count"],
            unassigned_count=candidate["unassigned_count"],
            created_by=actor_id,
        )
        db.add(plan)
        db.flush()

        explanations = candidate["explanations"]

        for booking_id, placement in candidate["solution"].items():
            assignment = SeatingPlanAssignment(
                code=next_code(db, "PLA"),
                plan_id=plan.id,
                event_id=event_id,
                booking_id=booking_id,
                table_id=placement["table_id"],
                start_slot=placement["start_slot"],
                slot_count=placement["slot_count"],
                score=Decimal(
                    str(
                        round(
                            placement["placement_score"],
                            2,
                        )
                    )
                ),
                explanation={
                    "items": explanations.get(
                        booking_id,
                        [],
                    )
                },
                created_by=actor_id,
            )
            db.add(assignment)

        created.append(plan)

    for booking in bookings:
        if booking.seating_status != "FINALIZED":
            booking.seating_status = "PLANNING"

    db.flush()

    return [
        plan_summary_dict(plan)
        for plan in created
    ]


def _solution_from_plan(
    plan: SeatingPlan,
) -> dict[UUID, dict]:
    return {
        item.booking_id: {
            "table_id": item.table_id,
            "start_slot": item.start_slot,
            "slot_count": item.slot_count,
            "placement_score": float(item.score or 0),
        }
        for item in plan.assignments
    }


def recalculate_plan(
    db: Session,
    plan: SeatingPlan,
    near_distance: float = 220.0,
) -> None:
    bookings = list(
        db.scalars(
            select(Booking)
            .where(
                Booking.event_id == plan.event_id,
                Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
            )
            .options(*_booking_with_preference_options())
        ).all()
    )
    tables = list(
        db.scalars(
            select(LayoutTable).where(
                LayoutTable.event_id == plan.event_id,
                LayoutTable.active.is_(True),
            )
        ).all()
    )

    preferences = {
        booking.id: booking.seating_preference
        for booking in bookings
        if (
            booking.seating_preference
            and booking.seating_preference.status == "SUBMITTED"
        )
    }
    solution = _solution_from_plan(plan)

    evaluation = _evaluate_solution(
        bookings,
        tables,
        solution,
        preferences,
        near_distance,
    )

    plan.score = Decimal(
        str(evaluation["score"])
    )
    plan.conflicts_count = evaluation[
        "conflicts_count"
    ]
    plan.unassigned_count = evaluation[
        "unassigned_count"
    ]

    explanation_map = evaluation["explanations"]
    for assignment in plan.assignments:
        assignment.explanation = {
            "items": explanation_map.get(
                assignment.booking_id,
                [],
            )
        }

    db.flush()


def place_booking_in_plan(
    db: Session,
    plan_id: UUID,
    booking_id: UUID,
    table_id: UUID,
    start_slot: int,
    actor_id: UUID,
) -> dict:
    plan = _load_plan(db, plan_id)
    if plan.status != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail="Only draft plans can be edited",
        )

    booking = db.get(Booking, booking_id)
    table = db.get(LayoutTable, table_id)
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )
    if not table:
        raise HTTPException(
            status_code=404,
            detail="Table not found",
        )
    if booking.event_id != plan.event_id or table.event_id != plan.event_id:
        raise HTTPException(
            status_code=409,
            detail="Booking, table and plan must belong to the same event",
        )
    if booking.booking_status not in ELIGIBLE_BOOKING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Booking is not eligible for seating planning",
        )

    slot_count = 2 if booking.booking_type == "FULL" else 1
    if slot_count == 2:
        start_slot = 1

    if (
        start_slot < 1
        or start_slot + slot_count - 1 > table.capacity_slots
    ):
        raise HTTPException(
            status_code=409,
            detail="Booking does not fit into target slot",
        )

    current = next(
        (
            item
            for item in plan.assignments
            if item.booking_id == booking.id
        ),
        None,
    )

    target_slots = _slots(
        table.id,
        start_slot,
        slot_count,
    )
    for existing in plan.assignments:
        if current and existing.id == current.id:
            continue
        existing_slots = _slots(
            existing.table_id,
            existing.start_slot,
            existing.slot_count,
        )
        if target_slots & existing_slots:
            raise HTTPException(
                status_code=409,
                detail="Target slot is already occupied in this plan",
            )

    if current:
        current.table_id = table.id
        current.start_slot = start_slot
        current.slot_count = slot_count
        current.created_by = actor_id
    else:
        current = SeatingPlanAssignment(
            code=next_code(db, "PLA"),
            plan_id=plan.id,
            event_id=plan.event_id,
            booking_id=booking.id,
            table_id=table.id,
            start_slot=start_slot,
            slot_count=slot_count,
            created_by=actor_id,
        )
        db.add(current)
        plan.assignments.append(current)

    booking.seating_status = "MANUAL_REVIEW"
    db.flush()
    recalculate_plan(db, plan)

    return plan_detail(db, plan.id)


def unassign_booking_from_plan(
    db: Session,
    plan_id: UUID,
    booking_id: UUID,
) -> dict:
    plan = _load_plan(db, plan_id)
    if plan.status != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail="Only draft plans can be edited",
        )

    assignment = next(
        (
            item
            for item in plan.assignments
            if item.booking_id == booking_id
        ),
        None,
    )
    if assignment:
        plan.assignments.remove(assignment)
        db.flush()

    booking = db.get(Booking, booking_id)
    if booking and booking.seating_status != "FINALIZED":
        booking.seating_status = "MANUAL_REVIEW"

    recalculate_plan(db, plan)
    return plan_detail(db, plan.id)


def finalize_plan(
    db: Session,
    plan_id: UUID,
    actor_id: UUID,
    allow_incomplete: bool,
) -> dict:
    plan = _load_plan(db, plan_id)
    if plan.status != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail="Only draft plans can be finalized",
        )

    recalculate_plan(db, plan)

    if (
        not allow_incomplete
        and (
            plan.conflicts_count > 0
            or plan.unassigned_count > 0
        )
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Plan contains conflicts or unassigned vendors. "
                "Resolve them before finalization."
            ),
        )

    existing = db.scalars(
        select(TableAssignment).where(
            TableAssignment.event_id == plan.event_id
        )
    ).all()
    for item in existing:
        db.delete(item)
    db.flush()

    assigned_booking_ids: set[UUID] = set()

    for item in plan.assignments:
        db.add(
            TableAssignment(
                code=next_code(db, "ASN"),
                event_id=plan.event_id,
                table_id=item.table_id,
                booking_id=item.booking_id,
                start_slot=item.start_slot,
                slot_count=item.slot_count,
                active=True,
                notes=f"Finalized from {plan.code}",
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        assigned_booking_ids.add(
            item.booking_id
        )

    eligible = db.scalars(
        select(Booking).where(
            Booking.event_id == plan.event_id,
            Booking.booking_status.in_(ELIGIBLE_BOOKING_STATUSES),
        )
    ).all()
    for booking in eligible:
        booking.seating_status = (
            "FINALIZED"
            if booking.id in assigned_booking_ids
            else "UNASSIGNED"
        )
        booking.updated_by = actor_id

    other_plans = db.scalars(
        select(SeatingPlan).where(
            SeatingPlan.event_id == plan.event_id,
            SeatingPlan.id != plan.id,
            SeatingPlan.status != "ARCHIVED",
        )
    ).all()
    for other in other_plans:
        other.status = "ARCHIVED"

    plan.status = "FINALIZED"
    plan.finalized_at = datetime.now(UTC)
    db.flush()

    return plan_detail(db, plan.id)


def delete_plan(
    db: Session,
    plan_id: UUID,
) -> None:
    plan = _load_plan(db, plan_id)
    if plan.status == "FINALIZED":
        raise HTTPException(
            status_code=409,
            detail="Finalized plan cannot be deleted",
        )

    db.delete(plan)
    db.flush()
