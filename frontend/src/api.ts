import type {
  AdminManagementState,
  ApplicationInbox,
  BookingRecord,
  CheckInOverview,
  CoreDashboard,
  SeatingOverview,
  CreateUserPayload,
  CurrentUser,
  EventRecord,
  PlanningOverview,
  PreferenceAccessResult,
  PublicApplicationResult,
  PublicRegistrationConfig,
  PublicPreferenceData,
  ReportData,
  SeatingPlanDetail,
  TariffRecord,
  UpdateUserPayload,
  UserRecord,
  VendorDetails,
  VendorRecord,
} from "./types";

function readCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;

  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }

  return null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers || {});

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (
    ["POST", "PUT", "PATCH", "DELETE"].includes(method) &&
    path !== "/api/auth/login"
  ) {
    const csrf = readCookie("conman_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg?: string }) => item.msg || "Validation error").join("; ")
          : detail && typeof detail === "object" && "message" in detail
            ? String(detail.message)
            : `HTTP ${response.status}`;

    throw new Error(message);
  }

  return body as T;
}

export const api = {
  login(email: string, password: string): Promise<CurrentUser> {
    return request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  logout(): Promise<void> {
    return request("/api/auth/logout", { method: "POST" });
  },

  me(): Promise<CurrentUser> {
    return request("/api/auth/me");
  },

  listUsers(): Promise<UserRecord[]> {
    return request("/api/users");
  },

  createUser(payload: CreateUserPayload): Promise<UserRecord> {
    return request("/api/users", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateUser(id: string, payload: UpdateUserPayload): Promise<UserRecord> {
    return request(`/api/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listEvents(): Promise<{
    current_event_id: string | null;
    items: EventRecord[];
  }> {
    return request("/api/events");
  },

  currentEvent(): Promise<{ event: EventRecord | null }> {
    return request("/api/events/current");
  },

  createEvent(payload: object): Promise<EventRecord> {
    return request("/api/events", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  setCurrentEvent(eventId: string): Promise<{ event: EventRecord }> {
    return request(`/api/events/current/${eventId}`, {
      method: "PUT",
    });
  },

  updateEvent(eventId: string, payload: object): Promise<EventRecord> {
    return request(`/api/events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listTariffs(eventId: string): Promise<{ items: TariffRecord[] }> {
    return request(`/api/events/${eventId}/tariffs`);
  },

  createTariff(eventId: string, payload: object): Promise<TariffRecord> {
    return request(`/api/events/${eventId}/tariffs`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateTariff(tariffId: string, payload: object): Promise<TariffRecord> {
    return request(`/api/tariffs/${tariffId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  listVendors(query = ""): Promise<{ items: VendorRecord[] }> {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    params.set("active", "true");

    return request(`/api/vendors?${params.toString()}`);
  },

  createVendor(payload: object): Promise<VendorRecord> {
    return request("/api/vendors", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateVendor(vendorId: string, payload: object): Promise<VendorRecord> {
    return request(`/api/vendors/${vendorId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  updateParticipant(participantId: string, payload: object): Promise<object> {
    return request(`/api/participants/${participantId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  vendorDetails(vendorId: string, eventId?: string): Promise<VendorDetails> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";

    return request(`/api/vendors/${vendorId}${suffix}`);
  },

  createBooking(payload: object): Promise<BookingRecord> {
    return request("/api/bookings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getBooking(bookingId: string): Promise<BookingRecord> {
    return request(`/api/bookings/${bookingId}`);
  },

  addParticipant(
    bookingId: string,
    payload: object,
  ): Promise<BookingRecord> {
    return request(`/api/bookings/${bookingId}/participants`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  cancelBookingParticipant(linkId: string): Promise<BookingRecord> {
    return request(`/api/booking-participants/${linkId}`, {
      method: "DELETE",
    });
  },

  transitionBooking(
    bookingId: string,
    status: string,
    comment = "",
  ): Promise<BookingRecord> {
    return request(`/api/bookings/${bookingId}/transition`, {
      method: "POST",
      body: JSON.stringify({ status, comment }),
    });
  },

  dashboard(eventId?: string): Promise<CoreDashboard> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/core/dashboard${suffix}`);
  },

  publicRegistration(eventId?: string): Promise<PublicRegistrationConfig> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/public/registration${suffix}`);
  },

  submitPublicApplication(payload: object): Promise<PublicApplicationResult> {
    return request("/api/public/applications", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  applications(
    filter = "PENDING",
    query = "",
    eventId?: string,
  ): Promise<ApplicationInbox> {
    const params = new URLSearchParams();
    params.set("filter", filter);
    if (query.trim()) params.set("q", query.trim());
    if (eventId) params.set("event_id", eventId);

    return request(`/api/applications?${params.toString()}`);
  },

  approveApplication(
    bookingId: string,
    comment = "",
  ): Promise<BookingRecord> {
    return request(`/api/applications/${bookingId}/approve`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    });
  },

  rejectApplication(
    bookingId: string,
    reason: string,
  ): Promise<BookingRecord> {
    return request(`/api/applications/${bookingId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  markAwaitingPayment(
    bookingId: string,
    comment = "",
  ): Promise<BookingRecord> {
    return request(`/api/applications/${bookingId}/awaiting-payment`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    });
  },

  confirmApplication(
    bookingId: string,
    comment = "",
  ): Promise<BookingRecord> {
    return request(`/api/applications/${bookingId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ comment }),
    });
  },

  recordPayment(
    bookingId: string,
    payload: object,
  ): Promise<{ duplicate: boolean; booking: BookingRecord }> {
    return request(`/api/bookings/${bookingId}/payments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createAdjustment(
    bookingId: string,
    payload: object,
  ): Promise<BookingRecord> {
    return request(`/api/bookings/${bookingId}/adjustments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },


  seatingLayout(eventId?: string): Promise<SeatingOverview> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/seating/layout${suffix}`);
  },

  createSeatingZone(payload: object): Promise<object> {
    return request("/api/seating/zones", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateSeatingZone(zoneId: string, payload: object): Promise<object> {
    return request(`/api/seating/zones/${zoneId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  createSeatingTables(payload: object): Promise<{ items: object[] }> {
    return request("/api/seating/tables/bulk", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateSeatingTable(tableId: string, payload: object): Promise<object> {
    return request(`/api/seating/tables/${tableId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  assignBookingToTable(payload: object): Promise<object> {
    return request("/api/seating/assignments/assign", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  unassignBookingFromTable(payload: object): Promise<{ ok: boolean }> {
    return request("/api/seating/assignments/unassign", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },


  checkInOverview(
    filter = "EXPECTED",
    query = "",
    eventId?: string,
  ): Promise<CheckInOverview> {
    const params = new URLSearchParams();
    params.set("filter", filter);
    if (query.trim()) params.set("q", query.trim());
    if (eventId) params.set("event_id", eventId);

    return request(`/api/checkin?${params.toString()}`);
  },

  checkInParticipant(
    linkId: string,
    notes = "",
  ): Promise<object> {
    return request(`/api/checkin/${linkId}/check-in`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  },

  cancelParticipantCheckIn(
    linkId: string,
    notes = "",
  ): Promise<{ changed: boolean }> {
    return request(`/api/checkin/${linkId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  },

  issueParticipantBadge(
    linkId: string,
    badgeNumber?: string,
    notes = "",
  ): Promise<object> {
    return request(`/api/checkin/${linkId}/badge`, {
      method: "POST",
      body: JSON.stringify({
        badge_number: badgeNumber || null,
        notes,
      }),
    });
  },

  checkInBookingTeam(
    bookingId: string,
    notes = "",
  ): Promise<object> {
    return request(`/api/checkin/bookings/${bookingId}/team`, {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  },


  adminState(eventId?: string): Promise<AdminManagementState> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/admin/data${suffix}`);
  },

  adminUpdateBooking(
    bookingId: string,
    payload: object,
  ): Promise<BookingRecord> {
    return request(`/api/admin/data/bookings/${bookingId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  adminDeleteEvent(
    eventId: string,
    cascade = false,
  ): Promise<object> {
    return request(
      `/api/admin/data/events/${eventId}?cascade=${cascade ? "true" : "false"}`,
      { method: "DELETE" },
    );
  },

  adminDeleteTariff(
    tariffId: string,
    cascade = false,
  ): Promise<object> {
    return request(
      `/api/admin/data/tariffs/${tariffId}?cascade=${cascade ? "true" : "false"}`,
      { method: "DELETE" },
    );
  },

  adminDeleteVendor(
    vendorId: string,
    cascade = false,
  ): Promise<object> {
    return request(
      `/api/admin/data/vendors/${vendorId}?cascade=${cascade ? "true" : "false"}`,
      { method: "DELETE" },
    );
  },

  adminDeleteBooking(
    bookingId: string,
  ): Promise<object> {
    return request(`/api/admin/data/bookings/${bookingId}`, {
      method: "DELETE",
    });
  },

  adminDeleteParticipant(
    participantId: string,
    cascade = false,
  ): Promise<object> {
    return request(
      `/api/admin/data/participants/${participantId}?cascade=${cascade ? "true" : "false"}`,
      { method: "DELETE" },
    );
  },

  adminDeleteZone(zoneId: string): Promise<object> {
    return request(`/api/admin/data/zones/${zoneId}`, {
      method: "DELETE",
    });
  },

  adminDeleteTable(tableId: string): Promise<object> {
    return request(`/api/admin/data/tables/${tableId}`, {
      method: "DELETE",
    });
  },

  adminCancelPayment(
    paymentId: string,
    reason = "",
  ): Promise<object> {
    return request(`/api/admin/data/payments/${paymentId}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    });
  },

  adminDeactivateCharge(
    chargeId: string,
    reason = "",
  ): Promise<object> {
    return request(`/api/admin/data/charges/${chargeId}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    });
  },

  report(
    reportName: string,
    eventId?: string,
  ): Promise<ReportData> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/reports/${reportName}${suffix}`);
  },


  accessSeatingPreferences(payload: {
    booking_code: string;
    email: string;
  }): Promise<PreferenceAccessResult> {
    return request("/api/public/preferences/access", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  publicSeatingPreferences(
    token: string,
  ): Promise<PublicPreferenceData> {
    return request(
      `/api/public/preferences/${encodeURIComponent(token)}`,
    );
  },

  saveSeatingPreferences(
    token: string,
    payload: object,
  ): Promise<PublicPreferenceData> {
    return request(
      `/api/public/preferences/${encodeURIComponent(token)}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  },

  planningOverview(
    eventId?: string,
  ): Promise<PlanningOverview> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/planning${suffix}`);
  },

  preparePlanningPreferences(
    eventId?: string,
  ): Promise<PlanningOverview> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(
      `/api/planning/preferences/prepare${suffix}`,
      { method: "POST" },
    );
  },

  generateSeatingPlans(
    payload: object,
    eventId?: string,
  ): Promise<{ items: object[] }> {
    const suffix = eventId
      ? `?event_id=${encodeURIComponent(eventId)}`
      : "";
    return request(`/api/planning/generate${suffix}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  seatingPlan(
    planId: string,
  ): Promise<SeatingPlanDetail> {
    return request(`/api/planning/plans/${planId}`);
  },

  assignSeatingPlan(
    planId: string,
    payload: object,
  ): Promise<SeatingPlanDetail> {
    return request(
      `/api/planning/plans/${planId}/assign`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  unassignSeatingPlan(
    planId: string,
    bookingId: string,
  ): Promise<SeatingPlanDetail> {
    return request(
      `/api/planning/plans/${planId}/unassign`,
      {
        method: "POST",
        body: JSON.stringify({
          booking_id: bookingId,
        }),
      },
    );
  },

  finalizeSeatingPlan(
    planId: string,
    allowIncomplete = false,
  ): Promise<SeatingPlanDetail> {
    return request(
      `/api/planning/plans/${planId}/finalize`,
      {
        method: "POST",
        body: JSON.stringify({
          allow_incomplete: allowIncomplete,
        }),
      },
    );
  },

  deleteSeatingPlan(
    planId: string,
  ): Promise<{ ok: boolean }> {
    return request(
      `/api/planning/plans/${planId}`,
      {
        method: "DELETE",
      },
    );
  },

};
