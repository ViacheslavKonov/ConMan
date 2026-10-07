import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "./api";
import type {
  AdjacencyPreferenceType,
  PublicPreferenceData,
} from "./types";


type AdjacencyDraft = {
  preference_type: AdjacencyPreferenceType | "";
  weight: number;
};


export default function PublicPreferencesPage() {
  const initialToken =
    new URLSearchParams(window.location.search).get("token") ||
    window.sessionStorage.getItem("conman:preferences-token") ||
    "";

  const [token, setToken] = useState(initialToken);
  const [data, setData] =
    useState<PublicPreferenceData | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [savedMessage, setSavedMessage] =
    useState<string | null>(null);

  const [allowOtherTables, setAllowOtherTables] =
    useState(true);
  const [allowOtherZones, setAllowOtherZones] =
    useState(true);
  const [tablePreferences, setTablePreferences] =
    useState<Record<string, number>>({});
  const [zonePreferences, setZonePreferences] =
    useState<Record<string, number>>({});
  const [adjacency, setAdjacency] =
    useState<Record<string, AdjacencyDraft>>({});
  const [notes, setNotes] = useState("");
  const [tableQuery, setTableQuery] = useState("");

  async function load(nextToken: string) {
    if (!nextToken) return;

    setBusy(true);
    setError(null);
    try {
      const result =
        await api.publicSeatingPreferences(nextToken);
      setToken(nextToken);
      setData(result);
      window.sessionStorage.setItem(
        "conman:preferences-token",
        nextToken,
      );
      initializeDraft(result);
    } catch (err) {
      setData(null);
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (initialToken) {
      void load(initialToken);
    }
  }, []);

  function initializeDraft(
    value: PublicPreferenceData,
  ) {
    setAllowOtherTables(
      value.preference.allow_other_tables,
    );
    setAllowOtherZones(
      value.preference.allow_other_zones,
    );
    setNotes(value.preference.notes || "");

    setTablePreferences(
      Object.fromEntries(
        value.preference.table_preferences.map(
          (item) => [
            item.table_id,
            item.priority,
          ],
        ),
      ),
    );
    setZonePreferences(
      Object.fromEntries(
        value.preference.zone_preferences.map(
          (item) => [
            item.zone_id,
            item.priority,
          ],
        ),
      ),
    );
    setAdjacency(
      Object.fromEntries(
        value.preference.adjacency_preferences.map(
          (item) => [
            item.target_booking_id,
            {
              preference_type:
                item.preference_type,
              weight: item.weight,
            },
          ],
        ),
      ),
    );
  }

  async function access(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);

    setBusy(true);
    setError(null);
    try {
      const result =
        await api.accessSeatingPreferences({
          booking_code: String(
            form.get("booking_code") || "",
          ).trim(),
          email: String(
            form.get("email") || "",
          ).trim(),
        });

      setToken(result.token);
      setData(result.data);
      initializeDraft(result.data);
      window.sessionStorage.setItem(
        "conman:preferences-token",
        result.token,
      );

      const url = new URL(
        window.location.href,
      );
      url.searchParams.set(
        "token",
        result.token,
      );
      window.history.replaceState(
        {},
        "",
        url,
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function save(submit: boolean) {
    if (!token) return;

    setBusy(true);
    setError(null);
    setSavedMessage(null);

    try {
      const result =
        await api.saveSeatingPreferences(
          token,
          {
            allow_other_tables:
              allowOtherTables,
            allow_other_zones:
              allowOtherZones,
            table_preferences:
              Object.entries(
                tablePreferences,
              ).map(
                ([table_id, priority]) => ({
                  table_id,
                  priority,
                }),
              ),
            zone_preferences:
              Object.entries(
                zonePreferences,
              ).map(
                ([zone_id, priority]) => ({
                  zone_id,
                  priority,
                }),
              ),
            adjacency_preferences:
              Object.entries(adjacency)
                .filter(
                  ([, value]) =>
                    value.preference_type,
                )
                .map(
                  ([
                    target_booking_id,
                    value,
                  ]) => ({
                    target_booking_id,
                    preference_type:
                      value.preference_type,
                    weight: value.weight,
                  }),
                ),
            notes:
              notes.trim() || null,
            submit,
          },
        );

      setData(result);
      initializeDraft(result);
      setSavedMessage(
        submit
          ? "Пожелания отправлены организатору."
          : "Черновик сохранён.",
      );
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const filteredTables = useMemo(() => {
    if (!data) return [];
    const needle =
      tableQuery.trim().toLowerCase();

    if (!needle) return data.tables;

    return data.tables.filter((table) =>
      [
        table.table_label,
        String(table.table_number),
        table.zone_name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [data, tableQuery]);

  if (!data) {
    return (
      <PreferenceShell>
        <div className="public-card public-centered">
          <div className="eyebrow">
            Seating preferences
          </div>
          <h1>Пожелания по рассадке</h1>
          <p className="muted">
            Форма доступна после одобрения заявки
            организатором.
          </p>

          {error && (
            <div className="alert error">
              {error}
            </div>
          )}

          <form
            className="public-access-form"
            onSubmit={access}
          >
            <label>
              <span>Код заявки</span>
              <input
                name="booking_code"
                placeholder="BKG-000001"
                required
              />
            </label>
            <label>
              <span>E-mail вендора</span>
              <input
                name="email"
                type="email"
                required
              />
            </label>
            <button
              className="button primary full"
              type="submit"
              disabled={busy}
            >
              {busy
                ? "Проверяем…"
                : "Открыть пожелания"}
            </button>
          </form>
        </div>
      </PreferenceShell>
    );
  }

  return (
    <PreferenceShell>
      <div className="public-card preference-hero">
        <div>
          <div className="eyebrow">
            Пожелания по рассадке
          </div>
          <h1>
            {data.booking.vendor_name}
          </h1>
          <p className="muted">
            {data.event.event_name} ·{" "}
            {data.booking.code} ·{" "}
            {data.booking.booking_type}
          </p>
        </div>

        <span
          className={
            data.preference.status ===
            "SUBMITTED"
              ? "badge green"
              : "badge amber"
          }
        >
          {data.preference.status ===
          "SUBMITTED"
            ? "Отправлено"
            : "Черновик"}
        </span>
      </div>

      {savedMessage && (
        <div className="alert success">
          {savedMessage}
        </div>
      )}

      {error && (
        <div className="alert error">
          {error}
        </div>
      )}

      <section className="public-card">
        <div className="public-section-row">
          <div>
            <div className="eyebrow">
              1 · Зоны
            </div>
            <h2>Предпочтительные зоны</h2>
            <p className="muted compact">
              Можно выбрать несколько зон и
              задать приоритет от 1 до 5.
            </p>
          </div>
        </div>

        <div className="preference-choice-grid">
          {data.zones.map((zone) => {
            const selected =
              zone.id in zonePreferences;

            return (
              <PreferenceChoice
                key={zone.id}
                title={zone.zone_name}
                subtitle={zone.zone_type}
                selected={selected}
                priority={
                  zonePreferences[
                    zone.id
                  ] || 3
                }
                onSelected={(value) => {
                  setZonePreferences(
                    (current) => {
                      const next = {
                        ...current,
                      };
                      if (value) {
                        next[zone.id] =
                          next[zone.id] || 3;
                      } else {
                        delete next[zone.id];
                      }
                      return next;
                    },
                  );
                }}
                onPriority={(priority) =>
                  setZonePreferences(
                    (current) => ({
                      ...current,
                      [zone.id]:
                        priority,
                    }),
                  )
                }
              />
            );
          })}
        </div>

        <label className="checkbox preference-policy">
          <input
            type="checkbox"
            checked={allowOtherZones}
            onChange={(event) =>
              setAllowOtherZones(
                event.target.checked,
              )
            }
          />
          <span>
            Допускаю размещение в других зонах,
            если выбранные недоступны
          </span>
        </label>
      </section>

      <section className="public-card">
        <div className="public-section-row">
          <div>
            <div className="eyebrow">
              2 · Столы
            </div>
            <h2>Предпочтительные столы</h2>
            <p className="muted compact">
              Выберите любое количество. Чем выше
              приоритет, тем сильнее алгоритм будет
              стремиться использовать этот стол.
            </p>
          </div>

          <input
            className="preference-table-search"
            value={tableQuery}
            onChange={(event) =>
              setTableQuery(
                event.target.value,
              )
            }
            placeholder="Поиск стола или зоны"
          />
        </div>

        <div className="preference-table-grid">
          {filteredTables.map((table) => {
            const selected =
              table.id in tablePreferences;
            return (
              <PreferenceChoice
                key={table.id}
                title={"Стол " + table.table_label}
                subtitle={
                  table.zone_name ||
                  "Без зоны"
                }
                selected={selected}
                priority={
                  tablePreferences[
                    table.id
                  ] || 3
                }
                onSelected={(value) => {
                  setTablePreferences(
                    (current) => {
                      const next = {
                        ...current,
                      };
                      if (value) {
                        next[table.id] =
                          next[table.id] ||
                          3;
                      } else {
                        delete next[
                          table.id
                        ];
                      }
                      return next;
                    },
                  );
                }}
                onPriority={(priority) =>
                  setTablePreferences(
                    (current) => ({
                      ...current,
                      [table.id]:
                        priority,
                    }),
                  )
                }
              />
            );
          })}
        </div>

        <label className="checkbox preference-policy">
          <input
            type="checkbox"
            checked={allowOtherTables}
            onChange={(event) =>
              setAllowOtherTables(
                event.target.checked,
              )
            }
          />
          <span>
            Допускаю другие столы, если выбранные
            недоступны
          </span>
        </label>
      </section>

      <section className="public-card">
        <div className="eyebrow">
          3 · Соседи
        </div>
        <h2>С кем хотелось бы сидеть рядом</h2>
        <p className="muted compact">
          «Обязательно» — жёсткое ограничение.
          Используйте его только когда это
          действительно необходимо.
        </p>

        <div className="preference-neighbor-list">
          {data.vendors.map((vendor) => {
            const current =
              adjacency[
                vendor.booking_id
              ] || {
                preference_type:
                  "",
                weight: 5,
              };

            return (
              <div
                className="preference-neighbor"
                key={vendor.booking_id}
              >
                <div>
                  <strong>
                    {vendor.vendor_name}
                  </strong>
                  <span>
                    {vendor.booking_code}
                  </span>
                </div>

                <select
                  value={
                    current.preference_type
                  }
                  onChange={(event) =>
                    setAdjacency(
                      (values) => ({
                        ...values,
                        [vendor.booking_id]:
                          {
                            ...current,
                            preference_type:
                              event.target
                                .value as AdjacencyPreferenceType | "",
                          },
                      }),
                    )
                  }
                >
                  <option value="">
                    Без пожелания
                  </option>
                  <option value="PREFER_NEAR">
                    Желательно рядом
                  </option>
                  <option value="MUST_NEAR">
                    Обязательно рядом
                  </option>
                  <option value="AVOID_NEAR">
                    Желательно не рядом
                  </option>
                  <option value="MUST_NOT_NEAR">
                    Обязательно не рядом
                  </option>
                </select>

                <select
                  value={current.weight}
                  disabled={
                    !current.preference_type
                  }
                  onChange={(event) =>
                    setAdjacency(
                      (values) => ({
                        ...values,
                        [vendor.booking_id]:
                          {
                            ...current,
                            weight: Number(
                              event.target
                                .value,
                            ),
                          },
                      }),
                    )
                  }
                >
                  {[1, 3, 5, 7, 10].map(
                    (value) => (
                      <option
                        value={value}
                        key={value}
                      >
                        Вес {value}
                      </option>
                    ),
                  )}
                </select>
              </div>
            );
          })}

          {data.vendors.length === 0 && (
            <div className="empty-state">
              Других одобренных вендоров пока
              нет.
            </div>
          )}
        </div>
      </section>

      <section className="public-card">
        <div className="eyebrow">
          4 · Комментарий
        </div>
        <h2>Дополнительные пожелания</h2>
        <textarea
          rows={5}
          value={notes}
          onChange={(event) =>
            setNotes(event.target.value)
          }
          placeholder="Например: нужен доступ к стене, место для стойки, ограничения по мобильности..."
        />
      </section>

      <div className="public-card preference-actions">
        <button
          className="button secondary"
          type="button"
          disabled={busy}
          onClick={() => void save(false)}
        >
          Сохранить черновик
        </button>
        <button
          className="button primary"
          type="button"
          disabled={busy}
          onClick={() => void save(true)}
        >
          {busy
            ? "Сохраняем…"
            : "Отправить организатору"}
        </button>
      </div>
    </PreferenceShell>
  );
}


function PreferenceChoice({
  title,
  subtitle,
  selected,
  priority,
  onSelected,
  onPriority,
}: {
  title: string;
  subtitle: string;
  selected: boolean;
  priority: number;
  onSelected: (value: boolean) => void;
  onPriority: (value: number) => void;
}) {
  return (
    <div
      className={
        selected
          ? "preference-choice selected"
          : "preference-choice"
      }
    >
      <label>
        <input
          type="checkbox"
          checked={selected}
          onChange={(event) =>
            onSelected(
              event.target.checked,
            )
          }
        />
        <span>
          <strong>{title}</strong>
          <small>{subtitle}</small>
        </span>
      </label>

      {selected && (
        <select
          value={priority}
          onChange={(event) =>
            onPriority(
              Number(
                event.target.value,
              ),
            )
          }
        >
          <option value="1">
            1 · низкий
          </option>
          <option value="2">2</option>
          <option value="3">
            3 · обычный
          </option>
          <option value="4">4</option>
          <option value="5">
            5 · высокий
          </option>
        </select>
      )}
    </div>
  );
}


function PreferenceShell({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="public-page">
      <header className="public-header">
        <div className="brand">
          <div className="brand-mark small">
            C
          </div>
          <div>
            <strong>ConMan</strong>
            <span>Seating preferences</span>
          </div>
        </div>
      </header>
      <main className="public-main">
        {children}
      </main>
    </div>
  );
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
