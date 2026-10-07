import { FormEvent, ReactNode, useEffect, useState } from "react";

import { api } from "./api";
import FinanceModal from "./FinanceModal";
import type {
  ApplicationInbox,
  BookingRecord,
  CurrentUser,
  EventRecord,
} from "./types";

export default function ApplicationsPage({
  user,
  currentEvent,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
}) {
  const [data, setData] = useState<ApplicationInbox | null>(null);
  const [filter, setFilter] = useState("PENDING");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<BookingRecord | null>(null);
  const [finance, setFinance] = useState<BookingRecord | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canReview = ["ADMIN", "MANAGER"].includes(user.role);

  async function reload(
    nextFilter = filter,
    nextQuery = query,
  ) {
    if (!currentEvent) {
      setData({
        summary: {
          pending: 0,
          approved: 0,
          confirmed: 0,
          rejected: 0,
        },
        items: [],
      });
      return;
    }

    try {
      setError(null);
      setData(
        await api.applications(
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
    reload();
  }, [currentEvent?.id, filter]);

  async function runAction(
    fn: () => Promise<BookingRecord>,
  ) {
    setBusy(true);
    setError(null);

    try {
      await fn();
      setSelected(null);
      setComment("");
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const currency = currentEvent?.currency || "RUB";

  return (
    <>
      <header className="page-header">
        <div>
          <div className="eyebrow">Applications</div>
          <h1>Заявки</h1>
          <p className="muted header-subtitle">
            {currentEvent?.event_name ||
              "Текущее мероприятие не выбрано"}
          </p>
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}

      <div className="application-summary">
        <SummaryCard label="На рассмотрении" value={data?.summary.pending || 0} />
        <SummaryCard label="Одобрены" value={data?.summary.approved || 0} />
        <SummaryCard label="Подтверждены" value={data?.summary.confirmed || 0} />
        <SummaryCard label="Отклонены" value={data?.summary.rejected || 0} />
      </div>

      <section className="panel">
        <div className="application-toolbar">
          <div className="application-tabs">
            {[
              ["PENDING", "На рассмотрении"],
              ["APPROVED", "Одобрены"],
              ["CONFIRMED", "Подтверждены"],
              ["REJECTED", "Отклонены"],
              ["ALL", "Все"],
            ].map(([value, label]) => (
              <button
                type="button"
                key={value}
                className={
                  filter === value
                    ? "application-tab active"
                    : "application-tab"
                }
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>

          <form
            className="search-row application-search"
            onSubmit={(event: FormEvent<HTMLFormElement>) => {
              event.preventDefault();
              reload(filter, query);
            }}
          >
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Вендор, e-mail, Telegram, BKG-..."
            />
            <button className="button secondary" type="submit">
              Найти
            </button>
          </form>
        </div>

        <div className="stack">
          {(data?.items || []).map((booking) => (
            <article className="application-card" key={booking.id}>
              <div className="application-card-main">
                <div className="application-card-heading">
                  <div>
                    <strong>
                      {booking.vendor?.vendor_name ||
                        booking.vendor_name ||
                        "—"}
                    </strong>
                    <span>
                      {booking.code} · {formatDateTime(booking.application_date)}
                    </span>
                  </div>

                  <div className="inline-badges">
                    <Badge>{booking.booking_type}</Badge>
                    <Badge tone="gray">{booking.booking_status}</Badge>
                    <Badge
                      tone={Number(booking.balance) > 0 ? "amber" : "green"}
                    >
                      {booking.payment_status}
                    </Badge>
                  </div>
                </div>

                <div className="application-card-grid">
                  <Info label="OWNER" value={ownerText(booking)} />
                  <Info label="Участники" value={String(booking.participants_count)} />
                  <Info label="Итого" value={money(booking.final_total, currency)} />
                  <Info label="Остаток" value={money(booking.balance, currency)} />
                </div>
              </div>

              <button
                className="button secondary"
                onClick={() => {
                  setComment("");
                  setSelected(booking);
                }}
              >
                Открыть
              </button>
            </article>
          ))}

          {(data?.items || []).length === 0 && (
            <div className="empty-state">
              Для выбранного фильтра заявок нет.
            </div>
          )}
        </div>
      </section>

      {selected && (
        <div className="modal-backdrop">
          <div className="modal wide">
            <div className="modal-header">
              <div>
                <h2>
                  {selected.vendor?.vendor_name ||
                    selected.vendor_name ||
                    "Заявка"}
                </h2>
                <p className="muted compact">
                  {selected.code} · {selected.booking_status}
                </p>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={() => setSelected(null)}
              >
                ×
              </button>
            </div>

            <div className="detail-grid">
              <Info label="E-mail" value={selected.vendor?.email || "—"} />
              <Info label="Telegram" value={selected.vendor?.telegram || "—"} />
              <Info label="Участников" value={String(selected.participants_count)} />
              <Info label="Доп. участников" value={String(selected.extra_participants_count)} />
            </div>

            <div className="finance-summary application-finance-summary">
              <FinanceValue label="Итого" value={money(selected.final_total, currency)} />
              <FinanceValue label="Оплачено" value={money(selected.paid_amount, currency)} />
              <FinanceValue
                label="Остаток"
                value={money(selected.balance, currency)}
                accent={Number(selected.balance) > 0}
              />
            </div>

            <section className="application-people">
              <h3>Участники</h3>
              <div className="stack">
                {(selected.participants || []).map((link) => (
                  <div className="participant-row" key={link.id}>
                    <div>
                      <strong>
                        {link.participant.last_name} {link.participant.first_name}
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
            </section>

            {canReview &&
              !["CONFIRMED", "REJECTED"].includes(selected.booking_status) && (
                <label className="review-comment">
                  <span>Комментарий сотрудника</span>
                  <textarea
                    value={comment}
                    rows={3}
                    onChange={(event) => setComment(event.target.value)}
                  />
                </label>
              )}

            <div className="modal-actions application-actions">
              {canReview && selected.booking_status === "SUBMITTED" && (
                <>
                  <button
                    className="button danger"
                    disabled={busy}
                    onClick={() => {
                      if (!comment.trim()) {
                        setError("Для отклонения укажите причину.");
                        return;
                      }

                      runAction(() =>
                        api.rejectApplication(
                          selected.id,
                          comment.trim(),
                        ),
                      );
                    }}
                  >
                    Отклонить
                  </button>

                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() =>
                      runAction(() =>
                        api.approveApplication(
                          selected.id,
                          comment,
                        ),
                      )
                    }
                  >
                    Одобрить
                  </button>
                </>
              )}

              {canReview &&
                selected.booking_status === "APPROVED" &&
                Number(selected.balance) > 0 && (
                  <>
                    <button
                      className="button secondary"
                      onClick={() => {
                        setFinance(selected);
                        setSelected(null);
                      }}
                    >
                      Внести оплату
                    </button>

                    <button
                      className="button primary"
                      disabled={busy}
                      onClick={() =>
                        runAction(() =>
                          api.markAwaitingPayment(
                            selected.id,
                            comment,
                          ),
                        )
                      }
                    >
                      Ожидает оплаты
                    </button>
                  </>
                )}

              {canReview &&
                ["APPROVED", "AWAITING_PAYMENT"].includes(
                  selected.booking_status,
                ) &&
                Number(selected.balance) <= 0 && (
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() =>
                      runAction(() =>
                        api.confirmApplication(
                          selected.id,
                          comment,
                        ),
                      )
                    }
                  >
                    Подтвердить
                  </button>
                )}

              {canReview &&
                selected.booking_status === "AWAITING_PAYMENT" &&
                Number(selected.balance) > 0 && (
                  <button
                    className="button primary"
                    onClick={() => {
                      setFinance(selected);
                      setSelected(null);
                    }}
                  >
                    Внести оплату
                  </button>
                )}
            </div>
          </div>
        </div>
      )}

      {finance && (
        <FinanceModal
          booking={finance}
          currency={currency}
          canAdjust={canReview}
          onClose={() => setFinance(null)}
          onSaved={async (updated) => {
            setFinance(null);
            setSelected(updated);
            await reload();
          }}
        />
      )}
    </>
  );
}

function SummaryCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="application-summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
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

function FinanceValue({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className={accent ? "finance-summary-cell accent" : "finance-summary-cell"}>
      <span>{label}</span>
      <strong>{value}</strong>
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

function ownerText(booking: BookingRecord) {
  const owner = (booking.participants || []).find(
    (item) => item.role === "OWNER",
  );

  if (!owner) return "—";

  return `${owner.participant.last_name} ${owner.participant.first_name} · @${owner.participant.nickname}`;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function money(value: number, currency: string) {
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

function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Неизвестная ошибка";
}
