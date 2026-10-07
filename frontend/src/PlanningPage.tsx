import {
  ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "./api";
import type {
  CurrentUser,
  EventRecord,
  PlanningOverview,
  SeatingPlanAssignmentRecord,
  SeatingPlanDetail,
  SeatingPlanSummary,
} from "./types";


type PlanningTab =
  | "preferences"
  | "plans"
  | "manual";


export default function PlanningPage({
  user,
  currentEvent,
  onEventChanged,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
  onEventChanged: () => Promise<void>;
}) {
  const [overview, setOverview] =
    useState<PlanningOverview | null>(null);
  const [selectedPlan, setSelectedPlan] =
    useState<SeatingPlanDetail | null>(null);
  const [tab, setTab] =
    useState<PlanningTab>("preferences");
  const [busy, setBusy] = useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [variants, setVariants] = useState(3);

  const canEdit = [
    "ADMIN",
    "MANAGER",
  ].includes(user.role);

  async function reload() {
    if (!currentEvent) {
      setOverview(null);
      setSelectedPlan(null);
      return;
    }

    try {
      setError(null);
      setOverview(
        await api.planningOverview(
          currentEvent.id,
        ),
      );
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    void reload();
  }, [currentEvent?.id]);

  async function run(
    action: () => Promise<unknown>,
    reloadPlan = false,
  ) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await reload();
      if (
        reloadPlan &&
        selectedPlan
      ) {
        setSelectedPlan(
          await api.seatingPlan(
            selectedPlan.plan.id,
          ),
        );
      }
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function openPlan(
    plan: SeatingPlanSummary,
  ) {
    try {
      setBusy(true);
      setError(null);
      setSelectedPlan(
        await api.seatingPlan(plan.id),
      );
      setTab("manual");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!currentEvent) {
    return (
      <section className="panel">
        <div className="empty-state">
          Сначала выберите текущее
          мероприятие.
        </div>
      </section>
    );
  }

  return (
    <>
      <header className="page-header">
        <div>
          <div className="eyebrow">
            Seating Preferences & Planning · Step 7
          </div>
          <h1>Планирование рассадки</h1>
          <p className="muted header-subtitle">
            {currentEvent.event_name}
          </p>
        </div>

        <div className="planning-header-actions">
          <span
            className={
              currentEvent.seating_preferences_open
                ? "checkin-live open"
                : "checkin-live closed"
            }
          >
            <i />
            {currentEvent.seating_preferences_open
              ? "Пожелания открыты"
              : "Пожелания закрыты"}
          </span>

          {canEdit && (
            <button
              className="button secondary"
              type="button"
              disabled={busy}
              onClick={() =>
                void run(
                  async () => {
                    await api.updateEvent(
                      currentEvent.id,
                      {
                        seating_preferences_open:
                          !currentEvent.seating_preferences_open,
                      },
                    );
                    await onEventChanged();
                  },
                )
              }
            >
              {currentEvent.seating_preferences_open
                ? "Закрыть сбор"
                : "Открыть сбор"}
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="alert error">
          {error}
        </div>
      )}

      <div className="planning-summary">
        <Summary
          label="Одобрено"
          value={
            overview?.summary.eligible || 0
          }
        />
        <Summary
          label="Пожелания получены"
          value={
            overview?.summary.submitted || 0
          }
          accent
        />
        <Summary
          label="Ожидаются"
          value={
            overview?.summary.pending || 0
          }
        />
        <Summary
          label="Версий планов"
          value={
            overview?.summary.plans || 0
          }
        />
      </div>

      <section className="panel planning-shell">
        <div className="planning-toolbar">
          <div className="management-tabs">
            <TabButton
              active={
                tab === "preferences"
              }
              onClick={() =>
                setTab("preferences")
              }
            >
              Пожелания
            </TabButton>
            <TabButton
              active={tab === "plans"}
              onClick={() =>
                setTab("plans")
              }
            >
              Автоварианты
            </TabButton>
            <TabButton
              active={tab === "manual"}
              onClick={() =>
                setTab("manual")
              }
            >
              Ручная корректировка
            </TabButton>
          </div>
        </div>

        {tab === "preferences" && (
          <PreferencesTab
            overview={overview}
            canEdit={canEdit}
            busy={busy}
            onPrepare={() =>
              void run(() =>
                api.preparePlanningPreferences(
                  currentEvent.id,
                ),
              )
            }
          />
        )}

        {tab === "plans" && (
          <PlansTab
            overview={overview}
            canEdit={canEdit}
            busy={busy}
            variants={variants}
            setVariants={setVariants}
            onGenerate={() =>
              void run(() =>
                api.generateSeatingPlans(
                  {
                    variants,
                    attempts_per_variant: 12,
                    near_distance: 220,
                  },
                  currentEvent.id,
                ),
              )
            }
            onOpen={openPlan}
            onDelete={(plan) =>
              void run(async () => {
                if (
                  !window.confirm(
                    "Удалить вариант " +
                      plan.code +
                      "?",
                  )
                ) {
                  return;
                }
                await api.deleteSeatingPlan(
                  plan.id,
                );
                if (
                  selectedPlan?.plan.id ===
                  plan.id
                ) {
                  setSelectedPlan(null);
                }
              })
            }
          />
        )}

        {tab === "manual" && (
          <ManualPlanTab
            detail={selectedPlan}
            plans={overview?.plans || []}
            canEdit={canEdit}
            busy={busy}
            onOpen={openPlan}
            onAssign={async (
              bookingId,
              tableId,
              slot,
              occupiedBookingId,
            ) => {
              if (!selectedPlan) return;

              await run(async () => {
                if (
                  occupiedBookingId &&
                  occupiedBookingId !==
                    bookingId
                ) {
                  const ok =
                    window.confirm(
                      "Ячейка занята. Снять текущего вендора и разместить выбранного?",
                    );
                  if (!ok) return;

                  await api.unassignSeatingPlan(
                    selectedPlan.plan.id,
                    occupiedBookingId,
                  );
                }

                setSelectedPlan(
                  await api.assignSeatingPlan(
                    selectedPlan.plan.id,
                    {
                      booking_id:
                        bookingId,
                      table_id: tableId,
                      start_slot: slot,
                    },
                  ),
                );
              });
            }}
            onUnassign={async (
              bookingId,
            ) => {
              if (!selectedPlan) return;
              await run(async () => {
                setSelectedPlan(
                  await api.unassignSeatingPlan(
                    selectedPlan.plan.id,
                    bookingId,
                  ),
                );
              });
            }}
            onFinalize={() => {
              if (!selectedPlan) return;

              const incomplete =
                selectedPlan.plan
                  .conflicts_count > 0 ||
                selectedPlan.plan
                  .unassigned_count > 0;

              if (incomplete) {
                setError(
                  "Перед утверждением устраните конфликты и разместите всех вендоров.",
                );
                return;
              }

              if (
                !window.confirm(
                  "Утвердить этот вариант? Он заменит текущую финальную рассадку мероприятия.",
                )
              ) {
                return;
              }

              void run(async () => {
                setSelectedPlan(
                  await api.finalizeSeatingPlan(
                    selectedPlan.plan.id,
                    false,
                  ),
                );
              });
            }}
          />
        )}
      </section>
    </>
  );
}


function PreferencesTab({
  overview,
  canEdit,
  busy,
  onPrepare,
}: {
  overview: PlanningOverview | null;
  canEdit: boolean;
  busy: boolean;
  onPrepare: () => void;
}) {
  return (
    <div className="management-section">
      <div className="management-section-head">
        <div>
          <h2>Пожелания вендоров</h2>
          <p>
            После APPROVED для вендора создаётся
            персональная ссылка. Для заявок,
            одобренных до Step 7, используйте
            «Подготовить ссылки».
          </p>
        </div>

        {canEdit && (
          <button
            className="button secondary"
            type="button"
            onClick={onPrepare}
            disabled={busy}
          >
            Подготовить ссылки
          </button>
        )}
      </div>

      <div className="data-table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Вендор</th>
              <th>Booking</th>
              <th>Тип</th>
              <th>Пожелания</th>
              <th>Столы</th>
              <th>Зоны</th>
              <th>Соседи</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(overview?.bookings || []).map(
              (row) => (
                <tr key={row.booking_id}>
                  <td>
                    <strong>
                      {row.vendor_name}
                    </strong>
                    <span className="row-subtitle">
                      {row.vendor_email}
                    </span>
                  </td>
                  <td>{row.booking_code}</td>
                  <td>{row.booking_type}</td>
                  <td>
                    <span
                      className={
                        row.preference
                          ?.status ===
                        "SUBMITTED"
                          ? "badge green"
                          : "badge amber"
                      }
                    >
                      {row.preference
                        ?.status ||
                        "NOT CREATED"}
                    </span>
                  </td>
                  <td>
                    {row.preference
                      ?.table_preferences
                      .length || 0}
                  </td>
                  <td>
                    {row.preference
                      ?.zone_preferences
                      .length || 0}
                  </td>
                  <td>
                    {row.preference
                      ?.adjacency_preferences
                      .length || 0}
                  </td>
                  <td>
                    {row.preference_token && (
                      <button
                        className="button secondary small"
                        type="button"
                        onClick={() =>
                          void copyPreferenceLink(
                            row.preference_token!,
                          )
                        }
                      >
                        Скопировать ссылку
                      </button>
                    )}
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function PlansTab({
  overview,
  canEdit,
  busy,
  variants,
  setVariants,
  onGenerate,
  onOpen,
  onDelete,
}: {
  overview: PlanningOverview | null;
  canEdit: boolean;
  busy: boolean;
  variants: number;
  setVariants: (value: number) => void;
  onGenerate: () => void;
  onOpen: (
    plan: SeatingPlanSummary,
  ) => Promise<void>;
  onDelete: (
    plan: SeatingPlanSummary,
  ) => void;
}) {
  return (
    <div className="management-section">
      <div className="management-section-head">
        <div>
          <h2>Автоматические варианты</h2>
          <p>
            Solver генерирует несколько независимых
            вариантов и ранжирует их по покрытию
            пожеланий, конфликтам и числу
            неразмещённых вендоров.
          </p>
        </div>

        {canEdit && (
          <div className="planning-generate">
            <label>
              <span>Вариантов</span>
              <select
                value={variants}
                onChange={(event) =>
                  setVariants(
                    Number(
                      event.target.value,
                    ),
                  )
                }
              >
                {[1, 2, 3, 4, 5].map(
                  (value) => (
                    <option
                      value={value}
                      key={value}
                    >
                      {value}
                    </option>
                  ),
                )}
              </select>
            </label>
            <button
              className="button primary"
              type="button"
              disabled={busy}
              onClick={onGenerate}
            >
              Сгенерировать варианты
            </button>
          </div>
        )}
      </div>

      <div className="planning-plan-grid">
        {(overview?.plans || []).map(
          (plan) => (
            <article
              className={
                plan.status === "FINALIZED"
                  ? "planning-plan-card finalized"
                  : "planning-plan-card"
              }
              key={plan.id}
            >
              <div className="planning-plan-head">
                <div>
                  <strong>
                    {plan.plan_name}
                  </strong>
                  <span>
                    {plan.code} ·{" "}
                    {plan.status}
                  </span>
                </div>
                <div className="planning-score">
                  {Math.round(
                    plan.score,
                  )}
                  %
                </div>
              </div>

              <div className="planning-plan-metrics">
                <Metric
                  label="Конфликты"
                  value={
                    plan.conflicts_count
                  }
                  bad={
                    plan.conflicts_count >
                    0
                  }
                />
                <Metric
                  label="Не размещено"
                  value={
                    plan.unassigned_count
                  }
                  bad={
                    plan.unassigned_count >
                    0
                  }
                />
              </div>

              <div className="row-actions">
                <button
                  className="button secondary small"
                  type="button"
                  onClick={() =>
                    void onOpen(plan)
                  }
                >
                  Открыть
                </button>
                {canEdit &&
                  plan.status !==
                    "FINALIZED" && (
                    <button
                      className="button danger small"
                      type="button"
                      onClick={() =>
                        onDelete(plan)
                      }
                    >
                      Удалить
                    </button>
                  )}
              </div>
            </article>
          ),
        )}

        {(overview?.plans || []).length ===
          0 && (
          <div className="empty-state">
            Вариантов пока нет. Соберите пожелания
            и запустите solver.
          </div>
        )}
      </div>
    </div>
  );
}


function ManualPlanTab({
  detail,
  plans,
  canEdit,
  busy,
  onOpen,
  onAssign,
  onUnassign,
  onFinalize,
}: {
  detail: SeatingPlanDetail | null;
  plans: SeatingPlanSummary[];
  canEdit: boolean;
  busy: boolean;
  onOpen: (
    plan: SeatingPlanSummary,
  ) => Promise<void>;
  onAssign: (
    bookingId: string,
    tableId: string,
    slot: number,
    occupiedBookingId?: string,
  ) => Promise<void>;
  onUnassign: (
    bookingId: string,
  ) => Promise<void>;
  onFinalize: () => void;
}) {
  if (!detail) {
    return (
      <div className="management-section">
        <h2>Ручная корректировка</h2>
        <p className="muted">
          Выберите один из вариантов:
        </p>
        <div className="planning-plan-picker">
          {plans.map((plan) => (
            <button
              type="button"
              className="button secondary"
              key={plan.id}
              onClick={() =>
                void onOpen(plan)
              }
            >
              {plan.code} ·{" "}
              {Math.round(plan.score)}%
            </button>
          ))}
        </div>
      </div>
    );
  }

  const byTable = new Map<
    string,
    SeatingPlanAssignmentRecord[]
  >();
  for (const assignment of detail.assignments) {
    const list =
      byTable.get(
        assignment.table_id,
      ) || [];
    list.push(assignment);
    byTable.set(
      assignment.table_id,
      list,
    );
  }

  const assignedIds = new Set(
    detail.assignments.map(
      (item) => item.booking_id,
    ),
  );

  return (
    <div className="management-section">
      <div className="management-section-head">
        <div>
          <h2>
            {detail.plan.plan_name} ·{" "}
            {detail.plan.code}
          </h2>
          <p>
            Score {Math.round(
              detail.plan.score,
            )}% · конфликтов{" "}
            {detail.plan.conflicts_count} ·
            не размещено{" "}
            {detail.plan.unassigned_count}
          </p>
        </div>

        {canEdit &&
          detail.plan.status ===
            "DRAFT" && (
            <button
              className="button primary"
              type="button"
              disabled={busy}
              onClick={onFinalize}
            >
              Утвердить рассадку
            </button>
          )}
      </div>

      {detail.plan.status ===
        "FINALIZED" && (
        <div className="alert success">
          Этот план утверждён и перенесён в
          финальную рассадку. Дальнейшие точечные
          правки можно делать в разделе
          «Рассадка».
        </div>
      )}

      {detail.plan.conflicts_count >
        0 && (
        <div className="alert error">
          В плане есть жёсткие конфликты пожеланий.
          Перед утверждением их необходимо
          устранить.
        </div>
      )}

      <div className="planning-unassigned">
        <strong>
          Не размещены:
        </strong>{" "}
        {detail.bookings
          .filter(
            (booking) =>
              !assignedIds.has(
                booking.id,
              ),
          )
          .map(
            (booking) =>
              booking.vendor_name,
          )
          .join(", ") || "нет"}
      </div>

      <div className="data-table-wrap">
        <table className="data-table planning-seat-table">
          <thead>
            <tr>
              <th>Стол</th>
              <th>Зона</th>
              <th>A</th>
              <th>B</th>
            </tr>
          </thead>
          <tbody>
            {detail.tables.map(
              (table) => {
                const assignments =
                  byTable.get(
                    table.id,
                  ) || [];
                const first =
                  assignments.find(
                    (item) =>
                      item.start_slot ===
                      1,
                  ) || null;
                const full =
                  first?.slot_count ===
                  2;
                const second = full
                  ? first
                  : assignments.find(
                      (item) =>
                        item.start_slot ===
                        2,
                    ) || null;
                const zone =
                  detail.zones.find(
                    (item) =>
                      item.id ===
                      table.zone_id,
                  );

                return (
                  <tr key={table.id}>
                    <td>
                      <strong>
                        {table.table_label}
                      </strong>
                    </td>
                    <td>
                      {zone?.zone_name ||
                        "Без зоны"}
                    </td>
                    <td>
                      <PlanSeat
                        tableId={
                          table.id
                        }
                        slot={1}
                        current={first}
                        bookings={
                          detail.bookings
                        }
                        disabled={
                          !canEdit ||
                          detail.plan
                            .status !==
                            "DRAFT"
                        }
                        onAssign={
                          onAssign
                        }
                        onUnassign={
                          onUnassign
                        }
                      />
                    </td>
                    <td>
                      <PlanSeat
                        tableId={
                          table.id
                        }
                        slot={2}
                        current={second}
                        bookings={
                          detail.bookings
                        }
                        disabled={
                          full ||
                          !canEdit ||
                          detail.plan
                            .status !==
                            "DRAFT"
                        }
                        onAssign={
                          onAssign
                        }
                        onUnassign={
                          onUnassign
                        }
                      />
                    </td>
                  </tr>
                );
              },
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}


function PlanSeat({
  tableId,
  slot,
  current,
  bookings,
  disabled,
  onAssign,
  onUnassign,
}: {
  tableId: string;
  slot: number;
  current: SeatingPlanAssignmentRecord | null;
  bookings: SeatingPlanDetail["bookings"];
  disabled: boolean;
  onAssign: (
    bookingId: string,
    tableId: string,
    slot: number,
    occupiedBookingId?: string,
  ) => Promise<void>;
  onUnassign: (
    bookingId: string,
  ) => Promise<void>;
}) {
  const currentId =
    current?.booking_id || "";

  return (
    <div className="plan-seat-editor">
      <select
        className="seat-select"
        disabled={disabled}
        value={currentId}
        onChange={(event) => {
          const next =
            event.target.value;

          if (!next) {
            if (currentId) {
              void onUnassign(
                currentId,
              );
            }
            return;
          }

          void onAssign(
            next,
            tableId,
            slot,
            currentId || undefined,
          );
        }}
      >
        <option value="">
          — свободно —
        </option>
        {bookings.map((booking) => (
          <option
            value={booking.id}
            key={booking.id}
          >
            {booking.vendor_name} ·{" "}
            {booking.booking_type}
          </option>
        ))}
      </select>

      {current?.explanation?.items &&
        current.explanation.items
          .length > 0 && (
          <details className="plan-explanation">
            <summary>
              Почему здесь
            </summary>
            <ul>
              {current.explanation.items.map(
                (item, index) => (
                  <li
                    key={
                      item +
                      String(index)
                    }
                  >
                    {item}
                  </li>
                ),
              )}
            </ul>
          </details>
        )}
    </div>
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


function Metric({
  label,
  value,
  bad = false,
}: {
  label: string;
  value: number;
  bad?: boolean;
}) {
  return (
    <div
      className={
        bad
          ? "planning-metric bad"
          : "planning-metric"
      }
    >
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={
        active
          ? "management-tab active"
          : "management-tab"
      }
      onClick={onClick}
    >
      {children}
    </button>
  );
}


async function copyPreferenceLink(
  token: string,
) {
  const url =
    window.location.origin +
    "/preferences?token=" +
    encodeURIComponent(token);

  await navigator.clipboard.writeText(
    url,
  );
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
