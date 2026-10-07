export type UserRole =
  | "ADMIN"
  | "MANAGER"
  | "REGISTRATION"
  | "VIEWER";

export interface CurrentUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

export interface UserRecord extends CurrentUser {
  active: boolean;
}

export interface CreateUserPayload {
  email: string;
  display_name: string;
  password: string;
  role: UserRole;
  active: boolean;
}

export interface UpdateUserPayload {
  display_name?: string;
  password?: string;
  role?: UserRole;
  active?: boolean;
}

export interface EventRecord {
  id: string;
  code: string;
  event_name: string;
  start_date: string;
  end_date: string;
  venue?: string | null;
  city?: string | null;
  currency: string;
  status: string;
  registration_open: boolean;
  vendor_checkin_open: boolean;
  notes?: string | null;
}

export interface TariffRecord {
  id: string;
  code: string;
  event_id: string;
  tariff_name: string;
  booking_type: "FULL" | "HALF";
  base_price: number;
  included_helpers: number;
  included_participants: number;
  extra_participant_price: number;
  valid_from: string;
  valid_to?: string | null;
  active: boolean;
  notes?: string | null;
}

export interface VendorRecord {
  id: string;
  code: string;
  vendor_name: string;
  legal_name?: string | null;
  email: string;
  phone?: string | null;
  telegram?: string | null;
  website?: string | null;
  social_link?: string | null;
  description?: string | null;
  notes?: string | null;
  active: boolean;
}

export interface ParticipantRecord {
  id: string;
  code: string;
  last_name: string;
  first_name: string;
  middle_name?: string | null;
  nickname: string;
  email?: string | null;
  phone?: string | null;
  telegram?: string | null;
  active: boolean;
}

export interface BookingParticipantRecord {
  id: string;
  code: string;
  role: "OWNER" | "HELPER";
  sort_order: number;
  is_included: boolean;
  charge_amount: number;
  registration_status: string;
  participant: ParticipantRecord;
}

export interface ChargeRecord {
  id: string;
  code: string;
  charge_type: string;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  automatic: boolean;
  active: boolean;
}

export interface PaymentRecord {
  id: string;
  code: string;
  booking_id: string;
  event_id: string;
  payment_type: "PAYMENT" | "REFUND";
  payment_date: string;
  amount: number;
  payment_method: "CASH" | "CARD" | "TRANSFER" | "SBP" | "OTHER";
  reference?: string | null;
  client_operation_id?: string | null;
  status: string;
  notes?: string | null;
}

export interface BookingRecord {
  id: string;
  code: string;
  event_id: string;
  vendor_id: string;
  tariff_id: string;
  booking_type: "FULL" | "HALF";
  booking_status: string;
  application_date: string;
  approved_date?: string | null;
  base_price: number;
  included_helpers: number;
  extra_participant_price: number;
  participants_count: number;
  included_participants_count: number;
  extra_participants_count: number;
  extras_amount: number;
  final_total: number;
  paid_amount: number;
  balance: number;
  payment_status: string;
  seating_status: string;
  checkin_status: string;
  notes?: string | null;
  vendor_name?: string;
  vendor?: VendorRecord;
  tariff?: TariffRecord;
  participants?: BookingParticipantRecord[];
  charges?: ChargeRecord[];
  payments?: PaymentRecord[];
}

export interface VendorDetails {
  vendor: VendorRecord;
  bookings: BookingRecord[];
}

export interface CoreDashboard {
  event: EventRecord | null;
  vendors: number;
  bookings: number;
  participants: number;
  submitted: number;
  confirmed: number;
  total: number;
  balance: number;
}


export interface ApplicationInbox {
  summary: {
    pending: number;
    approved: number;
    confirmed: number;
    rejected: number;
  };
  items: BookingRecord[];
}

export interface PublicRegistrationConfig {
  available: boolean;
  reason: string;
  message: string;
  event: EventRecord | null;
  events: EventRecord[];
  tariffs: Partial<Record<"FULL" | "HALF", TariffRecord>>;
}

export interface PublicApplicationResult {
  duplicate: boolean;
  application: {
    booking_id: string;
    booking_code: string;
    booking_status: string;
    booking_type: "FULL" | "HALF";
    vendor_name: string;
    participants_count: number;
    included_participants_count: number;
    extra_participants_count: number;
    extras_amount: number;
    final_total: number;
    payment_status: string;
  };
}


export interface LayoutZoneRecord {
  id: string;
  code: string;
  event_id: string;
  zone_name: string;
  zone_type: string;
  color?: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  sort_order: number;
  active: boolean;
  notes?: string | null;
}

export interface LayoutTableRecord {
  id: string;
  code: string;
  event_id: string;
  zone_id?: string | null;
  table_number: number;
  table_label: string;
  capacity_slots: number;
  x: number;
  y: number;
  width: number;
  height: number;
  sort_order: number;
  active: boolean;
  notes?: string | null;
}

export interface TableAssignmentRecord {
  id: string;
  code: string;
  event_id: string;
  table_id: string;
  booking_id: string;
  start_slot: number;
  slot_count: number;
  active: boolean;
  notes?: string | null;
  booking: BookingRecord;
}

export interface AuthorsGroup {
  title: string;
  items: {
    label: string;
    table_number: number;
    sort_order: number;
    vendor_name: string;
    booking_type: string;
    payment_status: string;
  }[];
}

export interface SeatingOverview {
  event_id: string | null;
  zones: LayoutZoneRecord[];
  tables: LayoutTableRecord[];
  assignments: TableAssignmentRecord[];
  unassigned_bookings: BookingRecord[];
  authors_groups: AuthorsGroup[];
}


export interface CheckInRow {
  booking_participant_id: string;
  booking_id: string;
  booking_code: string;
  booking_type: "FULL" | "HALF";
  booking_status: string;
  booking_checkin_status: string;
  participant_id: string;
  participant_code: string;
  last_name: string;
  first_name: string;
  middle_name?: string | null;
  nickname: string;
  role: "OWNER" | "HELPER";
  vendor_id?: string | null;
  vendor_name: string;
  table_label?: string | null;
  checkin_status: "NOT_CHECKED_IN" | "CHECKED_IN";
  checkin_time?: string | null;
  badge_required: boolean;
  badge_issued: boolean;
  badge_number?: string | null;
  final_total: number;
  paid_amount: number;
  balance: number;
  payment_status: string;
}

export interface CheckInOverview {
  event: {
    id: string;
    event_name: string;
    vendor_checkin_open: boolean;
  } | null;
  summary: {
    expected: number;
    arrived: number;
    badges: number;
    bookings_complete: number;
  };
  items: CheckInRow[];
}


export interface AdminParticipantRow {
  link_id: string;
  booking_id: string;
  booking_code: string;
  vendor_name: string;
  role: "OWNER" | "HELPER";
  registration_status: string;
  checkin_status: string;
  participant: ParticipantRecord;
}

export interface AdminManagementState {
  current_event_id: string | null;
  event?: EventRecord | null;
  events: EventRecord[];
  tariffs: TariffRecord[];
  vendors: VendorRecord[];
  bookings: BookingRecord[];
  participants: AdminParticipantRow[];
  zones: LayoutZoneRecord[];
  tables: LayoutTableRecord[];
  assignments: TableAssignmentRecord[];
}

export interface ReportColumn {
  key: string;
  label: string;
}

export interface ReportData {
  report: string;
  title: string;
  event: {
    id: string;
    code: string;
    event_name: string;
    currency: string;
  };
  columns: ReportColumn[];
  rows: Record<string, string | number | boolean | null>[];
}
