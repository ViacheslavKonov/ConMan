import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import type {
  PublicApplicationResult,
  PublicRegistrationConfig,
} from "./types";


type PersonDraft = {
  last_name: string;
  first_name: string;
  middle_name: string;
  nickname: string;
  email: string;
  phone: string;
  telegram: string;
};

const emptyPerson = (): PersonDraft => ({
  last_name: "",
  first_name: "",
  middle_name: "",
  nickname: "",
  email: "",
  phone: "",
  telegram: "",
});


export default function PublicRegistrationPage() {
  const [config, setConfig] =
    useState<PublicRegistrationConfig | null>(null);
  const [bookingType, setBookingType] =
    useState<"FULL" | "HALF">("FULL");
  const [helpers, setHelpers] =
    useState<PersonDraft[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [result, setResult] =
    useState<PublicApplicationResult | null>(null);

  async function loadRegistration(eventId?: string) {
    setError(null);

    try {
      const value = await api.publicRegistration(eventId);
      setConfig(value);

      if (!value.tariffs[bookingType]) {
        if (value.tariffs.FULL) {
          setBookingType("FULL");
        } else if (value.tariffs.HALF) {
          setBookingType("HALF");
        }
      }
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("event_id") || undefined;
    void loadRegistration(eventId);
  }, []);

  const tariff = config?.tariffs[bookingType];

  const price = useMemo(() => {
    if (!tariff) {
      return {
        participants: 1 + helpers.length,
        extra: 0,
        extrasAmount: 0,
        total: 0,
      };
    }

    const participants = 1 + helpers.length;
    const capacity = tariff.included_helpers + 1;
    const extra = Math.max(participants - capacity, 0);
    const extrasAmount =
      extra * Number(tariff.extra_participant_price);

    return {
      participants,
      extra,
      extrasAmount,
      total: Number(tariff.base_price) + extrasAmount,
    };
  }, [tariff, helpers.length]);

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!config?.available || !tariff) {
      return;
    }

    const data = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);

    try {
      const response = await api.submitPublicApplication({
        event_id: config.event?.id,
        booking_type: bookingType,
        vendor: {
          vendor_name: text(data, "vendor_name"),
          email: text(data, "vendor_email"),
          phone: optional(data, "vendor_phone"),
          telegram: optional(data, "vendor_telegram"),
          website: optional(data, "vendor_website"),
          social_link: optional(data, "vendor_social"),
          description: optional(data, "vendor_description"),
        },
        owner: {
          last_name: text(data, "owner_last_name"),
          first_name: text(data, "owner_first_name"),
          middle_name: optional(data, "owner_middle_name"),
          nickname: text(data, "owner_nickname"),
          email: optional(data, "owner_email"),
          phone: optional(data, "owner_phone"),
          telegram: optional(data, "owner_telegram"),
        },
        helpers: helpers.map((helper) => ({
          last_name: helper.last_name.trim(),
          first_name: helper.first_name.trim(),
          middle_name: helper.middle_name.trim() || null,
          nickname: helper.nickname.trim(),
          email: helper.email.trim() || null,
          phone: helper.phone.trim() || null,
          telegram: helper.telegram.trim() || null,
        })),
        notes: optional(data, "notes"),
        confirmed: data.get("confirmed") === "on",
        company_fax: text(data, "company_fax"),
      });

      setResult(response);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!config && !error) {
    return (
      <PublicShell>
        <div className="public-card public-centered">
          <div className="spinner" />
          <p>Загрузка регистрации…</p>
        </div>
      </PublicShell>
    );
  }

  if (error && !config) {
    return (
      <PublicShell>
        <PublicState
          title="Регистрация недоступна"
          text={error}
        />
      </PublicShell>
    );
  }

  if (result) {
    const app = result.application;

    return (
      <PublicShell>
        <div className="public-card public-centered">
          <div className="public-success-icon">✓</div>
          <div className="eyebrow">
            {result.duplicate
              ? "Заявка уже существует"
              : "Заявка отправлена"}
          </div>
          <h1>
            {result.duplicate
              ? "Повторная заявка не создана"
              : "Спасибо!"}
          </h1>
          <p className="muted">
            {app.vendor_name} · {app.booking_code}
          </p>

          <div className="public-result-grid">
            <PublicMetric
              label="Формат"
              value={app.booking_type}
            />
            <PublicMetric
              label="Участников"
              value={String(app.participants_count)}
            />
            <PublicMetric
              label="Итого"
              value={money(
                app.final_total,
                config?.event?.currency,
              )}
            />
          </div>
        </div>
      </PublicShell>
    );
  }

  if (!config) {
    return null;
  }

  if (!config.available) {
    return (
      <PublicShell>
        <EventSelector
          config={config}
          onSelect={(eventId) => {
            updateEventQuery(eventId);
            void loadRegistration(eventId);
          }}
        />
        <PublicState
          title="Регистрация закрыта"
          text={
            config?.message ||
            `Регистрация недоступна: ${config?.reason || "UNKNOWN"}`
          }
        />
      </PublicShell>
    );
  }

  return (
    <PublicShell>
      <EventSelector
        config={config}
        onSelect={(eventId) => {
          updateEventQuery(eventId);
          void loadRegistration(eventId);
        }}
      />

      <div className="public-card public-event-hero">
        <div>
          <div className="eyebrow">
            Регистрация вендора
          </div>
          <h1>{config.event?.event_name}</h1>
          <p className="muted">
            {[
              config.event?.city,
              config.event?.venue,
            ].filter(Boolean).join(" · ")}
          </p>
        </div>

        <div className="public-date">
          {formatDate(config.event?.start_date || "")}
          {config.event?.end_date !==
            config.event?.start_date &&
            ` — ${formatDate(config.event?.end_date || "")}`}
        </div>
      </div>

      {error && (
        <div className="alert error">{error}</div>
      )}

      <form onSubmit={submit}>
        <section className="public-card">
          <PublicSection
            number="1"
            title="Формат участия"
            subtitle="Выберите полный или половину стола."
          />

          <div className="public-tariffs">
            {(["FULL", "HALF"] as const).map((type) => {
              const item = config.tariffs[type];
              if (!item) return null;

              return (
                <label
                  className={
                    bookingType === type
                      ? "public-tariff selected"
                      : "public-tariff"
                  }
                  key={type}
                >
                  <input
                    type="radio"
                    name="booking_type"
                    value={type}
                    checked={bookingType === type}
                    onChange={() => setBookingType(type)}
                  />
                  <span className="public-tariff-type">
                    {type}
                  </span>
                  <strong>{item.tariff_name}</strong>
                  <b>
                    {money(
                      Number(item.base_price),
                      config.event?.currency,
                    )}
                  </b>
                  <small>
                    включено {item.included_participants} чел. ·
                    доп.{" "}
                    {money(
                      Number(item.extra_participant_price),
                      config.event?.currency,
                    )}
                  </small>
                </label>
              );
            })}
          </div>
        </section>

        <section className="public-card">
          <PublicSection
            number="2"
            title="Вендор"
            subtitle="Название и контакты стенда."
          />

          <div className="form-grid two">
            <Field label="Название *" wide>
              <input
                name="vendor_name"
                required
              />
            </Field>

            <Field label="E-mail *">
              <input
                name="vendor_email"
                type="email"
                required
              />
            </Field>

            <Field label="Телефон">
              <input name="vendor_phone" />
            </Field>

            <Field label="Telegram">
              <input name="vendor_telegram" />
            </Field>

            <Field label="Сайт">
              <input name="vendor_website" />
            </Field>

            <Field label="Соцсеть / портфолио" wide>
              <input name="vendor_social" />
            </Field>

            <Field label="О товарах / стенде" wide>
              <textarea
                name="vendor_description"
                rows={3}
              />
            </Field>
          </div>
        </section>

        <section className="public-card">
          <PublicSection
            number="3"
            title="Основной участник"
            subtitle="OWNER — ответственный за заявку."
          />

          <PersonFields prefix="owner" />
        </section>

        <section className="public-card">
          <div className="public-section-row">
            <PublicSection
              number="4"
              title="Помощники"
              subtitle={
                tariff
                  ? `В тариф включено ${tariff.included_helpers} помощн.`
                  : ""
              }
            />

            <button
              type="button"
              className="button secondary"
              onClick={() =>
                setHelpers((items) => [
                  ...items,
                  emptyPerson(),
                ])
              }
            >
              + Помощник
            </button>
          </div>

          <div className="public-helper-list">
            {helpers.map((helper, index) => (
              <div
                className="public-helper"
                key={index}
              >
                <div className="public-helper-head">
                  <strong>
                    Помощник {index + 1}
                  </strong>
                  <button
                    type="button"
                    className="button danger small"
                    onClick={() =>
                      setHelpers((items) =>
                        items.filter(
                          (_, itemIndex) =>
                            itemIndex !== index,
                        ),
                      )
                    }
                  >
                    Удалить
                  </button>
                </div>

                <PersonDraftFields
                  value={helper}
                  onChange={(next) =>
                    setHelpers((items) =>
                      items.map((item, itemIndex) =>
                        itemIndex === index
                          ? next
                          : item,
                      ),
                    )
                  }
                />
              </div>
            ))}
          </div>
        </section>

        <section className="public-card">
          <PublicSection
            number="5"
            title="Стоимость"
            subtitle="Финальный расчёт повторно выполняется сервером."
          />

          <div className="public-price-grid">
            <PublicMetric
              label="База"
              value={money(
                Number(tariff?.base_price || 0),
                config.event?.currency,
              )}
            />
            <PublicMetric
              label="Участников"
              value={String(price.participants)}
            />
            <PublicMetric
              label="Доп."
              value={`${price.extra} · ${money(
                price.extrasAmount,
                config.event?.currency,
              )}`}
            />
            <PublicMetric
              label="Итого"
              value={money(
                price.total,
                config.event?.currency,
              )}
              accent
            />
          </div>

          <Field label="Комментарий">
            <textarea name="notes" rows={3} />
          </Field>

          <label className="checkbox public-confirm">
            <input
              name="confirmed"
              type="checkbox"
              required
            />
            <span>
              Подтверждаю корректность указанных данных.
            </span>
          </label>

          <input
            className="honeypot"
            name="company_fax"
            tabIndex={-1}
            autoComplete="off"
          />

          <button
            className="button primary full public-submit"
            type="submit"
            disabled={busy}
          >
            {busy
              ? "Отправляем…"
              : "Отправить заявку"}
          </button>
        </section>
      </form>
    </PublicShell>
  );
}


function EventSelector({
  config,
  onSelect,
}: {
  config: PublicRegistrationConfig;
  onSelect: (eventId: string) => void;
}) {
  if (config.events.length <= 1) {
    return null;
  }

  return (
    <div className="public-card public-event-selector">
      <div>
        <div className="eyebrow">Мероприятие</div>
        <strong>Выберите событие для регистрации</strong>
      </div>

      <select
        value={config.event?.id || ""}
        onChange={(event) => onSelect(event.target.value)}
      >
        {config.events.map((item) => (
          <option value={item.id} key={item.id}>
            {item.event_name} · {formatDate(item.start_date)}
          </option>
        ))}
      </select>
    </div>
  );
}


function updateEventQuery(eventId: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("event_id", eventId);
  window.history.replaceState({}, "", url);
}


function PublicShell({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="public-page">
      <header className="public-brand">
        <div className="brand-mark small">C</div>
        <div>
          <strong>ConMan</strong>
          <span>Регистрация вендоров</span>
        </div>
      </header>
      <main className="public-main">
        {children}
      </main>
    </div>
  );
}


function PublicState({
  title,
  text,
}: {
  title: string;
  text: string;
}) {
  return (
    <div className="public-card public-centered">
      <div className="public-state-icon">◇</div>
      <h1>{title}</h1>
      <p className="muted">{text}</p>
    </div>
  );
}


function PublicSection({
  number,
  title,
  subtitle,
}: {
  number: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="public-section">
      <span>{number}</span>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}


function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={wide ? "wide-field" : ""}>
      <span>{label}</span>
      {children}
    </label>
  );
}


function PersonFields({
  prefix,
}: {
  prefix: string;
}) {
  return (
    <div className="form-grid two">
      <Field label="Фамилия *">
        <input
          name={`${prefix}_last_name`}
          required
        />
      </Field>
      <Field label="Имя *">
        <input
          name={`${prefix}_first_name`}
          required
        />
      </Field>
      <Field label="Отчество">
        <input
          name={`${prefix}_middle_name`}
        />
      </Field>
      <Field label="Ник *">
        <input
          name={`${prefix}_nickname`}
          required
        />
      </Field>
      <Field label="E-mail">
        <input
          name={`${prefix}_email`}
          type="email"
        />
      </Field>
      <Field label="Телефон">
        <input
          name={`${prefix}_phone`}
        />
      </Field>
      <Field label="Telegram" wide>
        <input
          name={`${prefix}_telegram`}
        />
      </Field>
    </div>
  );
}


function PersonDraftFields({
  value,
  onChange,
}: {
  value: PersonDraft;
  onChange: (value: PersonDraft) => void;
}) {
  const field = (
    key: keyof PersonDraft,
    next: string,
  ) => {
    onChange({
      ...value,
      [key]: next,
    });
  };

  return (
    <div className="form-grid two">
      <Field label="Фамилия *">
        <input
          value={value.last_name}
          onChange={(event) =>
            field("last_name", event.target.value)
          }
          required
        />
      </Field>
      <Field label="Имя *">
        <input
          value={value.first_name}
          onChange={(event) =>
            field("first_name", event.target.value)
          }
          required
        />
      </Field>
      <Field label="Отчество">
        <input
          value={value.middle_name}
          onChange={(event) =>
            field("middle_name", event.target.value)
          }
        />
      </Field>
      <Field label="Ник *">
        <input
          value={value.nickname}
          onChange={(event) =>
            field("nickname", event.target.value)
          }
          required
        />
      </Field>
      <Field label="E-mail">
        <input
          value={value.email}
          type="email"
          onChange={(event) =>
            field("email", event.target.value)
          }
        />
      </Field>
      <Field label="Телефон">
        <input
          value={value.phone}
          onChange={(event) =>
            field("phone", event.target.value)
          }
        />
      </Field>
      <Field label="Telegram" wide>
        <input
          value={value.telegram}
          onChange={(event) =>
            field("telegram", event.target.value)
          }
        />
      </Field>
    </div>
  );
}


function PublicMetric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div
      className={
        accent
          ? "public-metric accent"
          : "public-metric"
      }
    >
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


function money(
  value: number,
  currency = "RUB",
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


function formatDate(value: string) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("ru-RU").format(
    new Date(`${value}T00:00:00`),
  );
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
