import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "./api";
import FinanceModal from "./FinanceModal";
import type {
  BookingRecord,
  CheckInOverview,
  CheckInRow,
  CurrentUser,
  EventRecord,
} from "./types";


type Filter = "EXPECTED" | "ARRIVED" | "ALL";


export default function CheckInPage({
  user,
  currentEvent,
  onEventChanged,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
  onEventChanged: () => Promise<void>;
}) {
  const [data, setData] =
    useState<CheckInOverview | null>(null);
  const [filter, setFilter] =
    useState<Filter>("EXPECTED");
  const [query, setQuery] =
    useState("");
  const [busyId, setBusyId] =
    useState<string | null>(null);
  const [financeBooking, setFinanceBooking] =
    useState<BookingRecord | null>(null);
  const [error, setError] =
    useState<string | null>(null);

  const canOperate = [
    "ADMIN",
    "MANAGER",
    "REGISTRATION",
  ].includes(user.role);
  const canManageEvent = [
    "ADMIN",
    "MANAGER",
  ].includes(user.role);
  const canAdjust = [
    "ADMIN",
    "MANAGER",
  ].includes(user.role);

  const checkInOpen =
    data?.event?.vendor_checkin_open ?? false;
  const actionsAllowed =
    canOperate &&
    (checkInOpen || user.role === "ADMIN");

  async function reload(
    nextFilter = filter,
    nextQuery = query,
  ) {
    if (!currentEvent) {
      setData(null);
      return;
    }

    try {
      setError(null);
      setData(
        await api.checkInOverview(
          nextFilter,
          nextQuery,
          currentEvent.id,
        ),
      );
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    void reload(filter, "");
  }, [currentEvent?.id, filter]);

  async function withBusy(
    id: string,
    action: () => Promise<unknown>,
  ) {
    setBusyId(id);
    setError(null);

    try {
      await action();
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  }

  async function openFinance(
    row: CheckInRow,
  ) {
    try {
      setBusyId(row.booking_participant_id);
      setFinanceBooking(
        await api.getBooking(row.booking_id),
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusyId(null);
    }
  }

  const grouped = useMemo(() => {
    const groups = new Map<
      string,
      CheckInRow[]
    >();

    for (const item of data?.items || []) {
      const list =
        groups.get(item.booking_id) || [];
      list.push(item);
      groups.set(item.booking_id, list);
    }

    return [...groups.values()];
  }, [data]);

  return (
    <>
      <header className="page-header">
        <div>
          <div className="eyebrow">
            On-site operations · Step 5
          </div>
          <h1>Check-in и бейджи</h1>
          <p className="muted header-subtitle">
            {currentEvent?.event_name ||
              "Текущее мероприятие не выбрано"}
          </p>
        </div>

        {currentEvent && data?.event && (
          <div className="checkin-event-control">
            <span
              className={
                checkInOpen
                  ? "checkin-live open"
                  : "checkin-live closed"
              }
            >
              <i />
              {checkInOpen
                ? "Check-in открыт"
                : "Check-in закрыт"}
            </span>

            {canManageEvent && (
              <button
                className="button secondary"
                type="button"
                onClick={async () => {
                  try {
                    setBusyId("event-toggle");
                    await api.updateEvent(
                      currentEvent.id,
                      {
                        vendor_checkin_open:
                          !checkInOpen,
                      },
                    );
                    await onEventChanged();
                    await reload();
                  } catch (err) {
                    setError(
                      errorText(err),
                    );
                  } finally {
                    setBusyId(null);
                  }
                }}
                disabled={
                  busyId === "event-toggle"
                }
              >
                {checkInOpen
                  ? "Закрыть"
                  : "Открыть"}
              </button>
            )}
          </div>
        )}
      </header>

      {error && (
        <div className="alert error">
          {error}
        </div>
      )}

      {!currentEvent ? (
        <section className="panel">
          <div className="empty-state">
            Сначала выберите текущее
            мероприятие.
          </div>
        </section>
      ) : (
        <>
          <div className="checkin-summary">
            <Summary
              label="Ожидается"
              value={
                data?.summary.expected || 0
              }
            />
            <Summary
              label="Прибыло"
              value={
                data?.summary.arrived || 0
              }
              accent
            />
            <Summary
              label="Бейджей выдано"
              value={
                data?.summary.badges || 0
              }
            />
            <Summary
              label="Команд полностью"
              value={
                data?.summary
                  .bookings_complete || 0
              }
            />
          </div>

          {!actionsAllowed &&
            canOperate && (
              <div className="checkin-warning">
                Check-in сейчас закрыт. Оператор
                может искать и просматривать
                участников, но действия
                заблокированы.
                {user.role === "ADMIN" &&
                  " ADMIN может выполнять корректировки даже при закрытом check-in."}
              </div>
            )}

          <section className="panel checkin-workspace">
            <div className="checkin-toolbar">
              <div className="checkin-filters">
                <FilterButton
                  active={
                    filter === "EXPECTED"
                  }
                  onClick={() =>
                    setFilter("EXPECTED")
                  }
                >
                  Ожидаются
                </FilterButton>
                <FilterButton
                  active={
                    filter === "ARRIVED"
                  }
                  onClick={() =>
                    setFilter("ARRIVED")
                  }
                >
                  Прибыли
                </FilterButton>
                <FilterButton
                  active={filter === "ALL"}
                  onClick={() =>
                    setFilter("ALL")
                  }
                >
                  Все
                </FilterButton>
              </div>

              <form
                className="checkin-search"
                onSubmit={(
                  event: FormEvent<HTMLFormElement>,
                ) => {
                  event.preventDefault();
                  void reload(filter, query);
                }}
              >
                <input
                  value={query}
                  onChange={(event) =>
                    setQuery(
                      event.target.value,
                    )
                  }
                  placeholder="Имя, ник, вендор, стол, BKG-, PRS-..."
                />
                <button
                  className="button secondary"
                  type="submit"
                >
                  Найти
                </button>
                {query && (
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => {
                      setQuery("");
                      void reload(
                        filter,
                        "",
                      );
                    }}
                  >
                    Сбросить
                  </button>
                )}
              </form>
            </div>

            <div className="checkin-groups">
              {grouped.map((rows) => (
                <BookingCheckInCard
                  key={rows[0].booking_id}
                  rows={rows}
                  currency={
                    currentEvent.currency
                  }
                  actionsAllowed={
                    actionsAllowed
                  }
                  canOperate={canOperate}
                  busyId={busyId}
                  onCheckIn={(row) =>
                    withBusy(
                      row.booking_participant_id,
                      () =>
                        api.checkInParticipant(
                          row.booking_participant_id,
                        ),
                    )
                  }
                  onCancel={(row) =>
                    withBusy(
                      row.booking_participant_id,
                      () =>
                        api.cancelParticipantCheckIn(
                          row.booking_participant_id,
                        ),
                    )
                  }
                  onBadge={async (row) => {
                    const badgeNumber =
                      window.prompt(
                        row.badge_issued
                          ? "Номер нового / заменённого бейджа (можно оставить пустым):"
                          : "Номер бейджа (можно оставить пустым):",
                        row.badge_number || "",
                      );

                    if (badgeNumber === null) {
                      return;
                    }

                    await withBusy(
                      row.booking_participant_id,
                      () =>
                        api.issueParticipantBadge(
                          row.booking_participant_id,
                          badgeNumber,
                        ),
                    );
                  }}
                  onTeam={(row) =>
                    withBusy(
                      `team-${row.booking_id}`,
                      () =>
                        api.checkInBookingTeam(
                          row.booking_id,
                        ),
                    )
                  }
                  onFinance={openFinance}
                />
              ))}

              {grouped.length === 0 && (
                <div className="empty-state">
                  По текущему фильтру ничего не
                  найдено.
                </div>
              )}
            </div>
          </section>
        </>
      )}

      {financeBooking && currentEvent && (
        <FinanceModal
          booking={financeBooking}
          currency={currentEvent.currency}
          canAdjust={canAdjust}
          onClose={() =>
            setFinanceBooking(null)
          }
          onSaved={async () => {
            setFinanceBooking(null);
            await reload();
          }}
        />
      )}
    </>
  );
}


function BookingCheckInCard({
  rows,
  currency,
  actionsAllowed,
  canOperate,
  busyId,
  onCheckIn,
  onCancel,
  onBadge,
  onTeam,
  onFinance,
}: {
  rows: CheckInRow[];
  currency: string;
  actionsAllowed: boolean;
  canOperate: boolean;
  busyId: string | null;
  onCheckIn: (
    row: CheckInRow,
  ) => Promise<void>;
  onCancel: (
    row: CheckInRow,
  ) => Promise<void>;
  onBadge: (
    row: CheckInRow,
  ) => Promise<void>;
  onTeam: (
    row: CheckInRow,
  ) => Promise<void>;
  onFinance: (
    row: CheckInRow,
  ) => Promise<void>;
}) {
  const first = rows[0];
  const arrived = rows.filter(
    (row) =>
      row.checkin_status === "CHECKED_IN",
  ).length;

  return (
    <article className="checkin-booking-card">
      <div className="checkin-booking-head">
        <div>
          <div className="checkin-vendor-title">
            <strong>
              {first.vendor_name}
            </strong>
            <span>
              {first.booking_code} ·{" "}
              {first.booking_type}
            </span>
          </div>

          <div className="checkin-head-meta">
            <Badge>
              {first.table_label
                ? `Стол ${first.table_label}`
                : "Без стола"}
            </Badge>
            <Badge
              tone={
                first.balance > 0
                  ? "amber"
                  : "green"
              }
            >
              {first.payment_status}
            </Badge>
            <Badge
              tone={
                arrived === rows.length
                  ? "green"
                  : arrived > 0
                    ? "amber"
                    : "gray"
              }
            >
              {arrived}/{rows.length} прибыли
            </Badge>
          </div>
        </div>

        <div className="checkin-booking-actions">
          <div className="checkin-money">
            <span>
              Итого{" "}
              {money(
                first.final_total,
                currency,
              )}
            </span>
            <strong>
              {first.balance > 0
                ? `Осталось ${money(
                    first.balance,
                    currency,
                  )}`
                : "Оплачено"}
            </strong>
          </div>

          {canOperate &&
            first.balance > 0 && (
              <button
                className="button secondary small"
                type="button"
                onClick={() =>
                  void onFinance(first)
                }
              >
                Оплата
              </button>
            )}

          {actionsAllowed &&
            arrived < rows.length && (
              <button
                className="button primary small"
                type="button"
                disabled={
                  busyId ===
                  `team-${first.booking_id}`
                }
                onClick={() =>
                  void onTeam(first)
                }
              >
                Прибыла вся команда
              </button>
            )}
        </div>
      </div>

      <div className="checkin-person-list">
        {rows.map((row) => (
          <div
            className={
              row.checkin_status ===
              "CHECKED_IN"
                ? "checkin-person arrived"
                : "checkin-person"
            }
            key={
              row.booking_participant_id
            }
          >
            <div className="checkin-person-main">
              <div className="checkin-avatar">
                {initials(
                  row.nickname ||
                    `${row.first_name} ${row.last_name}`,
                )}
              </div>
              <div>
                <strong>
                  {row.last_name}{" "}
                  {row.first_name}
                </strong>
                <span>
                  @{row.nickname} · {row.role}
                </span>
              </div>
            </div>

            <div className="checkin-person-status">
              <Badge
                tone={
                  row.checkin_status ===
                  "CHECKED_IN"
                    ? "green"
                    : "gray"
                }
              >
                {row.checkin_status ===
                "CHECKED_IN"
                  ? "CHECKED IN"
                  : "EXPECTED"}
              </Badge>

              {row.badge_required && (
                <Badge
                  tone={
                    row.badge_issued
                      ? "green"
                      : "amber"
                  }
                >
                  {row.badge_issued
                    ? row.badge_number
                      ? `BADGE ${row.badge_number}`
                      : "BADGE ISSUED"
                    : "BADGE"}
                </Badge>
              )}
            </div>

            <div className="checkin-person-actions">
              {actionsAllowed &&
                row.checkin_status !==
                  "CHECKED_IN" && (
                  <button
                    className="button primary small"
                    type="button"
                    disabled={
                      busyId ===
                      row.booking_participant_id
                    }
                    onClick={() =>
                      void onCheckIn(row)
                    }
                  >
                    Check-in
                  </button>
                )}

              {actionsAllowed &&
                row.checkin_status ===
                  "CHECKED_IN" && (
                  <>
                    {row.badge_required && (
                      <button
                        className="button secondary small"
                        type="button"
                        disabled={
                          busyId ===
                          row.booking_participant_id
                        }
                        onClick={() =>
                          void onBadge(row)
                        }
                      >
                        {row.badge_issued
                          ? "Заменить бейдж"
                          : "Выдать бейдж"}
                      </button>
                    )}

                    <button
                      className="button secondary small"
                      type="button"
                      disabled={
                        busyId ===
                        row.booking_participant_id
                      }
                      onClick={() =>
                        void onCancel(row)
                      }
                    >
                      Отменить check-in
                    </button>
                  </>
                )}
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}


function Summary({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={
        accent
          ? "checkin-summary-card accent"
          : "checkin-summary-card"
      }
    >
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      className={
        active
          ? "filter-chip active"
          : "filter-chip"
      }
      onClick={onClick}
    >
      {children}
    </button>
  );
}


function Badge({
  children,
  tone = "blue",
}: {
  children: ReactNode;
  tone?: "blue" | "green" | "amber" | "gray";
}) {
  return (
    <span className={`badge ${tone}`}>
      {children}
    </span>
  );
}


function money(
  value: number,
  currency: string,
) {
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(Number(value || 0));
  } catch {
    return `${value} ${currency}`;
  }
}


function initials(value: string) {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) =>
      part.charAt(0).toUpperCase(),
    )
    .join("");
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
