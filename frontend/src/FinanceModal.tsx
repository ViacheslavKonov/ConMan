import { FormEvent, useState } from "react";

import { api } from "./api";
import type { BookingRecord } from "./types";

export default function FinanceModal({
  booking,
  currency,
  canAdjust,
  onClose,
  onSaved,
}: {
  booking: BookingRecord;
  currency: string;
  canAdjust: boolean;
  onClose: () => void;
  onSaved: (booking: BookingRecord) => Promise<void> | void;
}) {
  const [mode, setMode] = useState<"PAYMENT" | "REFUND">("PAYMENT");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      const response = await api.recordPayment(booking.id, {
        payment_type: mode,
        amount: Number(text(data, "amount")),
        payment_method: text(data, "payment_method"),
        reference: optional(data, "reference"),
        notes: optional(data, "notes"),
        client_operation_id:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `${Date.now()}-${Math.random()}`,
      });

      await onSaved(response.booking);
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitAdjustment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      const updated = await api.createAdjustment(booking.id, {
        charge_type: text(data, "charge_type"),
        description: text(data, "description"),
        amount: Number(text(data, "adjustment_amount")),
        notes: optional(data, "adjustment_notes"),
      });

      await onSaved(updated);
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const paymentMax =
    mode === "PAYMENT"
      ? Math.max(Number(booking.balance), 0)
      : Math.max(Number(booking.paid_amount), 0);

  return (
    <div className="modal-backdrop">
      <div className="modal wide finance-modal">
        <div className="modal-header">
          <div>
            <h2>Финансы</h2>
            <p className="muted compact">
              {booking.code} · {booking.vendor?.vendor_name || booking.vendor_name || ""}
            </p>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>
            ×
          </button>
        </div>

        {error && <div className="alert error">{error}</div>}

        <div className="finance-summary">
          <Summary label="Итого" value={money(booking.final_total, currency)} />
          <Summary label="Оплачено" value={money(booking.paid_amount, currency)} />
          <Summary
            label="Остаток"
            value={money(booking.balance, currency)}
            accent={Number(booking.balance) > 0}
          />
        </div>

        <div className="finance-columns">
          <section className="finance-panel">
            <div className="finance-tabs">
              <button
                type="button"
                className={mode === "PAYMENT" ? "finance-tab active" : "finance-tab"}
                onClick={() => setMode("PAYMENT")}
              >
                Оплата
              </button>
              <button
                type="button"
                className={mode === "REFUND" ? "finance-tab active" : "finance-tab"}
                onClick={() => setMode("REFUND")}
              >
                Возврат
              </button>
            </div>

            <form onSubmit={submitPayment}>
              <label>
                <span>Сумма · макс. {money(paymentMax, currency)}</span>
                <input
                  name="amount"
                  type="number"
                  min="0.01"
                  max={paymentMax}
                  step="0.01"
                  required
                />
              </label>

              <label>
                <span>Способ</span>
                <select name="payment_method" defaultValue="SBP">
                  <option value="CASH">Наличные</option>
                  <option value="CARD">Карта</option>
                  <option value="TRANSFER">Перевод</option>
                  <option value="SBP">СБП</option>
                  <option value="OTHER">Другое</option>
                </select>
              </label>

              <label>
                <span>Референс</span>
                <input name="reference" />
              </label>

              <label>
                <span>Комментарий</span>
                <textarea name="notes" rows={2} />
              </label>

              <button className="button primary full" type="submit" disabled={busy || paymentMax <= 0}>
                {busy
                  ? "Сохраняем…"
                  : mode === "PAYMENT"
                    ? "Внести оплату"
                    : "Оформить возврат"}
              </button>
            </form>
          </section>

          {canAdjust && (
            <section className="finance-panel">
              <h3>Финансовая корректировка</h3>

              <form onSubmit={submitAdjustment}>
                <label>
                  <span>Тип</span>
                  <select name="charge_type" defaultValue="DISCOUNT">
                    <option value="DISCOUNT">Скидка</option>
                    <option value="SURCHARGE">Доплата</option>
                    <option value="MANUAL">Ручная</option>
                  </select>
                </label>

                <label>
                  <span>Описание</span>
                  <input name="description" required />
                </label>

                <label>
                  <span>Сумма</span>
                  <input name="adjustment_amount" type="number" step="0.01" required />
                </label>

                <label>
                  <span>Комментарий</span>
                  <textarea name="adjustment_notes" rows={2} />
                </label>

                <button className="button secondary full" type="submit" disabled={busy}>
                  Добавить корректировку
                </button>
              </form>
            </section>
          )}
        </div>

        <section className="finance-history">
          <h3>История платежей</h3>

          {(booking.payments || []).length === 0 ? (
            <div className="empty-state">Платежей пока нет.</div>
          ) : (
            <div className="stack">
              {(booking.payments || []).map((payment) => (
                <div className="record-card" key={payment.id}>
                  <div className="record-main">
                    <strong>{payment.code} · {payment.payment_type}</strong>
                    <span>
                      {payment.payment_method}
                      {payment.reference ? ` · ${payment.reference}` : ""}
                    </span>
                  </div>

                  <strong
                    className={
                      payment.payment_type === "REFUND"
                        ? "money-negative"
                        : "money-positive"
                    }
                  >
                    {payment.payment_type === "REFUND" ? "−" : "+"}
                    {money(payment.amount, currency)}
                  </strong>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Summary({
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

function text(data: FormData, key: string) {
  return String(data.get(key) || "").trim();
}

function optional(data: FormData, key: string) {
  const value = text(data, key);
  return value || null;
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
