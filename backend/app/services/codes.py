from sqlalchemy import text
from sqlalchemy.orm import Session


SEQUENCES = {
    "EVT": "event_code_seq",
    "VND": "vendor_code_seq",
    "TRF": "tariff_code_seq",
    "BKG": "booking_code_seq",
    "PRS": "participant_code_seq",
    "BPR": "booking_participant_code_seq",
    "CHG": "charge_code_seq",
    "PAY": "payment_code_seq",
    "ZON": "zone_code_seq",
    "TBL": "table_layout_code_seq",
    "ASN": "table_assignment_code_seq",
    "CHK": "checkin_log_code_seq",
}


def next_code(db: Session, prefix: str) -> str:
    sequence = SEQUENCES.get(prefix)
    if not sequence:
        raise ValueError(f"Unknown code prefix: {prefix}")

    value = db.scalar(text(f"SELECT nextval('{sequence}')"))
    return f"{prefix}-{int(value):06d}"
