from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.user import User, UserRole
from app.schemas.step7 import (
    FinalizePlanInput,
    GeneratePlansInput,
    PlanAssignmentInput,
    PlanUnassignInput,
)
from app.services.core import current_event_id
from app.services.planning import (
    delete_plan,
    finalize_plan,
    generate_plans,
    place_booking_in_plan,
    plan_detail,
    planning_overview,
    prepare_preferences_for_event,
    unassign_booking_from_plan,
)


router = APIRouter(
    prefix="/planning",
    tags=["planning"],
)

PLANNING_VIEW_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.VIEWER.value,
]
PLANNING_EDIT_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
]


def view_user():
    return require_roles(*PLANNING_VIEW_ROLES)


def edit_user():
    return require_roles(*PLANNING_EDIT_ROLES)


@router.get("")
def overview(
    event_id: UUID | None = None,
    _: User = Depends(view_user()),
    db: Session = Depends(get_db),
):
    return planning_overview(
        db,
        event_id,
    )


@router.post("/preferences/prepare")
def prepare_preferences(
    _: CsrfDep,
    event_id: UUID | None = None,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    event_id = event_id or current_event_id(db)
    if not event_id:
        raise HTTPException(
            status_code=409,
            detail="Current event is not selected",
        )

    rows = prepare_preferences_for_event(
        db,
        event_id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PREFERENCE",
        entity_id=None,
        action="PREPARE_ALL",
        after={
            "event_id": str(event_id),
            "count": len(rows),
        },
    )
    db.commit()

    return planning_overview(
        db,
        event_id,
    )


@router.post("/generate")
def generate(
    payload: GeneratePlansInput,
    _: CsrfDep,
    event_id: UUID | None = None,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    event_id = event_id or current_event_id(db)
    if not event_id:
        raise HTTPException(
            status_code=409,
            detail="Current event is not selected",
        )

    plans = generate_plans(
        db,
        event_id,
        user.id,
        payload.variants,
        payload.attempts_per_variant,
        payload.near_distance,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PLAN",
        entity_id=None,
        action="GENERATE",
        after={
            "event_id": str(event_id),
            "plans": plans,
        },
    )
    db.commit()

    return {
        "items": plans,
    }


@router.get("/plans/{plan_id}")
def read_plan(
    plan_id: UUID,
    _: User = Depends(view_user()),
    db: Session = Depends(get_db),
):
    return plan_detail(db, plan_id)


@router.post("/plans/{plan_id}/assign")
def assign_in_plan(
    plan_id: UUID,
    payload: PlanAssignmentInput,
    _: CsrfDep,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    result = place_booking_in_plan(
        db,
        plan_id,
        payload.booking_id,
        payload.table_id,
        payload.start_slot,
        user.id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PLAN",
        entity_id=str(plan_id),
        action="MANUAL_ASSIGN",
        after={
            "booking_id": str(payload.booking_id),
            "table_id": str(payload.table_id),
            "start_slot": payload.start_slot,
        },
    )
    db.commit()
    return result


@router.post("/plans/{plan_id}/unassign")
def unassign_in_plan(
    plan_id: UUID,
    payload: PlanUnassignInput,
    _: CsrfDep,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    result = unassign_booking_from_plan(
        db,
        plan_id,
        payload.booking_id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PLAN",
        entity_id=str(plan_id),
        action="MANUAL_UNASSIGN",
        after={
            "booking_id": str(payload.booking_id),
        },
    )
    db.commit()
    return result


@router.post("/plans/{plan_id}/finalize")
def finalize(
    plan_id: UUID,
    payload: FinalizePlanInput,
    _: CsrfDep,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    result = finalize_plan(
        db,
        plan_id,
        user.id,
        payload.allow_incomplete,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PLAN",
        entity_id=str(plan_id),
        action="FINALIZE",
        after={
            "plan": result["plan"],
        },
    )
    db.commit()
    return result


@router.delete("/plans/{plan_id}")
def remove_plan(
    plan_id: UUID,
    _: CsrfDep,
    user: User = Depends(edit_user()),
    db: Session = Depends(get_db),
):
    delete_plan(
        db,
        plan_id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="SEATING_PLAN",
        entity_id=str(plan_id),
        action="DELETE",
    )
    db.commit()
    return {"ok": True}
