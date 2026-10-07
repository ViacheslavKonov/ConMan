import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "./api";
import type {
  AdminManagementState,
  BookingRecord,
  CurrentUser,
  EventRecord,
  LayoutTableRecord,
  LayoutZoneRecord,
  ParticipantRecord,
  TableAssignmentRecord,
  TariffRecord,
  VendorRecord,
} from "./types";


type Tab =
  | "events"
  | "tariffs"
  | "vendors"
  | "bookings"
  | "participants"
  | "finance"
  | "layout"
  | "seating"
  | "crud";


type Editor =
  | { type: "event"; item?: EventRecord }
  | { type: "tariff"; item?: TariffRecord }
  | { type: "vendor"; item?: VendorRecord }
  | { type: "booking"; item: BookingRecord }
  | {
      type: "participant";
      item: ParticipantRecord;
    }
  | {
      type: "zone";
      item: LayoutZoneRecord;
    }
  | {
      type: "table";
      item: LayoutTableRecord;
    };


export default function ManagementPage({
  user,
  currentEvent,
  onCurrentEventChanged,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
  onCurrentEventChanged: () => Promise<void>;
}) {
  const [tab, setTab] =
    useState<Tab>("events");
  const [data, setData] =
    useState<AdminManagementState | null>(null);
  const [editor, setEditor] =
    useState<Editor | null>(null);
  const [busy, setBusy] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  const canManage = [
    "ADMIN",
    "MANAGER",
  ].includes(user.role);

  async function reload(
    eventId = currentEvent?.id,
  ) {
    try {
      setError(null);
      setData(
        await api.adminState(eventId),
      );
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    void reload();
  }, [currentEvent?.id]);

  const bookingsById = useMemo(
    () =>
      new Map(
        (data?.bookings || []).map(
          (item) => [item.id, item],
        ),
      ),
    [data],
  );

  const assignmentsByTable = useMemo(() => {
    const result = new Map<
      string,
      TableAssignmentRecord[]
    >();
    for (const assignment of
      data?.assignments || []) {
      const list =
        result.get(assignment.table_id) ||
        [];
      list.push(assignment);
      result.set(
        assignment.table_id,
        list,
      );
    }
    return result;
  }, [data]);

  async function run(
    action: () => Promise<unknown>,
    refreshContext = false,
  ) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (refreshContext) {
        await onCurrentEventChanged();
        setData(await api.adminState());
      } else {
        await reload();
      }
      setEditor(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!canManage) {
    return (
      <section className="panel">
        <div className="empty-state">
          Раздел управления доступен ADMIN и
          MANAGER.
        </div>
      </section>
    );
  }

  return (
    <>
      <header className="page-header">
        <div>
          <div className="eyebrow">
            Administration · Step 6
          </div>
          <h1>Управление данными</h1>
          <p className="muted header-subtitle">
            Настройки, CRUD, каскадные операции и
            табличная рассадка.
          </p>
        </div>
      </header>

      {error && (
        <div className="alert error">
          {error}
        </div>
      )}

      <section className="panel management-shell">
        <div className="management-tabs">
          {[
            ["events", "Мероприятия"],
            ["tariffs", "Тарифы"],
            ["vendors", "Вендоры"],
            ["bookings", "Бронирования"],
            ["participants", "Участники"],
            ["finance", "Фин. записи"],
            ["layout", "Зоны и столы"],
            ["seating", "Вендор ↔ стол"],
            ["crud", "CRUD-матрица"],
          ].map(([value, label]) => (
            <button
              type="button"
              key={value}
              className={
                tab === value
                  ? "management-tab active"
                  : "management-tab"
              }
              onClick={() =>
                setTab(value as Tab)
              }
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "events" && (
          <EventsTab
            data={data}
            currentEvent={currentEvent}
            busy={busy}
            onEdit={(item) =>
              setEditor({
                type: "event",
                item,
              })
            }
            onCreate={() =>
              setEditor({
                type: "event",
              })
            }
            onSelect={async (eventId) => {
              await run(
                () =>
                  api.setCurrentEvent(
                    eventId,
                  ),
                true,
              );
            }}
            onDelete={async (item) => {
              if (
                !window.confirm(
                  `Удалить мероприятие «${item.event_name}»?\n\nВсе его бронирования, тарифы, платежи, начисления, рассадка и check-in будут удалены каскадно. Вендоры как мастер-данные останутся.`,
                )
              ) {
                return;
              }

              await run(
                () =>
                  api.adminDeleteEvent(
                    item.id,
                    true,
                  ),
                true,
              );
            }}
          />
        )}

        {tab === "tariffs" && (
          <TariffsTab
            data={data}
            busy={busy}
            onCreate={() =>
              setEditor({
                type: "tariff",
              })
            }
            onEdit={(item) =>
              setEditor({
                type: "tariff",
                item,
              })
            }
            onDelete={async (item) => {
              const used =
                data?.bookings.filter(
                  (booking) =>
                    booking.tariff_id ===
                    item.id,
                ).length || 0;

              const message = used
                ? `Тариф используется в ${used} бронированиях.\n\nOK — удалить тариф И эти бронирования каскадно.\nCancel — отменить.`
                : `Удалить тариф «${item.tariff_name}»?`;

              if (
                !window.confirm(message)
              ) {
                return;
              }

              await run(() =>
                api.adminDeleteTariff(
                  item.id,
                  used > 0,
                ),
              );
            }}
          />
        )}

        {tab === "vendors" && (
          <VendorsTab
            data={data}
            busy={busy}
            onCreate={() =>
              setEditor({
                type: "vendor",
              })
            }
            onEdit={(item) =>
              setEditor({
                type: "vendor",
                item,
              })
            }
            onDelete={async (item) => {
              const bookings =
                data?.bookings.filter(
                  (booking) =>
                    booking.vendor_id ===
                    item.id,
                ).length || 0;

              if (
                !window.confirm(
                  bookings > 0
                    ? `У вендора есть ${bookings} бронирований текущего мероприятия.\n\nУдалить вендора вместе со ВСЕМИ его бронированиями во всех мероприятиях?`
                    : `Удалить вендора «${item.vendor_name}»? Если у него есть бронирования в других мероприятиях, они также будут удалены.`,
                )
              ) {
                return;
              }

              await run(() =>
                api.adminDeleteVendor(
                  item.id,
                  true,
                ),
              );
            }}
          />
        )}

        {tab === "bookings" && (
          <BookingsTab
            data={data}
            busy={busy}
            onEdit={(item) =>
              setEditor({
                type: "booking",
                item,
              })
            }
            onDelete={async (item) => {
              if (
                !window.confirm(
                  `Удалить ${item.code}?\n\nБудут каскадно удалены платежи, начисления, связи участников, check-in и рассадка. Участники, больше нигде не используемые, также будут удалены.`,
                )
              ) {
                return;
              }

              await run(() =>
                api.adminDeleteBooking(
                  item.id,
                ),
              );
            }}
          />
        )}

        {tab === "participants" && (
          <ParticipantsTab
            data={data}
            busy={busy}
            onEdit={(item) =>
              setEditor({
                type: "participant",
                item,
              })
            }
            onDelete={async (item) => {
              if (
                !window.confirm(
                  `Удалить участника ${item.nickname}?\n\nСвязи с бронированиями будут удалены, а стоимость затронутых бронирований будет пересчитана.`,
                )
              ) {
                return;
              }

              await run(() =>
                api.adminDeleteParticipant(
                  item.id,
                  true,
                ),
              );
            }}
          />
        )}

        {tab === "finance" && (
          <FinancialRecordsTab
            data={data}
            busy={busy}
            onCancelPayment={async (
              paymentId,
            ) => {
              const reason =
                window.prompt(
                  "Причина отмены платежа:",
                  "",
                );
              if (reason === null) {
                return;
              }

              await run(() =>
                api.adminCancelPayment(
                  paymentId,
                  reason,
                ),
              );
            }}
            onDeactivateCharge={async (
              chargeId,
            ) => {
              const reason =
                window.prompt(
                  "Причина деактивации начисления:",
                  "",
                );
              if (reason === null) {
                return;
              }

              await run(() =>
                api.adminDeactivateCharge(
                  chargeId,
                  reason,
                ),
              );
            }}
          />
        )}

        {tab === "layout" && (
          <LayoutTab
            data={data}
            busy={busy}
            onEditZone={(item) =>
              setEditor({
                type: "zone",
                item,
              })
            }
            onEditTable={(item) =>
              setEditor({
                type: "table",
                item,
              })
            }
            onDeleteZone={async (item) => {
              if (
                !window.confirm(
                  `Удалить зону «${item.zone_name}»? Столы сохранятся, но станут «Без зоны».`,
                )
              ) {
                return;
              }
              await run(() =>
                api.adminDeleteZone(
                  item.id,
                ),
              );
            }}
            onDeleteTable={async (item) => {
              if (
                !window.confirm(
                  `Удалить стол ${item.table_label}? Назначенные бронирования будут сняты со стола.`,
                )
              ) {
                return;
              }
              await run(() =>
                api.adminDeleteTable(
                  item.id,
                ),
              );
            }}
          />
        )}

        {tab === "seating" && (
          <SeatingTableTab
            data={data}
            assignmentsByTable={
              assignmentsByTable
            }
            bookingsById={bookingsById}
            onAssign={async (
              bookingId,
              tableId,
              slot,
            ) => {
              await run(() =>
                api.assignBookingToTable({
                  booking_id: bookingId,
                  table_id: tableId,
                  start_slot: slot,
                }),
              );
            }}
            onClear={async (
              bookingId,
            ) => {
              await run(() =>
                api.unassignBookingFromTable(
                  {
                    booking_id:
                      bookingId,
                  },
                ),
              );
            }}
          />
        )}

        {tab === "crud" && (
          <CrudMatrix />
        )}
      </section>

      {editor && (
        <ManagementEditor
          editor={editor}
          data={data}
          busy={busy}
          onClose={() =>
            setEditor(null)
          }
          onSave={async (
            payload,
          ) => {
            if (
              editor.type === "event"
            ) {
              if (editor.item) {
                await run(
                  () =>
                    api.updateEvent(
                      editor.item!.id,
                      payload,
                    ),
                  true,
                );
              } else {
                await run(
                  () =>
                    api.createEvent(
                      payload,
                    ),
                  true,
                );
              }
              return;
            }

            if (
              editor.type === "tariff"
            ) {
              if (!data?.event) {
                throw new Error(
                  "Выберите мероприятие.",
                );
              }

              if (editor.item) {
                await run(() =>
                  api.updateTariff(
                    editor.item!.id,
                    payload,
                  ),
                );
              } else {
                await run(() =>
                  api.createTariff(
                    data.event!.id,
                    payload,
                  ),
                );
              }
              return;
            }

            if (
              editor.type === "vendor"
            ) {
              if (editor.item) {
                await run(() =>
                  api.updateVendor(
                    editor.item!.id,
                    payload,
                  ),
                );
              } else {
                await run(() =>
                  api.createVendor(
                    payload,
                  ),
                );
              }
              return;
            }

            if (
              editor.type === "booking"
            ) {
              await run(() =>
                api.adminUpdateBooking(
                  editor.item.id,
                  payload,
                ),
              );
              return;
            }

            if (
              editor.type ===
              "participant"
            ) {
              await run(() =>
                api.updateParticipant(
                  editor.item.id,
                  payload,
                ),
              );
              return;
            }

            if (
              editor.type === "zone"
            ) {
              await run(() =>
                api.updateSeatingZone(
                  editor.item.id,
                  payload,
                ),
              );
              return;
            }

            if (
              editor.type === "table"
            ) {
              await run(() =>
                api.updateSeatingTable(
                  editor.item.id,
                  payload,
                ),
              );
            }
          }}
        />
      )}
    </>
  );
}


function EventsTab({
  data,
  currentEvent,
  busy,
  onEdit,
  onCreate,
  onSelect,
  onDelete,
}: {
  data: AdminManagementState | null;
  currentEvent: EventRecord | null;
  busy: boolean;
  onEdit: (item: EventRecord) => void;
  onCreate: () => void;
  onSelect: (id: string) => Promise<void>;
  onDelete: (item: EventRecord) => Promise<void>;
}) {
  return (
    <DataSection
      title="Мероприятия"
      action={
        <button
          className="button primary"
          onClick={onCreate}
        >
          + Мероприятие
        </button>
      }
    >
      <DataTable
        headers={[
          "Код",
          "Название",
          "Даты",
          "Статус",
          "Регистрация",
          "Check-in",
          "",
        ]}
      >
        {(data?.events || []).map(
          (item) => (
            <tr key={item.id}>
              <td>{item.code}</td>
              <td>
                <strong>
                  {item.event_name}
                </strong>
                {currentEvent?.id ===
                  item.id && (
                  <span className="row-note">
                    текущее
                  </span>
                )}
              </td>
              <td>
                {item.start_date} —{" "}
                {item.end_date}
              </td>
              <td>{item.status}</td>
              <td>
                {item.registration_open
                  ? "ON"
                  : "OFF"}
              </td>
              <td>
                {item.vendor_checkin_open
                  ? "ON"
                  : "OFF"}
              </td>
              <td>
                <RowActions>
                  {currentEvent?.id !==
                    item.id && (
                    <button
                      className="button secondary small"
                      disabled={busy}
                      onClick={() =>
                        void onSelect(item.id)
                      }
                    >
                      Выбрать
                    </button>
                  )}
                  <button
                    className="button secondary small"
                    onClick={() =>
                      onEdit(item)
                    }
                  >
                    Изменить
                  </button>
                  <button
                    className="button danger small"
                    onClick={() =>
                      void onDelete(item)
                    }
                  >
                    Удалить
                  </button>
                </RowActions>
              </td>
            </tr>
          ),
        )}
      </DataTable>
    </DataSection>
  );
}


function TariffsTab({
  data,
  busy,
  onCreate,
  onEdit,
  onDelete,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onCreate: () => void;
  onEdit: (item: TariffRecord) => void;
  onDelete: (item: TariffRecord) => Promise<void>;
}) {
  return (
    <DataSection
      title={`Тарифы · ${data?.event?.event_name || "мероприятие не выбрано"}`}
      action={
        <button
          className="button primary"
          disabled={!data?.event}
          onClick={onCreate}
        >
          + Тариф
        </button>
      }
    >
      <DataTable
        headers={[
          "Код",
          "Название",
          "Тип",
          "База",
          "Включено",
          "Доп. участник",
          "Активен",
          "",
        ]}
      >
        {(data?.tariffs || []).map(
          (item) => (
            <tr key={item.id}>
              <td>{item.code}</td>
              <td>{item.tariff_name}</td>
              <td>{item.booking_type}</td>
              <td>
                {money(item.base_price)}
              </td>
              <td>
                {item.included_participants}
              </td>
              <td>
                {money(
                  item.extra_participant_price,
                )}
              </td>
              <td>
                {item.active ? "YES" : "NO"}
              </td>
              <td>
                <RowActions>
                  <button
                    className="button secondary small"
                    onClick={() =>
                      onEdit(item)
                    }
                  >
                    Изменить
                  </button>
                  <button
                    className="button danger small"
                    disabled={busy}
                    onClick={() =>
                      void onDelete(item)
                    }
                  >
                    Удалить
                  </button>
                </RowActions>
              </td>
            </tr>
          ),
        )}
      </DataTable>
    </DataSection>
  );
}


function VendorsTab({
  data,
  busy,
  onCreate,
  onEdit,
  onDelete,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onCreate: () => void;
  onEdit: (item: VendorRecord) => void;
  onDelete: (item: VendorRecord) => Promise<void>;
}) {
  return (
    <DataSection
      title="Вендоры текущего мероприятия"
      action={
        <button
          className="button primary"
          onClick={onCreate}
        >
          + Вендор
        </button>
      }
    >
      <DataTable
        headers={[
          "Код",
          "Название",
          "E-mail",
          "Telegram",
          "Активен",
          "",
        ]}
      >
        {(data?.vendors || []).map(
          (item) => (
            <tr key={item.id}>
              <td>{item.code}</td>
              <td>{item.vendor_name}</td>
              <td>{item.email}</td>
              <td>{item.telegram || "—"}</td>
              <td>
                {item.active ? "YES" : "NO"}
              </td>
              <td>
                <RowActions>
                  <button
                    className="button secondary small"
                    onClick={() =>
                      onEdit(item)
                    }
                  >
                    Изменить
                  </button>
                  <button
                    className="button danger small"
                    disabled={busy}
                    onClick={() =>
                      void onDelete(item)
                    }
                  >
                    Удалить
                  </button>
                </RowActions>
              </td>
            </tr>
          ),
        )}
      </DataTable>
    </DataSection>
  );
}


function BookingsTab({
  data,
  busy,
  onEdit,
  onDelete,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onEdit: (item: BookingRecord) => void;
  onDelete: (item: BookingRecord) => Promise<void>;
}) {
  return (
    <DataSection
      title="Бронирования"
      subtitle="Создание бронирования остаётся в карточке вендора; здесь доступны чтение, изменение и каскадное удаление."
    >
      <DataTable
        headers={[
          "Код",
          "Вендор",
          "Тип",
          "Статус",
          "Участники",
          "Итого",
          "Оплачено",
          "Остаток",
          "Рассадка",
          "",
        ]}
      >
        {(data?.bookings || []).map(
          (item) => (
            <tr key={item.id}>
              <td>{item.code}</td>
              <td>
                {item.vendor?.vendor_name ||
                  item.vendor_name ||
                  "—"}
              </td>
              <td>{item.booking_type}</td>
              <td>
                {item.booking_status}
              </td>
              <td>
                {item.participants_count}
              </td>
              <td>
                {money(item.final_total)}
              </td>
              <td>
                {money(item.paid_amount)}
              </td>
              <td>
                {money(item.balance)}
              </td>
              <td>
                {item.seating_status}
              </td>
              <td>
                <RowActions>
                  <button
                    className="button secondary small"
                    onClick={() =>
                      onEdit(item)
                    }
                  >
                    Изменить
                  </button>
                  <button
                    className="button danger small"
                    disabled={busy}
                    onClick={() =>
                      void onDelete(item)
                    }
                  >
                    Удалить
                  </button>
                </RowActions>
              </td>
            </tr>
          ),
        )}
      </DataTable>
    </DataSection>
  );
}


function ParticipantsTab({
  data,
  busy,
  onEdit,
  onDelete,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onEdit: (item: ParticipantRecord) => void;
  onDelete: (item: ParticipantRecord) => Promise<void>;
}) {
  return (
    <DataSection
      title="Участники"
      subtitle="Создание выполняется в бронировании; здесь можно исправить мастер-данные или удалить участника и пересчитать связанные бронирования."
    >
      <DataTable
        headers={[
          "Код",
          "Вендор",
          "Роль",
          "ФИО",
          "Ник",
          "Регистрация",
          "Check-in",
          "",
        ]}
      >
        {(data?.participants || []).map(
          (row) => (
            <tr key={row.link_id}>
              <td>
                {row.participant.code}
              </td>
              <td>{row.vendor_name}</td>
              <td>{row.role}</td>
              <td>
                {row.participant.last_name}{" "}
                {row.participant.first_name}
              </td>
              <td>
                @{row.participant.nickname}
              </td>
              <td>
                {row.registration_status}
              </td>
              <td>{row.checkin_status}</td>
              <td>
                <RowActions>
                  <button
                    className="button secondary small"
                    onClick={() =>
                      onEdit(
                        row.participant,
                      )
                    }
                  >
                    Изменить
                  </button>
                  <button
                    className="button danger small"
                    disabled={busy}
                    onClick={() =>
                      void onDelete(
                        row.participant,
                      )
                    }
                  >
                    Удалить
                  </button>
                </RowActions>
              </td>
            </tr>
          ),
        )}
      </DataTable>
    </DataSection>
  );
}


function FinancialRecordsTab({
  data,
  busy,
  onCancelPayment,
  onDeactivateCharge,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onCancelPayment: (
    paymentId: string,
  ) => Promise<void>;
  onDeactivateCharge: (
    chargeId: string,
  ) => Promise<void>;
}) {
  const paymentRows = (
    data?.bookings || []
  ).flatMap((booking) =>
    (booking.payments || []).map(
      (payment) => ({
        booking,
        payment,
      }),
    ),
  );

  const chargeRows = (
    data?.bookings || []
  ).flatMap((booking) =>
    (booking.charges || []).map(
      (charge) => ({
        booking,
        charge,
      }),
    ),
  );

  return (
    <div className="management-split">
      <DataSection
        title="Платежи"
        subtitle="Финансовые записи не удаляются физически. DELETE здесь означает soft-cancel и пересчёт Booking."
      >
        <DataTable
          headers={[
            "Код",
            "Booking",
            "Вендор",
            "Тип",
            "Сумма",
            "Метод",
            "Статус",
            "",
          ]}
        >
          {paymentRows.map(
            ({ booking, payment }) => (
              <tr key={payment.id}>
                <td>{payment.code}</td>
                <td>{booking.code}</td>
                <td>
                  {booking.vendor
                    ?.vendor_name ||
                    booking.vendor_name ||
                    "—"}
                </td>
                <td>
                  {payment.payment_type}
                </td>
                <td>
                  {money(payment.amount)}
                </td>
                <td>
                  {payment.payment_method}
                </td>
                <td>{payment.status}</td>
                <td>
                  {payment.status !==
                    "CANCELLED" && (
                    <button
                      className="button danger small"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void onCancelPayment(
                          payment.id,
                        )
                      }
                    >
                      Отменить
                    </button>
                  )}
                </td>
              </tr>
            ),
          )}
        </DataTable>
      </DataSection>

      <DataSection
        title="Начисления"
        subtitle="Automatic charges управляются pricing engine. Деактивировать вручную можно только manual/discount/surcharge."
      >
        <DataTable
          headers={[
            "Код",
            "Booking",
            "Тип",
            "Описание",
            "Сумма",
            "Auto",
            "Active",
            "",
          ]}
        >
          {chargeRows.map(
            ({ booking, charge }) => (
              <tr key={charge.id}>
                <td>{charge.code}</td>
                <td>{booking.code}</td>
                <td>
                  {charge.charge_type}
                </td>
                <td>
                  {charge.description}
                </td>
                <td>
                  {money(charge.amount)}
                </td>
                <td>
                  {charge.automatic
                    ? "YES"
                    : "NO"}
                </td>
                <td>
                  {charge.active
                    ? "YES"
                    : "NO"}
                </td>
                <td>
                  {!charge.automatic &&
                    charge.active && (
                    <button
                      className="button danger small"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void onDeactivateCharge(
                          charge.id,
                        )
                      }
                    >
                      Деактивировать
                    </button>
                  )}
                </td>
              </tr>
            ),
          )}
        </DataTable>
      </DataSection>
    </div>
  );
}


function LayoutTab({
  data,
  busy,
  onEditZone,
  onEditTable,
  onDeleteZone,
  onDeleteTable,
}: {
  data: AdminManagementState | null;
  busy: boolean;
  onEditZone: (item: LayoutZoneRecord) => void;
  onEditTable: (item: LayoutTableRecord) => void;
  onDeleteZone: (item: LayoutZoneRecord) => Promise<void>;
  onDeleteTable: (item: LayoutTableRecord) => Promise<void>;
}) {
  const zonesById = new Map(
    (data?.zones || []).map(
      (zone) => [zone.id, zone],
    ),
  );

  return (
    <div className="management-split">
      <DataSection
        title="Зоны"
        subtitle="Создание зон выполняется во вкладке Рассадка → Зоны."
      >
        <DataTable
          headers={[
            "Код",
            "Название",
            "Тип",
            "X/Y",
            "Размер",
            "",
          ]}
        >
          {(data?.zones || []).map(
            (item) => (
              <tr key={item.id}>
                <td>{item.code}</td>
                <td>{item.zone_name}</td>
                <td>{item.zone_type}</td>
                <td>
                  {item.x} / {item.y}
                </td>
                <td>
                  {item.width} ×{" "}
                  {item.height}
                </td>
                <td>
                  <RowActions>
                    <button
                      className="button secondary small"
                      onClick={() =>
                        onEditZone(item)
                      }
                    >
                      Изменить
                    </button>
                    <button
                      className="button danger small"
                      disabled={busy}
                      onClick={() =>
                        void onDeleteZone(
                          item,
                        )
                      }
                    >
                      Удалить
                    </button>
                  </RowActions>
                </td>
              </tr>
            ),
          )}
        </DataTable>
      </DataSection>

      <DataSection
        title="Столы"
        subtitle="Создание столов выполняется быстрыми кнопками в Рассадке."
      >
        <DataTable
          headers={[
            "№",
            "Подпись",
            "Зона",
            "Слоты",
            "X/Y",
            "",
          ]}
        >
          {(data?.tables || []).map(
            (item) => (
              <tr key={item.id}>
                <td>
                  {item.table_number}
                </td>
                <td>
                  {item.table_label}
                </td>
                <td>
                  {item.zone_id
                    ? zonesById.get(
                        item.zone_id,
                      )?.zone_name || "—"
                    : "Без зоны"}
                </td>
                <td>
                  {item.capacity_slots}
                </td>
                <td>
                  {item.x} / {item.y}
                </td>
                <td>
                  <RowActions>
                    <button
                      className="button secondary small"
                      onClick={() =>
                        onEditTable(item)
                      }
                    >
                      Изменить
                    </button>
                    <button
                      className="button danger small"
                      disabled={busy}
                      onClick={() =>
                        void onDeleteTable(
                          item,
                        )
                      }
                    >
                      Удалить
                    </button>
                  </RowActions>
                </td>
              </tr>
            ),
          )}
        </DataTable>
      </DataSection>
    </div>
  );
}


function SeatingTableTab({
  data,
  assignmentsByTable,
  bookingsById,
  onAssign,
  onClear,
}: {
  data: AdminManagementState | null;
  assignmentsByTable: Map<
    string,
    TableAssignmentRecord[]
  >;
  bookingsById: Map<string, BookingRecord>;
  onAssign: (
    bookingId: string,
    tableId: string,
    slot: number,
  ) => Promise<void>;
  onClear: (
    bookingId: string,
  ) => Promise<void>;
}) {
  const seatable = (
    data?.bookings || []
  ).filter((booking) =>
    [
      "SUBMITTED",
      "APPROVED",
      "AWAITING_PAYMENT",
      "CONFIRMED",
    ].includes(booking.booking_status),
  );

  return (
    <DataSection
      title="Табличная рассадка"
      subtitle="Прямое редактирование связи вендор ↔ стол. Выбор уже размещённого вендора переносит его; конфликт разрешается теми же правилами MOVE/SWAP, что и на карте."
    >
      <DataTable
        headers={[
          "Стол",
          "Зона",
          "A",
          "B",
        ]}
      >
        {(data?.tables || []).map(
          (table) => {
            const assignments =
              assignmentsByTable.get(
                table.id,
              ) || [];
            const a =
              assignments.find(
                (item) =>
                  item.start_slot === 1,
              ) || null;
            const full =
              a?.slot_count === 2;
            const b = full
              ? a
              : assignments.find(
                  (item) =>
                    item.start_slot ===
                    2,
                ) || null;

            const zone =
              data?.zones.find(
                (item) =>
                  item.id ===
                  table.zone_id,
              ) || null;

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
                  <SeatSelect
                    tableId={table.id}
                    slot={1}
                    current={a}
                    bookings={seatable}
                    bookingsById={
                      bookingsById
                    }
                    onAssign={onAssign}
                    onClear={onClear}
                  />
                </td>
                <td>
                  <SeatSelect
                    tableId={table.id}
                    slot={2}
                    current={b}
                    bookings={seatable}
                    bookingsById={
                      bookingsById
                    }
                    onAssign={onAssign}
                    onClear={onClear}
                    disabled={full}
                  />
                </td>
              </tr>
            );
          },
        )}
      </DataTable>
    </DataSection>
  );
}


function SeatSelect({
  tableId,
  slot,
  current,
  bookings,
  bookingsById,
  onAssign,
  onClear,
  disabled = false,
}: {
  tableId: string;
  slot: number;
  current:
    | TableAssignmentRecord
    | null;
  bookings: BookingRecord[];
  bookingsById: Map<string, BookingRecord>;
  onAssign: (
    bookingId: string,
    tableId: string,
    slot: number,
  ) => Promise<void>;
  onClear: (
    bookingId: string,
  ) => Promise<void>;
  disabled?: boolean;
}) {
  const currentBooking =
    current
      ? bookingsById.get(
          current.booking_id,
        ) || current.booking
      : null;

  return (
    <select
      className="seat-select"
      disabled={disabled}
      value={
        currentBooking?.id || ""
      }
      onChange={async (event) => {
        const next =
          event.target.value;

        if (!next) {
          if (currentBooking) {
            await onClear(
              currentBooking.id,
            );
          }
          return;
        }

        await onAssign(
          next,
          tableId,
          slot,
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
          {booking.vendor?.vendor_name ||
            booking.vendor_name ||
            booking.code}{" "}
          · {booking.booking_type}
        </option>
      ))}
    </select>
  );
}


function CrudMatrix() {
  const rows = [
    ["Event", "✓", "✓", "✓", "✓ cascade", "Удаление мероприятия каскадно удаляет все event-specific данные; orphan participants очищаются."],
    ["Tariff", "✓", "✓", "✓", "✓ / cascade", "Используемый тариф удаляется только с явным cascade; безопасная альтернатива — Active=false."],
    ["Vendor", "✓", "✓", "✓", "✓ / cascade", "Master-объект. При cascade удаляются все его bookings во всех событиях."],
    ["Booking", "✓", "✓", "✓", "✓ cascade", "Удаляются participant links, charges, payments, seating, check-in; orphan participants очищаются."],
    ["Participant", "через Booking", "✓", "✓", "✓ / cascade", "При удалении links убираются, затронутые bookings пересчитываются."],
    ["Zone", "✓", "✓", "✓", "✓", "Столы сохраняются и получают zone_id=NULL."],
    ["Table", "✓", "✓", "✓", "✓ cascade", "Assignments удаляются, bookings становятся UNASSIGNED."],
    ["Assignment", "✓", "✓", "✓ MOVE", "✓ unassign", "Карта и табличная форма используют единые MOVE/SWAP правила."],
    ["Payment", "✓", "✓", "—", "soft cancel", "Финансовая история не удаляется физически; отмена меняет status и пересчитывает booking."],
    ["Charge", "✓", "✓", "—", "deactivate", "Automatic управляются pricing engine; manual можно деактивировать."],
    ["User", "✓", "✓", "✓", "soft deactivate", "Физическое удаление не используется из-за AuditLog и безопасности."],
    ["CheckInLog", "system", "✓", "append-only", "append-only", "Операционный журнал сохраняется."],
    ["AuditLog", "system", "✓", "append-only", "append-only", "Аудит не редактируется и не удаляется."],
  ];

  return (
    <DataSection
      title="CRUD-матрица"
      subtitle="Не все сущности должны иметь физический DELETE: финансовые и аудиторские журналы сохраняются append-only/soft-delete."
    >
      <DataTable
        headers={[
          "Объект",
          "Create",
          "Read",
          "Update",
          "Delete",
          "Правило",
        ]}
      >
        {rows.map((row) => (
          <tr key={row[0]}>
            {row.map((cell, index) => (
              <td key={`${row[0]}-${index}`}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </DataTable>
    </DataSection>
  );
}


function ManagementEditor({
  editor,
  data,
  busy,
  onClose,
  onSave,
}: {
  editor: Editor;
  data: AdminManagementState | null;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  if (editor.type === "event") {
    return (
      <EventEditor
        item={editor.item}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  if (editor.type === "tariff") {
    return (
      <TariffEditor
        item={editor.item}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  if (editor.type === "vendor") {
    return (
      <VendorEditor
        item={editor.item}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  if (editor.type === "booking") {
    return (
      <BookingEditor
        item={editor.item}
        data={data}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  if (editor.type === "participant") {
    return (
      <ParticipantEditor
        item={editor.item}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  if (editor.type === "zone") {
    return (
      <ZoneEditor
        item={editor.item}
        busy={busy}
        onClose={onClose}
        onSave={onSave}
      />
    );
  }

  return (
    <TableEditor
      item={editor.item}
      zones={data?.zones || []}
      busy={busy}
      onClose={onClose}
      onSave={onSave}
    />
  );
}


function EventEditor({
  item,
  busy,
  onClose,
  onSave,
}: {
  item?: EventRecord;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={
        item
          ? `Мероприятие ${item.code}`
          : "Новое мероприятие"
      }
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          event_name:
            text(form, "event_name"),
          start_date:
            text(form, "start_date"),
          end_date:
            text(form, "end_date"),
          venue:
            optional(form, "venue"),
          city: optional(form, "city"),
          currency:
            text(form, "currency") ||
            "RUB",
          status: text(form, "status"),
          registration_open:
            checked(
              form,
              "registration_open",
            ),
          vendor_checkin_open:
            checked(
              form,
              "vendor_checkin_open",
            ),
          seating_preferences_open:
            checked(
              form,
              "seating_preferences_open",
            ),
          notes:
            optional(form, "notes"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Название *" wide>
          <input
            name="event_name"
            defaultValue={
              item?.event_name || ""
            }
            required
          />
        </Field>
        <Field label="Начало *">
          <input
            name="start_date"
            type="date"
            defaultValue={
              item?.start_date || ""
            }
            required
          />
        </Field>
        <Field label="Окончание *">
          <input
            name="end_date"
            type="date"
            defaultValue={
              item?.end_date || ""
            }
            required
          />
        </Field>
        <Field label="Город">
          <input
            name="city"
            defaultValue={
              item?.city || ""
            }
          />
        </Field>
        <Field label="Площадка">
          <input
            name="venue"
            defaultValue={
              item?.venue || ""
            }
          />
        </Field>
        <Field label="Валюта">
          <input
            name="currency"
            defaultValue={
              item?.currency || "RUB"
            }
          />
        </Field>
        <Field label="Статус">
          <select
            name="status"
            defaultValue={
              item?.status || "DRAFT"
            }
          >
            {[
              "DRAFT",
              "REGISTRATION",
              "ACTIVE",
              "CLOSED",
              "ARCHIVED",
            ].map((value) => (
              <option
                value={value}
                key={value}
              >
                {value}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="registration_open"
          type="checkbox"
          defaultChecked={
            item?.registration_open ||
            false
          }
        />
        <span>Регистрация открыта</span>
      </label>
      <label className="checkbox">
        <input
          name="vendor_checkin_open"
          type="checkbox"
          defaultChecked={
            item?.vendor_checkin_open ||
            false
          }
        />
        <span>Check-in открыт</span>
      </label>
      <label className="checkbox">
        <input
          name="seating_preferences_open"
          type="checkbox"
          defaultChecked={
            item?.seating_preferences_open ||
            false
          }
        />
        <span>Сбор пожеланий по рассадке открыт</span>
      </label>
      <Field label="Комментарий">
        <textarea
          name="notes"
          rows={3}
          defaultValue={
            item?.notes || ""
          }
        />
      </Field>
    </FormModal>
  );
}


function TariffEditor({
  item,
  busy,
  onClose,
  onSave,
}: {
  item?: TariffRecord;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={
        item
          ? `Тариф ${item.code}`
          : "Новый тариф"
      }
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          tariff_name:
            text(form, "tariff_name"),
          booking_type:
            text(form, "booking_type"),
          base_price: Number(
            text(form, "base_price"),
          ),
          included_helpers: Number(
            text(
              form,
              "included_helpers",
            ),
          ),
          extra_participant_price:
            Number(
              text(
                form,
                "extra_participant_price",
              ),
            ),
          valid_from:
            text(form, "valid_from"),
          valid_to:
            optional(form, "valid_to"),
          active:
            checked(form, "active"),
          notes:
            optional(form, "notes"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Название *" wide>
          <input
            name="tariff_name"
            defaultValue={
              item?.tariff_name || ""
            }
            required
          />
        </Field>
        <Field label="Тип">
          <select
            name="booking_type"
            defaultValue={
              item?.booking_type ||
              "FULL"
            }
          >
            <option value="FULL">
              FULL
            </option>
            <option value="HALF">
              HALF
            </option>
          </select>
        </Field>
        <Field label="Базовая цена">
          <input
            name="base_price"
            type="number"
            step="0.01"
            defaultValue={
              item?.base_price || 0
            }
          />
        </Field>
        <Field label="Включено помощников">
          <input
            name="included_helpers"
            type="number"
            defaultValue={
              item?.included_helpers || 0
            }
          />
        </Field>
        <Field label="Цена доп. участника">
          <input
            name="extra_participant_price"
            type="number"
            step="0.01"
            defaultValue={
              item?.extra_participant_price ||
              0
            }
          />
        </Field>
        <Field label="Действует с">
          <input
            name="valid_from"
            type="date"
            defaultValue={
              item?.valid_from || ""
            }
            required
          />
        </Field>
        <Field label="Действует до">
          <input
            name="valid_to"
            type="date"
            defaultValue={
              item?.valid_to || ""
            }
          />
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="active"
          type="checkbox"
          defaultChecked={
            item?.active ?? true
          }
        />
        <span>Активен</span>
      </label>
      <Field label="Комментарий">
        <textarea
          name="notes"
          rows={3}
          defaultValue={
            item?.notes || ""
          }
        />
      </Field>
    </FormModal>
  );
}


function VendorEditor({
  item,
  busy,
  onClose,
  onSave,
}: {
  item?: VendorRecord;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={
        item
          ? `Вендор ${item.code}`
          : "Новый вендор"
      }
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          vendor_name:
            text(form, "vendor_name"),
          legal_name:
            optional(form, "legal_name"),
          email: text(form, "email"),
          phone: optional(form, "phone"),
          telegram:
            optional(form, "telegram"),
          website:
            optional(form, "website"),
          social_link:
            optional(form, "social_link"),
          description:
            optional(form, "description"),
          notes:
            optional(form, "notes"),
          active:
            checked(form, "active"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Название *" wide>
          <input
            name="vendor_name"
            defaultValue={
              item?.vendor_name || ""
            }
            required
          />
        </Field>
        <Field label="Юр. название">
          <input
            name="legal_name"
            defaultValue={
              item?.legal_name || ""
            }
          />
        </Field>
        <Field label="E-mail *">
          <input
            name="email"
            type="email"
            defaultValue={
              item?.email || ""
            }
            required
          />
        </Field>
        <Field label="Телефон">
          <input
            name="phone"
            defaultValue={
              item?.phone || ""
            }
          />
        </Field>
        <Field label="Telegram">
          <input
            name="telegram"
            defaultValue={
              item?.telegram || ""
            }
          />
        </Field>
        <Field label="Website">
          <input
            name="website"
            defaultValue={
              item?.website || ""
            }
          />
        </Field>
        <Field label="Соцсеть">
          <input
            name="social_link"
            defaultValue={
              item?.social_link || ""
            }
          />
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="active"
          type="checkbox"
          defaultChecked={
            item?.active ?? true
          }
        />
        <span>Активен</span>
      </label>
      <Field label="Описание">
        <textarea
          name="description"
          rows={2}
          defaultValue={
            item?.description || ""
          }
        />
      </Field>
      <Field label="Комментарий">
        <textarea
          name="notes"
          rows={2}
          defaultValue={
            item?.notes || ""
          }
        />
      </Field>
    </FormModal>
  );
}


function BookingEditor({
  item,
  data,
  busy,
  onClose,
  onSave,
}: {
  item: BookingRecord;
  data: AdminManagementState | null;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={`Бронирование ${item.code}`}
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          vendor_id:
            text(form, "vendor_id"),
          tariff_id:
            text(form, "tariff_id"),
          notes:
            optional(form, "notes"),
        });
      }}
    >
      <Field label="Вендор">
        <select
          name="vendor_id"
          defaultValue={item.vendor_id}
        >
          {(data?.vendors || []).map(
            (vendor) => (
              <option
                key={vendor.id}
                value={vendor.id}
              >
                {vendor.vendor_name}
              </option>
            ),
          )}
        </select>
      </Field>
      <Field label="Тариф">
        <select
          name="tariff_id"
          defaultValue={item.tariff_id}
        >
          {(data?.tariffs || []).map(
            (tariff) => (
              <option
                key={tariff.id}
                value={tariff.id}
              >
                {tariff.tariff_name} ·{" "}
                {tariff.booking_type}
              </option>
            ),
          )}
        </select>
      </Field>
      <Field label="Комментарий">
        <textarea
          name="notes"
          rows={3}
          defaultValue={
            item.notes || ""
          }
        />
      </Field>
      <div className="management-note">
        Смена тарифа каскадно обновляет snapshot
        цены и запускает pricing recalculation.
        Платежи сохраняются; возможен статус
        OVERPAID.
      </div>
    </FormModal>
  );
}


function ParticipantEditor({
  item,
  busy,
  onClose,
  onSave,
}: {
  item: ParticipantRecord;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={`Участник ${item.code}`}
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          last_name:
            text(form, "last_name"),
          first_name:
            text(form, "first_name"),
          middle_name:
            optional(
              form,
              "middle_name",
            ),
          nickname:
            text(form, "nickname"),
          email:
            optional(form, "email"),
          phone:
            optional(form, "phone"),
          telegram:
            optional(form, "telegram"),
          active:
            checked(form, "active"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Фамилия">
          <input
            name="last_name"
            defaultValue={
              item.last_name
            }
            required
          />
        </Field>
        <Field label="Имя">
          <input
            name="first_name"
            defaultValue={
              item.first_name
            }
            required
          />
        </Field>
        <Field label="Отчество">
          <input
            name="middle_name"
            defaultValue={
              item.middle_name || ""
            }
          />
        </Field>
        <Field label="Ник">
          <input
            name="nickname"
            defaultValue={
              item.nickname
            }
            required
          />
        </Field>
        <Field label="E-mail">
          <input
            name="email"
            type="email"
            defaultValue={
              item.email || ""
            }
          />
        </Field>
        <Field label="Телефон">
          <input
            name="phone"
            defaultValue={
              item.phone || ""
            }
          />
        </Field>
        <Field label="Telegram" wide>
          <input
            name="telegram"
            defaultValue={
              item.telegram || ""
            }
          />
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="active"
          type="checkbox"
          defaultChecked={item.active}
        />
        <span>Активен</span>
      </label>
    </FormModal>
  );
}


function ZoneEditor({
  item,
  busy,
  onClose,
  onSave,
}: {
  item: LayoutZoneRecord;
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={`Зона ${item.code}`}
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          zone_name:
            text(form, "zone_name"),
          zone_type:
            text(form, "zone_type"),
          color:
            optional(form, "color"),
          x: Number(text(form, "x")),
          y: Number(text(form, "y")),
          width: Number(
            text(form, "width"),
          ),
          height: Number(
            text(form, "height"),
          ),
          active:
            checked(form, "active"),
          notes:
            optional(form, "notes"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Название" wide>
          <input
            name="zone_name"
            defaultValue={
              item.zone_name
            }
            required
          />
        </Field>
        <Field label="Тип">
          <input
            name="zone_type"
            defaultValue={
              item.zone_type
            }
          />
        </Field>
        <Field label="Цвет">
          <input
            name="color"
            defaultValue={
              item.color || ""
            }
          />
        </Field>
        <Field label="X">
          <input
            name="x"
            type="number"
            defaultValue={item.x}
          />
        </Field>
        <Field label="Y">
          <input
            name="y"
            type="number"
            defaultValue={item.y}
          />
        </Field>
        <Field label="Ширина">
          <input
            name="width"
            type="number"
            defaultValue={item.width}
          />
        </Field>
        <Field label="Высота">
          <input
            name="height"
            type="number"
            defaultValue={item.height}
          />
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="active"
          type="checkbox"
          defaultChecked={item.active}
        />
        <span>Активна</span>
      </label>
      <Field label="Комментарий">
        <textarea
          name="notes"
          defaultValue={
            item.notes || ""
          }
        />
      </Field>
    </FormModal>
  );
}


function TableEditor({
  item,
  zones,
  busy,
  onClose,
  onSave,
}: {
  item: LayoutTableRecord;
  zones: LayoutZoneRecord[];
  busy: boolean;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
  ) => Promise<void>;
}) {
  return (
    <FormModal
      title={`Стол ${item.code}`}
      busy={busy}
      onClose={onClose}
      onSubmit={async (form) => {
        await onSave({
          table_label:
            text(form, "table_label"),
          zone_id:
            text(form, "zone_id") ||
            null,
          capacity_slots: Number(
            text(
              form,
              "capacity_slots",
            ),
          ),
          x: Number(text(form, "x")),
          y: Number(text(form, "y")),
          width: Number(
            text(form, "width"),
          ),
          height: Number(
            text(form, "height"),
          ),
          active:
            checked(form, "active"),
          notes:
            optional(form, "notes"),
        });
      }}
    >
      <div className="form-grid two">
        <Field label="Подпись">
          <input
            name="table_label"
            defaultValue={
              item.table_label
            }
            required
          />
        </Field>
        <Field label="Зона">
          <select
            name="zone_id"
            defaultValue={
              item.zone_id || ""
            }
          >
            <option value="">
              Без зоны
            </option>
            {zones.map((zone) => (
              <option
                key={zone.id}
                value={zone.id}
              >
                {zone.zone_name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Слоты">
          <select
            name="capacity_slots"
            defaultValue={String(
              item.capacity_slots,
            )}
          >
            <option value="2">
              A/B
            </option>
            <option value="1">
              Один
            </option>
          </select>
        </Field>
        <Field label="X">
          <input
            name="x"
            type="number"
            defaultValue={item.x}
          />
        </Field>
        <Field label="Y">
          <input
            name="y"
            type="number"
            defaultValue={item.y}
          />
        </Field>
        <Field label="Ширина">
          <input
            name="width"
            type="number"
            defaultValue={item.width}
          />
        </Field>
        <Field label="Высота">
          <input
            name="height"
            type="number"
            defaultValue={item.height}
          />
        </Field>
      </div>
      <label className="checkbox">
        <input
          name="active"
          type="checkbox"
          defaultChecked={item.active}
        />
        <span>Активен</span>
      </label>
      <Field label="Комментарий">
        <textarea
          name="notes"
          defaultValue={
            item.notes || ""
          }
        />
      </Field>
    </FormModal>
  );
}


function FormModal({
  title,
  busy,
  onClose,
  onSubmit,
  children,
}: {
  title: string;
  busy: boolean;
  onClose: () => void;
  onSubmit: (
    form: FormData,
  ) => Promise<void>;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal wide">
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <form
          className="stack"
          onSubmit={async (
            event: FormEvent<HTMLFormElement>,
          ) => {
            event.preventDefault();
            await onSubmit(
              new FormData(
                event.currentTarget,
              ),
            );
          }}
        >
          {children}

          <div className="modal-actions">
            <button
              className="button secondary"
              type="button"
              onClick={onClose}
            >
              Отмена
            </button>
            <button
              className="button primary"
              type="submit"
              disabled={busy}
            >
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


function DataSection({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="management-section">
      <div className="management-section-head">
        <div>
          <h2>{title}</h2>
          {subtitle && (
            <p>{subtitle}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}


function DataTable({
  headers,
  children,
}: {
  headers: string[];
  children: ReactNode;
}) {
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}


function RowActions({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="row-actions">
      {children}
    </div>
  );
}


function Field({
  label,
  wide = false,
  children,
}: {
  label: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={wide ? "wide-field" : ""}>
      <span>{label}</span>
      {children}
    </label>
  );
}


function text(
  form: FormData,
  key: string,
) {
  return String(form.get(key) || "").trim();
}


function optional(
  form: FormData,
  key: string,
) {
  const value = text(form, key);
  return value || null;
}


function checked(
  form: FormData,
  key: string,
) {
  return form.get(key) === "on";
}


function money(value: number) {
  return Number(value || 0).toLocaleString(
    "ru-RU",
    {
      maximumFractionDigits: 2,
    },
  );
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
