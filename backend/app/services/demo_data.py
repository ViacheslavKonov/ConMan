"""Load the bundled demo dataset into the caller's transaction."""

import hashlib
import json
from datetime import UTC, datetime, time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.audit import audit
from app.models.core import (
    AppSetting, Booking, BookingParticipant, Event, LayoutTable, LayoutZone,
    Participant, Payment, SeatingAdjacencyPreference, SeatingTablePreference,
    SeatingZonePreference, Tariff, Vendor,
)
from app.schemas.demo_data import DemoDataset, ELIGIBLE
from app.services.checkin import add_checkin_log, refresh_booking_checkin_status
from app.services.core import recalculate_booking, set_current_event
from app.services.planning import ensure_preference
from app.services.seating import place_booking


DATASET_PATH = Path(__file__).resolve().parents[1] / "data" / "demo-v1.json"
MARKER_KEY = "demo_dataset:conman-demo-v1"
NOTE = "Синтетические тестовые данные ConMan. Не являются реальными регистрациями."


class DemoDataConflict(ValueError):
    pass


def read_dataset() -> DemoDataset:
    return DemoDataset.model_validate_json(DATASET_PATH.read_text(encoding="utf-8"))


def record_id(model, code: str):
    return uuid5(NAMESPACE_URL, f"conman/demo-v1/{model.__tablename__}/{code}")


def dataset_records(dataset: DemoDataset) -> dict[str, int]:
    tariffs = {item.code: item for item in dataset.tariffs}
    links = [link for booking in dataset.bookings for link in booking.participants]
    preferences = [booking.preference for booking in dataset.bookings if booking.preference]
    return {
        **{name: len(getattr(dataset, name)) for name in (
            "events", "tariffs", "vendors", "participants", "zones", "tables", "bookings",
        )},
        "booking_participants": len(links),
        "charges": sum(1 + (len(booking.participants) > 1 + tariffs[booking.tariff].included_helpers)
                       for booking in dataset.bookings),
        "payments": sum(len(booking.payments) for booking in dataset.bookings),
        "assignments": sum(booking.assignment is not None for booking in dataset.bookings),
        "preferences": len(preferences),
        "table_preferences": len(preferences),
        "zone_preferences": len(preferences),
        "adjacency_preferences": sum(bool(pref.near) + bool(pref.avoid) for pref in preferences),
        "checkin_logs": sum(link.checked_in + bool(link.badge_number) for link in links),
    }


def _fingerprint(dataset):
    return hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()


def _result(dataset, status, marker=None, current_event_changed=False):
    return {
        "status": status,
        "dataset_id": dataset.dataset_id,
        "version": dataset.version,
        "description": dataset.description,
        "loaded_at": marker.get("loaded_at") if marker else None,
        "current_event_changed": current_event_changed,
        "records": dataset_records(dataset),
        "events": [{
            "id": str(record_id(Event, event.code)),
            "code": event.code,
            "name": event.event_name,
            "primary": event.code == dataset.primary_event,
        } for event in dataset.events],
    }


def _existing_marker(db, dataset):
    row = db.get(AppSetting, MARKER_KEY)
    if row is None:
        return None
    try:
        marker = json.loads(row.value or "")
        if marker["sha256"] != _fingerprint(dataset):
            raise DemoDataConflict("The bundled dataset changed after import; use a new dataset version.")
        marker["loaded_at"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DemoDataConflict("The demo import marker is invalid; no data was changed.") from exc
    return marker


def _check_collisions(db: Session, dataset: DemoDataset):
    groups = [
        (Event, dataset.events), (Tariff, dataset.tariffs), (Vendor, dataset.vendors),
        (Participant, dataset.participants), (LayoutZone, dataset.zones),
        (LayoutTable, dataset.tables), (Booking, dataset.bookings),
        (BookingParticipant, [link for booking in dataset.bookings for link in booking.participants]),
        (Payment, [payment for booking in dataset.bookings for payment in booking.payments]),
    ]
    for model, records in groups:
        if not records:
            continue
        existing = db.scalar(select(model.code).where(or_(
            model.code.in_([item.code for item in records]),
            model.id.in_([record_id(model, item.code) for item in records]),
        )).limit(1))
        if existing:
            raise DemoDataConflict(
                f"Existing record conflicts with the demo dataset: {existing}. No data was changed."
            )


def preview_demo_dataset(db: Session) -> dict:
    dataset = read_dataset()
    marker = _existing_marker(db, dataset)
    if not marker:
        _check_collisions(db, dataset)
    return _result(dataset, "already_loaded" if marker else "ready", marker)


def load_demo_dataset(db: Session, *, make_current: bool = False) -> dict:
    dataset = read_dataset()
    # The web application and other sessions remain usable; only demo imports serialize.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": MARKER_KEY})
    marker = _existing_marker(db, dataset)
    if marker:
        return _result(dataset, "already_loaded", marker)
    _check_collisions(db, dataset)

    for model, records, excluded in (
        (Event, dataset.events, set()),
        (Vendor, dataset.vendors, set()),
        (Participant, dataset.participants, set()),
        (Tariff, dataset.tariffs, {"event"}),
        (LayoutZone, dataset.zones, {"event"}),
        (LayoutTable, dataset.tables, {"event", "zone"}),
    ):
        for item in records:
            fields = item.model_dump(exclude=excluded)
            if "event" in excluded:
                fields["event_id"] = record_id(Event, item.event)
            if "zone" in excluded:
                fields["zone_id"] = record_id(LayoutZone, item.zone)
            if model is not LayoutTable:
                fields["notes"] = f"{NOTE}\n{fields.get('notes') or ''}".strip()
            db.add(model(id=record_id(model, item.code), **fields))
        db.flush()

    tariffs = {item.code: item for item in dataset.tariffs}
    events = {item.code: item for item in dataset.events}
    for item in dataset.bookings:
        tariff = tariffs[item.tariff]
        booking = Booking(
            id=record_id(Booking, item.code), code=item.code,
            event_id=record_id(Event, item.event), vendor_id=record_id(Vendor, item.vendor),
            tariff_id=record_id(Tariff, item.tariff), booking_type=tariff.booking_type,
            booking_status=item.status, application_date=item.application_date,
            approved_date=item.application_date if item.status in ELIGIBLE else None,
            base_price=tariff.base_price, included_helpers=tariff.included_helpers,
            extra_participant_price=tariff.extra_participant_price,
            notes=f"{NOTE}\n{item.notes}",
        )
        db.add(booking)
        db.flush()
        for index, link in enumerate(item.participants):
            row = BookingParticipant(
                id=record_id(BookingParticipant, link.code), code=link.code,
                booking_id=booking.id, participant_id=record_id(Participant, link.participant),
                role=link.role, sort_order=index,
                checkin_status="CHECKED_IN" if link.checked_in else "NOT_CHECKED_IN",
                checkin_time=datetime.combine(events[item.event].start_date, time(10), UTC) if link.checked_in else None,
                badge_issued=bool(link.badge_number), badge_number=link.badge_number,
                notes=NOTE,
            )
            db.add(row)
            db.flush()
            if link.checked_in:
                add_checkin_log(db, row, "CHECK_IN", None, NOTE)
            if link.badge_number:
                add_checkin_log(db, row, "BADGE_ISSUED", None, NOTE)
        for payment in item.payments:
            db.add(Payment(
                id=record_id(Payment, payment.code), booking_id=booking.id,
                event_id=booking.event_id, **payment.model_dump(),
            ))
        db.flush()
        recalculate_booking(db, booking)
        refresh_booking_checkin_status(db, booking)
        if item.status == "CONFIRMED" and booking.balance > 0:
            raise ValueError(f"Confirmed demo booking has a debt: {item.code}")

    for item in dataset.bookings:
        booking = db.get(Booking, record_id(Booking, item.code))
        if item.preference:
            pref = item.preference
            row = ensure_preference(db, booking)
            row.status = pref.status
            row.submitted_at = item.application_date if pref.status == "SUBMITTED" else None
            row.notes = NOTE
            row.table_preferences.append(SeatingTablePreference(
                table_id=record_id(LayoutTable, pref.table), priority=5,
            ))
            row.zone_preferences.append(SeatingZonePreference(
                zone_id=record_id(LayoutZone, pref.zone), priority=4,
            ))
            for target, kind in ((pref.near, "PREFER_NEAR"), (pref.avoid, "AVOID_NEAR")):
                if target:
                    row.adjacency_preferences.append(SeatingAdjacencyPreference(
                        target_booking_id=record_id(Booking, target), preference_type=kind,
                        weight=5, notes=NOTE,
                    ))
            booking.seating_status = (
                "PREFERENCES_SUBMITTED" if pref.status == "SUBMITTED" else "PREFERENCES_PENDING"
            )
            db.flush()
        if item.assignment:
            place_booking(db, booking.id, record_id(LayoutTable, item.assignment.table),
                          item.assignment.start_slot, None)

    if make_current:
        set_current_event(db, record_id(Event, dataset.primary_event))
    marker = {"sha256": _fingerprint(dataset), "loaded_at": datetime.now(UTC).isoformat()}
    db.add(AppSetting(key=MARKER_KEY, value=json.dumps(marker)))
    audit(db, user_id=None, entity_type="DEMO_DATASET", entity_id=dataset.dataset_id,
          action="IMPORT", after=dataset_records(dataset),
          metadata={"source": "CLI", "version": dataset.version, "make_current": make_current})
    db.flush()
    return _result(dataset, "loaded", marker, make_current)
