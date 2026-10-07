import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  useEffect,
  useState,
} from "react";

import { api } from "./api";
import ApplicationsPage from "./ApplicationsPage";
import CheckInPage from "./CheckInPage";
import ManagementPage from "./ManagementPage";
import ReportsPage from "./ReportsPage";
import FinanceModal from "./FinanceModal";
import PublicRegistrationPage from "./PublicRegistrationPage";
import SeatingPage from "./SeatingPage";
import type {
  BookingRecord,
  CoreDashboard,
  CreateUserPayload,
  CurrentUser,
  EventRecord,
  TariffRecord,
  UserRecord,
  UserRole,
  VendorDetails,
  VendorRecord,
} from "./types";

type View = "dashboard" | "applications" | "events" | "vendors" | "seating" | "checkin" | "reports" | "management" | "users";

const roles: UserRole[] = [
  "ADMIN",
  "MANAGER",
  "REGISTRATION",
  "VIEWER",
];

export default function App() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";

  if (path === "/register") {
    return <PublicRegistrationPage />;
  }

  return <AuthenticatedApp />;
}

function AuthenticatedApp() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <LoadingScreen text="Загрузка ConMan…" />;
  }

  if (!user) {
    return (
      <LoginPage
        error={error}
        onLogin={async (email, password) => {
          setError(null);
          try {
            setUser(await api.login(email, password));
          } catch (err) {
            setError(errorText(err));
          }
        }}
      />
    );
  }

  return (
    <Shell
      user={user}
      onLogout={async () => {
        try {
          await api.logout();
        } finally {
          setUser(null);
        }
      }}
    />
  );
}

function Shell({
  user,
  onLogout,
}: {
  user: CurrentUser;
  onLogout: () => Promise<void>;
}) {
  const [view, setView] = useState<View>("dashboard");
  const [currentEvent, setCurrentEvent] =
    useState<EventRecord | null>(null);
  const [contextVersion, setContextVersion] = useState(0);

  async function refreshContext() {
    const response = await api.currentEvent();
    setCurrentEvent(response.event);
    setContextVersion((value) => value + 1);
  }

  useEffect(() => {
    refreshContext().catch(console.error);
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark small">C</div>
          <div>
            <strong>ConMan</strong>
            <span>v2 · Admin & Reports</span>
          </div>
        </div>

        <div className="current-event-mini">
          <span>Текущее мероприятие</span>
          <strong>
            {currentEvent?.event_name || "не выбрано"}
          </strong>
        </div>

        <nav>
          <NavButton
            active={view === "dashboard"}
            onClick={() => setView("dashboard")}
          >
            Dashboard
          </NavButton>

          <NavButton
            active={view === "events"}
            onClick={() => setView("events")}
          >
            Мероприятия
          </NavButton>

          <NavButton
            active={view === "vendors"}
            onClick={() => setView("vendors")}
          >
            Вендоры
          </NavButton>

          {user.role !== "REGISTRATION" && (
            <NavButton
              active={view === "applications"}
              onClick={() => setView("applications")}
            >
              Заявки
            </NavButton>
          )}

          <NavButton
            active={view === "seating"}
            onClick={() => setView("seating")}
          >
            Рассадка
          </NavButton>

          <NavButton
            active={view === "checkin"}
            onClick={() => setView("checkin")}
          >
            Check-in
          </NavButton>

          <NavButton
            active={view === "reports"}
            onClick={() => setView("reports")}
          >
            Отчёты
          </NavButton>

          {["ADMIN", "MANAGER"].includes(user.role) && (
            <NavButton
              active={view === "management"}
              onClick={() => setView("management")}
            >
              Управление
            </NavButton>
          )}

          {user.role === "ADMIN" && (
            <NavButton
              active={view === "users"}
              onClick={() => setView("users")}
            >
              Пользователи
            </NavButton>
          )}
        </nav>

        <div className="sidebar-user">
          <div>
            <strong>{user.display_name}</strong>
            <span>{user.role}</span>
          </div>
          <button className="link-button" onClick={onLogout}>
            Выйти
          </button>
        </div>
      </aside>

      <main className="main">
        {view === "dashboard" && (
          <Dashboard
            currentEvent={currentEvent}
            contextVersion={contextVersion}
          />
        )}

        {view === "events" && (
          <EventsPage
            user={user}
            currentEvent={currentEvent}
            onContextChanged={refreshContext}
          />
        )}

        {view === "vendors" && (
          <VendorsPage
            user={user}
            currentEvent={currentEvent}
            contextVersion={contextVersion}
          />
        )}

        {view === "applications" && user.role !== "REGISTRATION" && (
          <ApplicationsPage
            user={user}
            currentEvent={currentEvent}
          />
        )}

        {view === "seating" && (
          <SeatingPage
            user={user}
            currentEvent={currentEvent}
          />
        )}

        {view === "checkin" && (
          <CheckInPage
            user={user}
            currentEvent={currentEvent}
            onEventChanged={refreshContext}
          />
        )}

        {view === "reports" && (
          <ReportsPage
            currentEvent={currentEvent}
          />
        )}

        {view === "management" && ["ADMIN", "MANAGER"].includes(user.role) && (
          <ManagementPage
            user={user}
            currentEvent={currentEvent}
            onCurrentEventChanged={refreshContext}
          />
        )}

        {view === "users" && user.role === "ADMIN" && (
          <UsersPage currentUser={user} />
        )}
      </main>
    </div>
  );
}

function LoginPage({
  onLogin,
  error,
}: {
  onLogin: (email: string, password: string) => Promise<void>;
  error: string | null;
}) {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    try {
      await onLogin(
        String(data.get("email") || ""),
        String(data.get("password") || ""),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand-mark">C</div>
        <div className="eyebrow">ConMan v2</div>
        <h1>Вход</h1>
        <p className="muted">
          Система управления вендорами, заявками и рассадкой.
        </p>

        {error && <div className="alert error">{error}</div>}

        <form onSubmit={submit}>
          <Field label="E-mail">
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
            />
          </Field>

          <Field label="Пароль">
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </Field>

          <button
            className="button primary full"
            type="submit"
            disabled={busy}
          >
            {busy ? "Входим…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Dashboard({
  currentEvent,
  contextVersion,
}: {
  currentEvent: EventRecord | null;
  contextVersion: number;
}) {
  const [data, setData] = useState<CoreDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.dashboard(currentEvent?.id)
      .then(setData)
      .catch((err) => setError(errorText(err)));
  }, [currentEvent?.id, contextVersion]);

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title={currentEvent?.event_name || "Dashboard"}
        subtitle={
          currentEvent
            ? `${formatDate(currentEvent.start_date)} · ${currentEvent.code}`
            : "Создайте первое мероприятие"
        }
      />

      {error && <div className="alert error">{error}</div>}

      {!data ? (
        <Panel><p className="muted">Загрузка…</p></Panel>
      ) : (
        <>
          <section className="grid cards">
            <Metric title="Вендоры" value={data.vendors} />
            <Metric title="Бронирования" value={data.bookings} />
            <Metric title="Участники" value={data.participants} />
            <Metric title="SUBMITTED" value={data.submitted} />
            <Metric title="CONFIRMED" value={data.confirmed} />
            <Metric
              title="Начислено"
              value={money(data.total, currentEvent?.currency)}
            />
            <Metric
              title="Остаток"
              value={money(data.balance, currentEvent?.currency)}
            />
          </section>

          <Panel>
            <h2>Core-модель активна</h2>
            <p className="muted">
              Теперь расчёт стоимости, заявки, платежи и рассадка выполняются на backend и сохраняются транзакционно в PostgreSQL.
            </p>
          </Panel>
        </>
      )}
    </>
  );
}

function EventsPage({
  user,
  currentEvent,
  onContextChanged,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
  onContextChanged: () => Promise<void>;
}) {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [tariffs, setTariffs] = useState<TariffRecord[]>([]);
  const [showEvent, setShowEvent] = useState(false);
  const [showTariff, setShowTariff] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canWrite = ["ADMIN", "MANAGER"].includes(user.role);

  async function reload() {
    try {
      setError(null);
      const eventResponse = await api.listEvents();
      setEvents(eventResponse.items);

      if (currentEvent) {
        const tariffResponse = await api.listTariffs(currentEvent.id);
        setTariffs(tariffResponse.items);
      } else {
        setTariffs([]);
      }
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    reload();
  }, [currentEvent?.id]);

  return (
    <>
      <PageHeader
        eyebrow="Core"
        title="Мероприятия"
        subtitle="События и тарифы участия"
        actions={
          canWrite ? (
            <button
              className="button primary"
              onClick={() => setShowEvent(true)}
            >
              + Мероприятие
            </button>
          ) : null
        }
      />

      {error && <div className="alert error">{error}</div>}

      <div className="two-column">
        <Panel>
          <div className="panel-heading">
            <h2>Мероприятия</h2>
            <span className="count-pill">{events.length}</span>
          </div>

          <div className="stack">
            {events.length === 0 && (
              <Empty text="Мероприятий пока нет." />
            )}

            {events.map((event) => (
              <div
                key={event.id}
                className={
                  currentEvent?.id === event.id
                    ? "record-card selected"
                    : "record-card"
                }
              >
                <div className="record-main">
                  <strong>{event.event_name}</strong>
                  <span>
                    {event.code} · {formatDate(event.start_date)}
                  </span>
                </div>

                <div className="inline-badges">
                  <Badge>{event.status}</Badge>
                  {currentEvent?.id === event.id && (
                    <Badge tone="green">CURRENT</Badge>
                  )}
                </div>

                {canWrite && currentEvent?.id !== event.id && (
                  <button
                    className="button secondary small"
                    onClick={async () => {
                      try {
                        await api.setCurrentEvent(event.id);
                        await onContextChanged();
                      } catch (err) {
                        setError(errorText(err));
                      }
                    }}
                  >
                    Сделать текущим
                  </button>
                )}
              </div>
            ))}
          </div>
        </Panel>

        <Panel>
          <div className="panel-heading">
            <div>
              <h2>Тарифы</h2>
              <p className="muted compact">
                {currentEvent?.event_name || "Нет текущего мероприятия"}
              </p>
            </div>

            {canWrite && currentEvent && (
              <button
                className="button secondary small"
                onClick={() => setShowTariff(true)}
              >
                + Тариф
              </button>
            )}
          </div>

          <div className="stack">
            {tariffs.length === 0 && (
              <Empty text="Тарифов пока нет." />
            )}

            {tariffs.map((tariff) => (
              <div key={tariff.id} className="record-card">
                <div className="record-main">
                  <strong>{tariff.tariff_name}</strong>
                  <span>
                    {tariff.booking_type} · включено{" "}
                    {tariff.included_participants} чел.
                  </span>
                </div>

                <div className="tariff-price">
                  {money(tariff.base_price, currentEvent?.currency)}
                  <small>
                    + {money(
                      tariff.extra_participant_price,
                      currentEvent?.currency,
                    )} / доп.
                  </small>
                </div>

                <Badge tone={tariff.active ? "green" : "gray"}>
                  {tariff.active ? "ACTIVE" : "OFF"}
                </Badge>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {showEvent && (
        <EventModal
          onClose={() => setShowEvent(false)}
          onSaved={async () => {
            setShowEvent(false);
            await onContextChanged();
            await reload();
          }}
        />
      )}

      {showTariff && currentEvent && (
        <TariffModal
          event={currentEvent}
          onClose={() => setShowTariff(false)}
          onSaved={async () => {
            setShowTariff(false);
            await reload();
          }}
        />
      )}
    </>
  );
}

function VendorsPage({
  user,
  currentEvent,
  contextVersion,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
  contextVersion: number;
}) {
  const [vendors, setVendors] = useState<VendorRecord[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<VendorDetails | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [tariffs, setTariffs] = useState<TariffRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const canWrite = ["ADMIN", "MANAGER"].includes(user.role);
  const canPay = ["ADMIN", "MANAGER", "REGISTRATION"].includes(user.role);
  const canAdjust = ["ADMIN", "MANAGER"].includes(user.role);

  async function loadVendors(search = query) {
    try {
      const response = await api.listVendors(search);
      setVendors(response.items);
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function openVendor(vendorId: string) {
    try {
      setError(null);
      const details = await api.vendorDetails(
        vendorId,
        currentEvent?.id,
      );
      setSelected(details);

      if (currentEvent) {
        const tariffResponse = await api.listTariffs(currentEvent.id);
        setTariffs(tariffResponse.items.filter((item) => item.active));
      }
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    loadVendors("");
  }, [contextVersion]);

  return (
    <>
      <PageHeader
        eyebrow="Core"
        title="Вендоры"
        subtitle={
          currentEvent
            ? `Текущее мероприятие: ${currentEvent.event_name}`
            : "Сначала выберите мероприятие"
        }
        actions={
          canWrite ? (
            <button
              className="button primary"
              onClick={() => setShowCreate(true)}
            >
              + Вендор
            </button>
          ) : null
        }
      />

      {error && <div className="alert error">{error}</div>}

      <Panel>
        <form
          className="search-row"
          onSubmit={(event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();
            loadVendors();
          }}
        >
          <input
            value={query}
            onChange={(event: ChangeEvent<HTMLInputElement>) =>
              setQuery(event.target.value)
            }
            placeholder="Название, e-mail, Telegram, VND-..."
          />
          <button className="button secondary" type="submit">
            Найти
          </button>
        </form>

        <div className="vendor-grid">
          {vendors.map((vendor) => (
            <button
              className="vendor-card"
              key={vendor.id}
              onClick={() => openVendor(vendor.id)}
            >
              <div className="avatar">
                {initials(vendor.vendor_name)}
              </div>
              <div>
                <strong>{vendor.vendor_name}</strong>
                <span>{vendor.code}</span>
                <small>
                  {vendor.telegram || vendor.email}
                </small>
              </div>
            </button>
          ))}
        </div>

        {vendors.length === 0 && (
          <Empty text="Вендоры не найдены." />
        )}
      </Panel>

      {showCreate && (
        <VendorModal
          onClose={() => setShowCreate(false)}
          onSaved={async (vendor) => {
            setShowCreate(false);
            await loadVendors("");
            await openVendor(vendor.id);
          }}
        />
      )}

      {selected && (
        <VendorDetailsModal
          details={selected}
          currentEvent={currentEvent}
          tariffs={tariffs}
          canWrite={canWrite}
          canPay={canPay}
          canAdjust={canAdjust}
          onClose={() => setSelected(null)}
          onReload={() => openVendor(selected.vendor.id)}
        />
      )}
    </>
  );
}

function VendorDetailsModal({
  details,
  currentEvent,
  tariffs,
  canWrite,
  canPay,
  canAdjust,
  onClose,
  onReload,
}: {
  details: VendorDetails;
  currentEvent: EventRecord | null;
  tariffs: TariffRecord[];
  canWrite: boolean;
  canPay: boolean;
  canAdjust: boolean;
  onClose: () => void;
  onReload: () => Promise<void>;
}) {
  const [showBooking, setShowBooking] = useState(false);
  const [participantBooking, setParticipantBooking] =
    useState<BookingRecord | null>(null);
  const [financeBooking, setFinanceBooking] =
    useState<BookingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <Modal
      title={details.vendor.vendor_name}
      subtitle={`${details.vendor.code} · ${details.vendor.email}`}
      onClose={onClose}
      wide
    >
      {error && <div className="alert error">{error}</div>}

      <div className="detail-grid">
        <Info label="Telegram" value={details.vendor.telegram || "—"} />
        <Info label="Телефон" value={details.vendor.phone || "—"} />
        <Info
          label="Сайт / соцсеть"
          value={details.vendor.social_link || details.vendor.website || "—"}
        />
        <Info
          label="Статус"
          value={details.vendor.active ? "ACTIVE" : "INACTIVE"}
        />
      </div>

      <div className="panel-heading modal-section-heading">
        <div>
          <h3>Бронирования</h3>
          <p className="muted compact">
            {currentEvent?.event_name || "Текущее мероприятие не выбрано"}
          </p>
        </div>

        {canWrite && currentEvent && details.bookings.length === 0 && (
          <button
            className="button primary small"
            disabled={tariffs.length === 0}
            onClick={() => setShowBooking(true)}
          >
            + Бронирование
          </button>
        )}
      </div>

      <div className="stack">
        {details.bookings.length === 0 && (
          <Empty
            text={
              tariffs.length === 0
                ? "Нет бронирования. Сначала создайте тариф."
                : "На текущее мероприятие бронирования нет."
            }
          />
        )}

        {details.bookings.map((booking) => (
          <div className="booking-card" key={booking.id}>
            <div className="booking-head">
              <div>
                <strong>
                  {booking.code} · {booking.booking_type}
                </strong>
                <span>
                  {booking.booking_status} · {booking.payment_status}
                </span>
              </div>

              <div className="booking-total">
                {money(booking.final_total, currentEvent?.currency)}
                <small>
                  balance {money(booking.balance, currentEvent?.currency)}
                </small>
              </div>
            </div>

            <div className="booking-stats">
              <Info
                label="Участников"
                value={String(booking.participants_count)}
              />
              <Info
                label="Включено"
                value={String(booking.included_participants_count)}
              />
              <Info
                label="Доп."
                value={String(booking.extra_participants_count)}
              />
              <Info
                label="Доплата"
                value={money(
                  booking.extras_amount,
                  currentEvent?.currency,
                )}
              />
            </div>

            <div className="participant-list">
              {(booking.participants || []).map((link) => (
                <div className="participant-row" key={link.id}>
                  <div>
                    <strong>
                      {link.participant.last_name}{" "}
                      {link.participant.first_name}
                    </strong>
                    <span>@{link.participant.nickname}</span>
                  </div>
                  <Badge>{link.role}</Badge>
                  <Badge tone={link.is_included ? "green" : "amber"}>
                    {link.is_included ? "INCLUDED" : "EXTRA"}
                  </Badge>
                </div>
              ))}
            </div>

            {(canPay ||
              (canWrite &&
                ["DRAFT", "SUBMITTED"].includes(booking.booking_status))) && (
                <div className="booking-actions">
                  {canPay && !["CANCELLED", "REJECTED"].includes(booking.booking_status) && (
                    <button
                      className="button secondary small"
                      onClick={() => setFinanceBooking(booking)}
                    >
                      Финансы
                    </button>
                  )}

                  {canWrite &&
                    ["DRAFT", "SUBMITTED"].includes(booking.booking_status) && (
                    <button
                      className="button secondary small"
                      onClick={() => setParticipantBooking(booking)}
                    >
                      + Участник
                    </button>
                  )}

                  {canWrite && booking.booking_status === "DRAFT" && (
                    <button
                      className="button primary small"
                      onClick={async () => {
                        try {
                          await api.transitionBooking(
                            booking.id,
                            "SUBMITTED",
                          );
                          await onReload();
                        } catch (err) {
                          setError(errorText(err));
                        }
                      }}
                    >
                      Отправить заявку
                    </button>
                  )}
                </div>
              )}
          </div>
        ))}
      </div>

      {showBooking && currentEvent && (
        <BookingModal
          vendor={details.vendor}
          event={currentEvent}
          tariffs={tariffs}
          onClose={() => setShowBooking(false)}
          onSaved={async () => {
            setShowBooking(false);
            await onReload();
          }}
        />
      )}

      {participantBooking && (
        <ParticipantModal
          booking={participantBooking}
          onClose={() => setParticipantBooking(null)}
          onSaved={async () => {
            setParticipantBooking(null);
            await onReload();
          }}
        />
      )}

      {financeBooking && (
        <FinanceModal
          booking={financeBooking}
          currency={currentEvent?.currency || "RUB"}
          canAdjust={canAdjust}
          onClose={() => setFinanceBooking(null)}
          onSaved={async () => {
            setFinanceBooking(null);
            await onReload();
          }}
        />
      )}
    </Modal>
  );
}

function EventModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      await api.createEvent({
        event_name: text(data, "event_name"),
        start_date: text(data, "start_date"),
        end_date: text(data, "end_date"),
        city: optional(data, "city"),
        venue: optional(data, "venue"),
        currency: text(data, "currency").toUpperCase(),
        status: text(data, "status"),
        registration_open: data.get("registration_open") === "on",
        vendor_checkin_open: false,
      });
      await onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новое мероприятие" onClose={onClose}>
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        <Field label="Название">
          <input name="event_name" required />
        </Field>

        <div className="form-grid two">
          <Field label="Дата начала">
            <input name="start_date" type="date" required />
          </Field>
          <Field label="Дата окончания">
            <input name="end_date" type="date" required />
          </Field>
          <Field label="Город">
            <input name="city" />
          </Field>
          <Field label="Площадка">
            <input name="venue" />
          </Field>
          <Field label="Валюта">
            <input name="currency" defaultValue="RUB" maxLength={3} required />
          </Field>
          <Field label="Статус">
            <select name="status" defaultValue="DRAFT">
              <option>DRAFT</option>
              <option>REGISTRATION</option>
              <option>ACTIVE</option>
              <option>CLOSED</option>
            </select>
          </Field>
        </div>

        <label className="checkbox">
          <input name="registration_open" type="checkbox" />
          <span>Регистрация открыта</span>
        </label>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

function TariffModal({
  event,
  onClose,
  onSaved,
}: {
  event: EventRecord;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    const data = new FormData(formEvent.currentTarget);

    setBusy(true);
    setError(null);

    try {
      await api.createTariff(event.id, {
        tariff_name: text(data, "tariff_name"),
        booking_type: text(data, "booking_type"),
        base_price: Number(text(data, "base_price")),
        included_helpers: Number(text(data, "included_helpers")),
        extra_participant_price: Number(
          text(data, "extra_participant_price"),
        ),
        valid_from: text(data, "valid_from"),
        valid_to: optional(data, "valid_to"),
        active: true,
      });
      await onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новый тариф" subtitle={event.event_name} onClose={onClose}>
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        <Field label="Название">
          <input name="tariff_name" required />
        </Field>

        <div className="form-grid two">
          <Field label="Тип">
            <select name="booking_type" defaultValue="FULL">
              <option value="FULL">FULL</option>
              <option value="HALF">HALF</option>
            </select>
          </Field>

          <Field label="Базовая цена">
            <input name="base_price" type="number" min="0" step="0.01" required />
          </Field>

          <Field label="Включено помощников">
            <input
              name="included_helpers"
              type="number"
              min="0"
              defaultValue="2"
              required
            />
          </Field>

          <Field label="Цена доп. участника">
            <input
              name="extra_participant_price"
              type="number"
              min="0"
              step="0.01"
              defaultValue="0"
              required
            />
          </Field>

          <Field label="Действует с">
            <input
              name="valid_from"
              type="date"
              defaultValue={today()}
              required
            />
          </Field>

          <Field label="Действует до">
            <input name="valid_to" type="date" />
          </Field>
        </div>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

function VendorModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: (vendor: VendorRecord) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      const vendor = await api.createVendor({
        vendor_name: text(data, "vendor_name"),
        email: text(data, "email"),
        phone: optional(data, "phone"),
        telegram: optional(data, "telegram"),
        website: optional(data, "website"),
        social_link: optional(data, "social_link"),
        description: optional(data, "description"),
        active: true,
      });
      await onSaved(vendor);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Новый вендор" onClose={onClose}>
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        <Field label="Название">
          <input name="vendor_name" required />
        </Field>
        <Field label="E-mail">
          <input name="email" type="email" required />
        </Field>

        <div className="form-grid two">
          <Field label="Телефон">
            <input name="phone" />
          </Field>
          <Field label="Telegram">
            <input name="telegram" />
          </Field>
          <Field label="Сайт">
            <input name="website" />
          </Field>
          <Field label="Соцсеть">
            <input name="social_link" />
          </Field>
        </div>

        <Field label="Описание">
          <textarea name="description" rows={3} />
        </Field>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

function BookingModal({
  vendor,
  event,
  tariffs,
  onClose,
  onSaved,
}: {
  vendor: VendorRecord;
  event: EventRecord;
  tariffs: TariffRecord[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    const data = new FormData(formEvent.currentTarget);

    setBusy(true);
    setError(null);

    try {
      await api.createBooking({
        event_id: event.id,
        vendor_id: vendor.id,
        tariff_id: text(data, "tariff_id"),
        notes: optional(data, "notes"),
      });
      await onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Новое бронирование"
      subtitle={`${vendor.vendor_name} · ${event.event_name}`}
      onClose={onClose}
    >
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        <Field label="Тариф">
          <select name="tariff_id" required>
            {tariffs.map((tariff) => (
              <option key={tariff.id} value={tariff.id}>
                {tariff.booking_type} — {tariff.tariff_name} —{" "}
                {money(tariff.base_price, event.currency)}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Комментарий">
          <textarea name="notes" rows={3} />
        </Field>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

function ParticipantModal({
  booking,
  onClose,
  onSaved,
}: {
  booking: BookingRecord;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasOwner = (booking.participants || []).some(
    (item) => item.role === "OWNER",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      await api.addParticipant(booking.id, {
        role: text(data, "role"),
        participant: {
          last_name: text(data, "last_name"),
          first_name: text(data, "first_name"),
          middle_name: optional(data, "middle_name"),
          nickname: text(data, "nickname"),
          email: optional(data, "email"),
          phone: optional(data, "phone"),
          telegram: optional(data, "telegram"),
        },
      });
      await onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Добавить участника" subtitle={booking.code} onClose={onClose}>
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        <Field label="Роль">
          <select name="role" defaultValue={hasOwner ? "HELPER" : "OWNER"}>
            {!hasOwner && <option value="OWNER">OWNER</option>}
            <option value="HELPER">HELPER</option>
          </select>
        </Field>

        <div className="form-grid two">
          <Field label="Фамилия">
            <input name="last_name" required />
          </Field>
          <Field label="Имя">
            <input name="first_name" required />
          </Field>
          <Field label="Отчество">
            <input name="middle_name" />
          </Field>
          <Field label="Ник">
            <input name="nickname" required />
          </Field>
          <Field label="E-mail">
            <input name="email" type="email" />
          </Field>
          <Field label="Телефон">
            <input name="phone" />
          </Field>
        </div>

        <Field label="Telegram">
          <input name="telegram" />
        </Field>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

function UsersPage({
  currentUser,
}: {
  currentUser: CurrentUser;
}) {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<UserRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      setUsers(await api.listUsers());
      setError(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Пользователи"
        actions={
          <button
            className="button primary"
            onClick={() => setShowCreate(true)}
          >
            + Пользователь
          </button>
        }
      />

      {error && <div className="alert error">{error}</div>}

      <Panel>
        {loading ? (
          <p className="muted">Загрузка…</p>
        ) : (
          <div className="stack">
            {users.map((item) => (
              <div className="record-card" key={item.id}>
                <div className="avatar">
                  {initials(item.display_name || item.email)}
                </div>
                <div className="record-main">
                  <strong>{item.display_name}</strong>
                  <span>{item.email}</span>
                </div>
                <Badge>{item.role}</Badge>
                <Badge tone={item.active ? "green" : "gray"}>
                  {item.active ? "ACTIVE" : "OFF"}
                </Badge>
                <button
                  className="button secondary small"
                  onClick={() => setEditing(item)}
                >
                  Изменить
                </button>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {showCreate && (
        <UserModal
          title="Новый пользователь"
          onClose={() => setShowCreate(false)}
          onSave={async (payload) => {
            await api.createUser(payload as CreateUserPayload);
            setShowCreate(false);
            await reload();
          }}
        />
      )}

      {editing && (
        <UserModal
          title="Изменить пользователя"
          existing={editing}
          currentUser={currentUser}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            await api.updateUser(editing.id, payload);
            setEditing(null);
            await reload();
          }}
        />
      )}
    </>
  );
}

function UserModal({
  title,
  existing,
  currentUser,
  onClose,
  onSave,
}: {
  title: string;
  existing?: UserRecord;
  currentUser?: CurrentUser;
  onClose: () => void;
  onSave: (payload: CreateUserPayload | {
    display_name?: string;
    password?: string;
    role?: UserRole;
    active?: boolean;
  }) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    const isCurrentUser =
      existing !== undefined &&
      currentUser !== undefined &&
      existing.id === currentUser.id;

    const payload = {
      display_name: text(data, "display_name"),
      role: text(data, "role") as UserRole,
      active: isCurrentUser
        ? existing.active
        : data.get("active") === "on",
      ...(optional(data, "password")
        ? { password: text(data, "password") }
        : {}),
    };

    setBusy(true);
    setError(null);

    try {
      if (existing) {
        await onSave(payload);
      } else {
        await onSave({
          ...payload,
          email: text(data, "email"),
          password: text(data, "password"),
        } as CreateUserPayload);
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      {error && <div className="alert error">{error}</div>}

      <form onSubmit={submit}>
        {!existing && (
          <Field label="E-mail">
            <input name="email" type="email" required />
          </Field>
        )}

        <Field label="Имя">
          <input
            name="display_name"
            defaultValue={existing?.display_name || ""}
            required
          />
        </Field>

        <Field
          label={
            existing
              ? "Новый пароль (необязательно)"
              : "Пароль"
          }
        >
          <input
            name="password"
            type="password"
            minLength={10}
            required={!existing}
          />
        </Field>

        <Field label="Роль">
          <select name="role" defaultValue={existing?.role || "VIEWER"}>
            {roles.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </Field>

        <label className="checkbox">
          <input
            name="active"
            type="checkbox"
            defaultChecked={existing?.active ?? true}
            disabled={existing?.id === currentUser?.id}
          />
          <span>Активен</span>
        </label>

        <ModalButtons busy={busy} onClose={onClose} />
      </form>
    </Modal>
  );
}

/* UI primitives */

function NavButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      className={active ? "nav-button active" : "nav-button"}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        {subtitle && <p className="muted header-subtitle">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

function Panel({ children }: { children: ReactNode }) {
  return <section className="panel">{children}</section>;
}

function Metric({
  title,
  value,
}: {
  title: string;
  value: ReactNode;
}) {
  return (
    <article className="card">
      <span>{title}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label>
      <span>{label}</span>
      {children}
    </label>
  );
}

function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className="modal-backdrop">
      <div className={wide ? "modal wide" : "modal"}>
        <div className="modal-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="muted compact">{subtitle}</p>}
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ModalButtons({
  busy,
  onClose,
}: {
  busy: boolean;
  onClose: () => void;
}) {
  return (
    <div className="modal-actions">
      <button
        type="button"
        className="button secondary"
        onClick={onClose}
      >
        Отмена
      </button>
      <button
        type="submit"
        className="button primary"
        disabled={busy}
      >
        {busy ? "Сохраняем…" : "Сохранить"}
      </button>
    </div>
  );
}

function Badge({
  children,
  tone = "blue",
}: {
  children: ReactNode;
  tone?: "blue" | "green" | "amber" | "gray";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function Info({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="info-cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

function LoadingScreen({ text }: { text: string }) {
  return (
    <div className="center-screen">
      <div className="spinner" />
      <p>{text}</p>
    </div>
  );
}

/* helpers */

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Неизвестная ошибка";
}

function text(data: FormData, key: string) {
  return String(data.get(key) || "").trim();
}

function optional(data: FormData, key: string) {
  const value = text(data, key);
  return value || null;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU").format(
    new Date(`${value}T00:00:00`),
  );
}

function money(value: number, currency = "RUB") {
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(Number(value || 0));
  } catch {
    return `${Number(value || 0).toLocaleString("ru-RU")} ${currency}`;
  }
}

function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}
