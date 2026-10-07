import {
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api } from "./api";
import type {
  BookingParticipantRecord,
  BookingRecord,
  CurrentUser,
  EventRecord,
  LayoutTableRecord,
  LayoutZoneRecord,
  SeatingOverview,
  TableAssignmentRecord,
} from "./types";

type MainTab = "layout" | "zones" | "authors";
type BookingFilter = "UNASSIGNED" | "ASSIGNED" | "ALL";

type DragPayload = {
  bookingId: string;
};

type TablePreset = {
  zoneId: string;
  columns: number;
  startX: number;
  startY: number;
  xGap: number;
  yGap: number;
  width: number;
  height: number;
  capacitySlots: number;
  numberingPrefix: string;
};

const TABLE_PRESET_STORAGE_KEY =
  "conman:seating:table-preset";

const DEFAULT_TABLE_PRESET: TablePreset = {
  zoneId: "",
  columns: 8,
  startX: 28,
  startY: 28,
  xGap: 14,
  yGap: 16,
  width: 112,
  height: 62,
  capacitySlots: 2,
  numberingPrefix: "",
};

export default function SeatingPage({
  user,
  currentEvent,
}: {
  user: CurrentUser;
  currentEvent: EventRecord | null;
}) {
  const [data, setData] =
    useState<SeatingOverview | null>(null);
  const [error, setError] =
    useState<string | null>(null);
  const [busy, setBusy] =
    useState(false);
  const [tab, setTab] =
    useState<MainTab>("layout");
  const [movingTableId, setMovingTableId] =
    useState<string | null>(null);
  const [movingZoneId, setMovingZoneId] =
    useState<string | null>(null);
  const [selectedBookingId, setSelectedBookingId] =
    useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] =
    useState<string | null>(null);
  const [bookingQuery, setBookingQuery] =
    useState("");
  const [bookingFilter, setBookingFilter] =
    useState<BookingFilter>("UNASSIGNED");
  const [editingTable, setEditingTable] =
    useState<LayoutTableRecord | null>(null);
  const [snapMode, setSnapMode] =
    useState(true);
  const [gridSize, setGridSize] =
    useState(24);
  const [showTableModal, setShowTableModal] =
    useState(false);
  const [quickTableCount, setQuickTableCount] =
    useState("12");
  const [tablePreset, setTablePreset] =
    useState<TablePreset>(
      readTablePreset(),
    );

  const canEdit = ["ADMIN", "MANAGER"].includes(
    user.role,
  );
  const canAssign = [
    "ADMIN",
    "MANAGER",
    "REGISTRATION",
  ].includes(user.role);

  async function reload() {
    if (!currentEvent) {
      setData(null);
      return;
    }

    try {
      setError(null);
      setData(
        await api.seatingLayout(currentEvent.id),
      );
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    void reload();
  }, [currentEvent?.id]);

  useEffect(() => {
    persistTablePreset(tablePreset);
  }, [tablePreset]);

  useEffect(() => {
    if (
      selectedZoneId &&
      !data?.zones.some(
        (zone) => zone.id === selectedZoneId,
      )
    ) {
      setSelectedZoneId(null);
    }
  }, [data?.zones, selectedZoneId]);

  const assignmentsByTable = useMemo(() => {
    const map = new Map<
      string,
      TableAssignmentRecord[]
    >();
    for (const item of data?.assignments || []) {
      const list = map.get(item.table_id) || [];
      list.push(item);
      map.set(item.table_id, list);
    }
    for (const list of map.values()) {
      list.sort(
        (a, b) => a.start_slot - b.start_slot,
      );
    }
    return map;
  }, [data]);

  const tableMap = useMemo(
    () =>
      new Map(
        (data?.tables || []).map((table) => [
          table.id,
          table,
        ]),
      ),
    [data],
  );

  const zoneMap = useMemo(
    () =>
      new Map(
        (data?.zones || []).map((zone) => [
          zone.id,
          zone,
        ]),
      ),
    [data],
  );

  const assignmentByBookingId = useMemo(() => {
    const map = new Map<
      string,
      TableAssignmentRecord
    >();
    for (const item of data?.assignments || []) {
      map.set(item.booking_id, item);
    }
    return map;
  }, [data]);

  const allBookings = useMemo(() => {
    const map = new Map<string, BookingRecord>();

    for (const item of data?.assignments || []) {
      if (item.booking) {
        map.set(item.booking.id, item.booking);
      }
    }

    for (const item of data?.unassigned_bookings ||
      []) {
      map.set(item.id, item);
    }

    const list = [...map.values()];
    list.sort((a, b) => {
      const aAssigned =
        assignmentByBookingId.has(a.id) ? 1 : 0;
      const bAssigned =
        assignmentByBookingId.has(b.id) ? 1 : 0;

      if (aAssigned !== bAssigned) {
        return aAssigned - bAssigned;
      }

      return bookingDisplayName(a).localeCompare(
        bookingDisplayName(b),
        "ru",
      );
    });

    return list;
  }, [data, assignmentByBookingId]);

  const filteredBookings = useMemo(() => {
    const query = bookingQuery.trim().toLowerCase();

    const byStatus = allBookings.filter((booking) => {
      const assigned = assignmentByBookingId.has(booking.id);

      if (bookingFilter === "UNASSIGNED") {
        return !assigned;
      }

      if (bookingFilter === "ASSIGNED") {
        return assigned;
      }

      return true;
    });

    return query
      ? byStatus.filter((booking) =>
          bookingSearchText(booking)
            .toLowerCase()
            .includes(query),
        )
      : byStatus;
  }, [
    allBookings,
    bookingQuery,
    bookingFilter,
    assignmentByBookingId,
  ]);

  const selectedBooking =
    allBookings.find(
      (item) => item.id === selectedBookingId,
    ) || null;
  const selectedZone =
    data?.zones.find(
      (item) => item.id === selectedZoneId,
    ) || null;

  async function handleAssign(
    bookingId: string,
    tableId: string,
    startSlot: number,
  ) {
    try {
      setBusy(true);
      await api.assignBookingToTable({
        booking_id: bookingId,
        table_id: tableId,
        start_slot: startSlot,
      });
      setSelectedBookingId(bookingId);
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleUnassign(
    bookingId: string,
  ) {
    try {
      setBusy(true);
      await api.unassignBookingFromTable({
        booking_id: bookingId,
      });
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function moveTable(
    table: LayoutTableRecord,
    nextX: number,
    nextY: number,
  ) {
    setMovingTableId(table.id);
    try {
      const [x, y] = normalizePoint(
        nextX,
        nextY,
        snapMode,
        gridSize,
      );
      await api.updateSeatingTable(table.id, {
        x,
        y,
      });
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setMovingTableId(null);
    }
  }

  async function moveZone(
    zone: LayoutZoneRecord,
    nextX: number,
    nextY: number,
  ) {
    setMovingZoneId(zone.id);
    try {
      const [x, y] = normalizePoint(
        nextX,
        nextY,
        snapMode,
        gridSize,
      );
      await api.updateSeatingZone(zone.id, {
        x,
        y,
      });
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setMovingZoneId(null);
    }
  }

  async function snapAllTablesToGrid() {
    if (!data?.tables.length) return;
    try {
      setBusy(true);
      for (const table of data.tables) {
        const [x, y] = normalizePoint(
          table.x,
          table.y,
          true,
          gridSize,
        );
        if (x !== table.x || y !== table.y) {
          await api.updateSeatingTable(table.id, {
            x,
            y,
          });
        }
      }
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function snapAllZonesToGrid() {
    if (!data?.zones.length) return;
    try {
      setBusy(true);
      for (const zone of data.zones) {
        const [x, y] = normalizePoint(
          zone.x,
          zone.y,
          true,
          gridSize,
        );
        if (x !== zone.x || y !== zone.y) {
          await api.updateSeatingZone(zone.id, {
            x,
            y,
          });
        }
      }
      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function createQuickTables(
    count: number,
  ) {
    if (!currentEvent || !data) return;

    try {
      setBusy(true);

      const matchingTables = data.tables.filter(
        (table) =>
          (table.zone_id || "") === tablePreset.zoneId,
      );

      const nextNumber = data.tables.length
        ? Math.max(
            ...data.tables.map(
              (table) => table.table_number,
            ),
          ) + 1
        : 1;

      const indexBase = matchingTables.length;

      const startIndex = indexBase;
      const startRow = Math.floor(
        startIndex / tablePreset.columns,
      );
      const startCol =
        startIndex % tablePreset.columns;

      const startX =
        tablePreset.startX +
        startCol *
          (tablePreset.width + tablePreset.xGap);
      const startY =
        tablePreset.startY +
        startRow *
          (tablePreset.height + tablePreset.yGap);

      await api.createSeatingTables({
        zone_id:
          tablePreset.zoneId || null,
        start_number: nextNumber,
        count,
        columns: tablePreset.columns,
        start_x: startX,
        start_y: startY,
        x_gap: tablePreset.xGap,
        y_gap: tablePreset.yGap,
        width: tablePreset.width,
        height: tablePreset.height,
        capacity_slots:
          tablePreset.capacitySlots,
        numbering_prefix:
          tablePreset.numberingPrefix || null,
      });

      await reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-header seating-header">
        <div>
          <div className="eyebrow">
            Seating · Step 4.1
          </div>
          <h1>Рассадка и карта маркета</h1>
          <p className="muted header-subtitle">
            {currentEvent?.event_name ||
              "Текущее мероприятие не выбрано"}
          </p>
        </div>
      </header>

      {error && (
        <div className="alert error">
          {error}
        </div>
      )}

      {!currentEvent && (
        <section className="panel">
          <div className="empty-state">
            Сначала выберите текущее мероприятие.
          </div>
        </section>
      )}

      {currentEvent && (
        <div className="seating-two-column">
          <aside className="seating-side">
            <section className="panel candy-panel">
              <div className="panel-heading">
                <div>
                  <h2>Сводка</h2>
                  <p className="muted compact">
                    Карта столов и список авторов —
                    основные ручные артефакты
                    процесса.
                  </p>
                </div>
              </div>

              <div className="seating-metrics">
                <Metric
                  label="Зоны"
                  value={String(
                    data?.zones.length || 0,
                  )}
                />
                <Metric
                  label="Столы"
                  value={String(
                    data?.tables.length || 0,
                  )}
                />
                <Metric
                  label="Назначено"
                  value={String(
                    data?.assignments.length || 0,
                  )}
                />
                <Metric
                  label="Без места"
                  value={String(
                    data?.unassigned_bookings
                      .length || 0,
                  )}
                />
              </div>
            </section>

            <BookingPickerPanel
              bookings={filteredBookings}
              query={bookingQuery}
              onQueryChange={setBookingQuery}
              filter={bookingFilter}
              onFilterChange={setBookingFilter}
              selectedBookingId={selectedBookingId}
              onSelect={(bookingId) =>
                setSelectedBookingId((current) =>
                  current === bookingId ? null : bookingId,
                )
              }
              assignmentByBookingId={assignmentByBookingId}
              tableMap={tableMap}
              onUnassign={handleUnassign}
            />

            {canEdit && (
              <TableQuickCreatePanel
                busy={busy}
                preset={tablePreset}
                zones={data?.zones || []}
                quickTableCount={quickTableCount}
                setQuickTableCount={
                  setQuickTableCount
                }
                onQuickAddOne={() =>
                  void createQuickTables(1)
                }
                onQuickAddFive={() =>
                  void createQuickTables(5)
                }
                onQuickAddN={() =>
                  void createQuickTables(
                    Math.max(
                      1,
                      Number(quickTableCount) || 1,
                    ),
                  )
                }
                onOpenSettings={() =>
                  setShowTableModal(true)
                }
              />
            )}

            <section className="panel candy-panel">
              <div className="panel-heading">
                <div>
                  <h2>Режим размещения</h2>
                  <p className="muted compact">
                    Можно таскать столы свободно
                    либо с привязкой к сетке.
                  </p>
                </div>
              </div>

              <div className="seating-grid-tools">
                <div className="segmented">
                  <button
                    type="button"
                    className={
                      snapMode
                        ? "segment active"
                        : "segment"
                    }
                    onClick={() =>
                      setSnapMode(true)
                    }
                  >
                    Привязка к сетке
                  </button>
                  <button
                    type="button"
                    className={
                      !snapMode
                        ? "segment active"
                        : "segment"
                    }
                    onClick={() =>
                      setSnapMode(false)
                    }
                  >
                    Свободно
                  </button>
                </div>

                <label>
                  <span>Шаг сетки</span>
                  <input
                    type="number"
                    min="8"
                    max="80"
                    value={gridSize}
                    onChange={(event) =>
                      setGridSize(
                        Math.max(
                          8,
                          Number(
                            event.target.value,
                          ) || 24,
                        ),
                      )
                    }
                  />
                </label>

                <div className="stack compact-stack">
                  <button
                    className="button secondary full"
                    type="button"
                    onClick={() =>
                      void snapAllTablesToGrid()
                    }
                    disabled={busy}
                  >
                    Привязать все столы
                  </button>

                  <button
                    className="button secondary full"
                    type="button"
                    onClick={() =>
                      void snapAllZonesToGrid()
                    }
                    disabled={busy}
                  >
                    Привязать все зоны
                  </button>
                </div>
              </div>
            </section>
          </aside>

          <section className="seating-main">
            <div className="panel candy-panel">
              <div className="seating-toolbar">
                <div className="seating-tabs">
                  <TabButton
                    active={tab === "layout"}
                    onClick={() =>
                      setTab("layout")
                    }
                  >
                    Карта
                  </TabButton>
                  <TabButton
                    active={tab === "zones"}
                    onClick={() =>
                      setTab("zones")
                    }
                  >
                    Зоны
                  </TabButton>
                  <TabButton
                    active={tab === "authors"}
                    onClick={() =>
                      setTab("authors")
                    }
                  >
                    Список авторов
                  </TabButton>
                </div>

                <div className="muted compact">
                  Главный сценарий: выбрать
                  вендора слева → нажать или
                  перетащить на стол.
                </div>
              </div>

              {tab === "layout" && (
                <LayoutCanvas
                  data={data}
                  assignmentsByTable={
                    assignmentsByTable
                  }
                  zoneMap={zoneMap}
                  canEdit={canEdit}
                  canAssign={canAssign}
                  onAssign={handleAssign}
                  onUnassign={handleUnassign}
                  onMoveTable={moveTable}
                  onEditTable={(table) =>
                    setEditingTable(table)
                  }
                  movingTableId={movingTableId}
                  selectedBookingId={
                    selectedBookingId
                  }
                  onSelectBooking={
                    setSelectedBookingId
                  }
                />
              )}

              {tab === "zones" && (
                <ZoneManagementTab
                  zones={data?.zones || []}
                  selectedZone={selectedZone}
                  selectedZoneId={
                    selectedZoneId
                  }
                  setSelectedZoneId={
                    setSelectedZoneId
                  }
                  canEdit={canEdit}
                  busy={busy}
                  snapMode={snapMode}
                  gridSize={gridSize}
                  onCreate={async (payload) => {
                    try {
                      setBusy(true);
                      const zone =
                        (await api.createSeatingZone(
                          payload,
                        )) as LayoutZoneRecord;
                      setSelectedZoneId(zone.id);
                      await reload();
                    } catch (err) {
                      setError(errorText(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                  onUpdate={async (
                    zoneId,
                    payload,
                  ) => {
                    try {
                      setBusy(true);
                      await api.updateSeatingZone(
                        zoneId,
                        payload,
                      );
                      await reload();
                    } catch (err) {
                      setError(errorText(err));
                    } finally {
                      setBusy(false);
                    }
                  }}
                  onMoveZone={moveZone}
                  movingZoneId={movingZoneId}
                />
              )}

              {tab === "authors" && (
                <AuthorsPreview
                  groups={
                    data?.authors_groups || []
                  }
                />
              )}
            </div>
          </section>
        </div>
      )}

      {editingTable && (
        <TableEditModal
          table={editingTable}
          zones={data?.zones || []}
          onClose={() => setEditingTable(null)}
          onSave={async (payload) => {
            try {
              setBusy(true);
              await api.updateSeatingTable(
                editingTable.id,
                payload,
              );
              setEditingTable(null);
              await reload();
            } catch (err) {
              setError(errorText(err));
            } finally {
              setBusy(false);
            }
          }}
          busy={busy}
        />
      )}

      {showTableModal && (
        <TableSettingsModal
          preset={tablePreset}
          zones={data?.zones || []}
          onClose={() =>
            setShowTableModal(false)
          }
          onSave={(next) => {
            setTablePreset(next);
            setShowTableModal(false);
          }}
        />
      )}
    </>
  );
}

function BookingPickerPanel({
  bookings,
  query,
  onQueryChange,
  filter,
  onFilterChange,
  selectedBookingId,
  onSelect,
  assignmentByBookingId,
  tableMap,
  onUnassign,
}: {
  bookings: BookingRecord[];
  query: string;
  onQueryChange: (value: string) => void;
  filter: BookingFilter;
  onFilterChange: (value: BookingFilter) => void;
  selectedBookingId: string | null;
  onSelect: (bookingId: string) => void;
  assignmentByBookingId: Map<
    string,
    TableAssignmentRecord
  >;
  tableMap: Map<string, LayoutTableRecord>;
  onUnassign: (bookingId: string) => Promise<void>;
}) {
  return (
    <section className="panel candy-panel vendor-picker-panel">
      <div className="panel-heading">
        <div>
          <h2>Выбор вендора / автора</h2>
          <p className="muted compact">
            Поиск по вендору, нику, ФИО и коду заявки.
          </p>
        </div>
      </div>

      <div className="booking-filter-toggle">
        <button
          type="button"
          className={
            filter === "UNASSIGNED"
              ? "filter-chip active"
              : "filter-chip"
          }
          onClick={() => onFilterChange("UNASSIGNED")}
        >
          Не размещены
        </button>
        <button
          type="button"
          className={
            filter === "ASSIGNED"
              ? "filter-chip active"
              : "filter-chip"
          }
          onClick={() => onFilterChange("ASSIGNED")}
        >
          Размещены
        </button>
        <button
          type="button"
          className={
            filter === "ALL"
              ? "filter-chip active"
              : "filter-chip"
          }
          onClick={() => onFilterChange("ALL")}
        >
          Все
        </button>
      </div>

      <div className="booking-search-box">
        <input
          placeholder="Вендор, ник, ФИО или BKG-..."
          value={query}
          onChange={(event) =>
            onQueryChange(event.target.value)
          }
        />
      </div>

      <div className="booking-picker-list">
        {bookings.slice(0, 40).map((booking) => {
          const assignment =
            assignmentByBookingId.get(
              booking.id,
            ) || null;
          const table =
            assignment &&
            tableMap.get(assignment.table_id);
          const selected =
            booking.id === selectedBookingId;

          return (
            <div
              key={booking.id}
              className={
                selected
                  ? "picker-item-wrap active"
                  : "picker-item-wrap"
              }
            >
              <button
                type="button"
                className="picker-item"
                onClick={() =>
                  onSelect(booking.id)
                }
              >
                <div className="picker-main">
                  <strong>
                    {bookingDisplayName(booking)}
                  </strong>
                  <span>
                    {booking.code} ·{" "}
                    {booking.booking_type} ·{" "}
                    {booking.payment_status}
                  </span>
                  <small>
                    {assignment && table
                      ? `Стол ${table.table_label}${assignment.slot_count === 1 ? (assignment.start_slot === 1 ? "A" : "B") : ""}`
                      : "Не размещён"}
                  </small>
                </div>

                <span
                  className={
                    assignment
                      ? "status active"
                      : "status"
                  }
                >
                  {assignment
                    ? "assigned"
                    : "open"}
                </span>
              </button>

              {selected && (
                <div className="picker-expanded">
                  <div className="picker-expanded-grid">
                    <InfoLine
                      label="Заявка"
                      value={booking.booking_status}
                    />
                    <InfoLine
                      label="Оплата"
                      value={booking.payment_status}
                    />
                    <InfoLine
                      label="Участников"
                      value={String(
                        booking.participants_count,
                      )}
                    />
                    <InfoLine
                      label="Сумма"
                      value={formatMoney(
                        booking.final_total,
                      )}
                    />
                  </div>

                  <div className="picker-authors">
                    <strong>Авторы / участники</strong>
                    <span>
                      {bookingParticipantsSummary(
                        booking,
                      )}
                    </span>
                  </div>

                  <div className="picker-hint">
                    {assignment && table
                      ? `Сейчас: стол ${table.table_label}${assignment.slot_count === 1 ? (assignment.start_slot === 1 ? "A" : "B") : ""}. Кликните по другой ячейке карты, чтобы перенести.`
                      : "Кликните по A/B на карте или перетащите карточку на нужный стол."}
                  </div>

                  {assignment && (
                    <button
                      className="button secondary small"
                      type="button"
                      onClick={() =>
                        void onUnassign(
                          booking.id,
                        )
                      }
                    >
                      Снять со стола
                    </button>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {bookings.length === 0 && (
          <div className="empty-state">
            Ничего не найдено.
          </div>
        )}
      </div>
    </section>
  );
}

function InfoLine({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="picker-info-line">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TableQuickCreatePanel({
  busy,
  preset,
  zones,
  quickTableCount,
  setQuickTableCount,
  onQuickAddOne,
  onQuickAddFive,
  onQuickAddN,
  onOpenSettings,
}: {
  busy: boolean;
  preset: TablePreset;
  zones: LayoutZoneRecord[];
  quickTableCount: string;
  setQuickTableCount: (value: string) => void;
  onQuickAddOne: () => void;
  onQuickAddFive: () => void;
  onQuickAddN: () => void;
  onOpenSettings: () => void;
}) {
  const currentZone =
    zones.find((item) => item.id === preset.zoneId) ||
    null;

  return (
    <section className="panel candy-panel">
      <div className="panel-heading">
        <div>
          <h2>Столы</h2>
          <p className="muted compact">
            Быстрое добавление с автонумерацией
            и авторасстановкой.
          </p>
        </div>
      </div>

      <div className="table-quick-summary">
        <span>
          Зона:{" "}
          <strong>
            {currentZone?.zone_name ||
              "Без зоны"}
          </strong>
        </span>
        <span>
          Размер:{" "}
          <strong>
            {preset.width} × {preset.height}
          </strong>
        </span>
        <span>
          Слоты:{" "}
          <strong>
            {preset.capacitySlots}
          </strong>
        </span>
      </div>

      <div className="quick-table-actions">
        <button
          className="button secondary"
          type="button"
          onClick={onQuickAddOne}
          disabled={busy}
        >
          +1 стол
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={onQuickAddFive}
          disabled={busy}
        >
          +5 столов
        </button>
      </div>

      <div className="inline-form">
        <input
          value={quickTableCount}
          onChange={(event) =>
            setQuickTableCount(
              event.target.value,
            )
          }
          inputMode="numeric"
        />
        <button
          className="button secondary"
          type="button"
          onClick={onQuickAddN}
          disabled={busy}
        >
          +N столов
        </button>
      </div>

      <button
        className="button secondary full"
        type="button"
        onClick={onOpenSettings}
      >
        Параметры создания столов
      </button>
    </section>
  );
}

function LayoutCanvas({
  data,
  assignmentsByTable,
  zoneMap,
  canEdit,
  canAssign,
  onAssign,
  onUnassign,
  onMoveTable,
  onEditTable,
  movingTableId,
  selectedBookingId,
  onSelectBooking,
}: {
  data: SeatingOverview | null;
  assignmentsByTable: Map<
    string,
    TableAssignmentRecord[]
  >;
  zoneMap: Map<string, LayoutZoneRecord>;
  canEdit: boolean;
  canAssign: boolean;
  onAssign: (
    bookingId: string,
    tableId: string,
    startSlot: number,
  ) => Promise<void>;
  onUnassign: (
    bookingId: string,
  ) => Promise<void>;
  onMoveTable: (
    table: LayoutTableRecord,
    nextX: number,
    nextY: number,
  ) => Promise<void>;
  onEditTable: (
    table: LayoutTableRecord,
  ) => void;
  movingTableId: string | null;
  selectedBookingId: string | null;
  onSelectBooking: (
    bookingId: string | null,
  ) => void;
}) {
  const stageRef = useRef<HTMLDivElement | null>(
    null,
  );
  const dragRef = useRef<{
    table: LayoutTableRecord;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  useEffect(() => {
    function move(event: MouseEvent) {
      if (!dragRef.current || !stageRef.current)
        return;
      const stage =
        stageRef.current.getBoundingClientRect();
      const nextX = Math.max(
        0,
        Math.round(
          event.clientX -
            stage.left -
            dragRef.current.offsetX,
        ),
      );
      const nextY = Math.max(
        0,
        Math.round(
          event.clientY -
            stage.top -
            dragRef.current.offsetY,
        ),
      );
      const el = document.querySelector(
        `[data-table-id="${dragRef.current.table.id}"]`,
      ) as HTMLElement | null;
      if (el) {
        el.style.left = `${nextX}px`;
        el.style.top = `${nextY}px`;
      }
    }

    async function up(event: MouseEvent) {
      if (!dragRef.current || !stageRef.current)
        return;
      const stage =
        stageRef.current.getBoundingClientRect();
      const nextX = Math.max(
        0,
        Math.round(
          event.clientX -
            stage.left -
            dragRef.current.offsetX,
        ),
      );
      const nextY = Math.max(
        0,
        Math.round(
          event.clientY -
            stage.top -
            dragRef.current.offsetY,
        ),
      );
      const table = dragRef.current.table;
      dragRef.current = null;
      await onMoveTable(table, nextX, nextY);
    }

    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener(
        "mousemove",
        move,
      );
      window.removeEventListener("mouseup", up);
    };
  }, [onMoveTable]);

  return (
    <div className="seating-layout-wrap">
      <div className="seating-layout-legend">
        <span>
          🍓 FULL — занимает весь стол
        </span>
        <span>
          💗 HALF — размещается в A или B
        </span>
      </div>

      <div
        className="seating-stage"
        ref={stageRef}
      >
        {(data?.zones || []).map((zone) => (
          <div
            className="layout-zone"
            key={zone.id}
            style={{
              left: zone.x,
              top: zone.y,
              width: zone.width,
              height: zone.height,
              borderColor:
                zone.color || "#cbd4ff",
              background:
                zone.color
                  ? `${zone.color}26`
                  : undefined,
            }}
          >
            <strong>{zone.zone_name}</strong>
            <span>{zone.zone_type}</span>
          </div>
        ))}

        {(data?.tables || []).map((table) => {
          const assignments =
            assignmentsByTable.get(table.id) || [];
          const slotA =
            assignments.find(
              (item) => item.start_slot === 1,
            ) || null;
          const slotB =
            assignments.find(
              (item) =>
                item.start_slot === 2 ||
                (item.start_slot === 1 &&
                  item.slot_count === 2),
            ) || null;

          return (
            <div
              className={
                movingTableId === table.id
                  ? "layout-table moving"
                  : "layout-table"
              }
              data-table-id={table.id}
              key={table.id}
              style={{
                left: table.x,
                top: table.y,
                width: table.width,
                height: table.height,
              }}
            >
              <div
                className="layout-table-head"
                onMouseDown={(event) => {
                  if (!canEdit || !stageRef.current)
                    return;
                  const target = event.target as HTMLElement;
                  if (
                    target.closest(
                      ".layout-table-edit",
                    )
                  ) {
                    return;
                  }

                  const rect = (
                    event.currentTarget
                      .parentElement as HTMLElement
                  ).getBoundingClientRect();
                  dragRef.current = {
                    table,
                    offsetX:
                      event.clientX - rect.left,
                    offsetY:
                      event.clientY - rect.top,
                  };
                }}
                title={
                  canEdit
                    ? `${table.table_label} · тащите для перемещения`
                    : table.table_label
                }
              >
                <span className="layout-table-number">
                  {table.table_label}
                </span>

                <span
                  className="layout-table-zone-dot"
                  title={
                    zoneMap.get(
                      table.zone_id || "",
                    )?.zone_name || "Без зоны"
                  }
                />

                {canEdit && (
                  <button
                    type="button"
                    className="layout-table-edit"
                    onMouseDown={(event) =>
                      event.stopPropagation()
                    }
                    onClick={(event) => {
                      event.stopPropagation();
                      onEditTable(table);
                    }}
                    title="Редактировать стол"
                  >
                    ✎
                  </button>
                )}
              </div>

              {table.capacity_slots === 1 ? (
                <DropSlot
                  label="место"
                  booking={
                    assignments[0]?.booking || null
                  }
                  occupiedByFull={
                    assignments[0]?.slot_count === 2
                  }
                  canAssign={canAssign}
                  selectedBookingId={
                    selectedBookingId
                  }
                  onDropBooking={async (
                    bookingId,
                  ) => {
                    await onAssign(
                      bookingId,
                      table.id,
                      1,
                    );
                  }}
                  onClickSlot={async () => {
                    if (selectedBookingId) {
                      await onAssign(
                        selectedBookingId,
                        table.id,
                        1,
                      );
                    }
                  }}
                  onUnassign={async () => {
                    if (assignments[0]) {
                      await onUnassign(
                        assignments[0].booking_id,
                      );
                    }
                  }}
                  onSelectBooking={
                    onSelectBooking
                  }
                />
              ) : (
                <div className="layout-slot-row">
                  <DropSlot
                    label="A"
                    booking={slotA?.booking || null}
                    occupiedByFull={
                      slotA?.slot_count === 2
                    }
                    canAssign={canAssign}
                    selectedBookingId={
                      selectedBookingId
                    }
                    onDropBooking={async (
                      bookingId,
                    ) => {
                      await onAssign(
                        bookingId,
                        table.id,
                        1,
                      );
                    }}
                    onClickSlot={async () => {
                      if (selectedBookingId) {
                        await onAssign(
                          selectedBookingId,
                          table.id,
                          1,
                        );
                      }
                    }}
                    onUnassign={async () => {
                      if (slotA) {
                        await onUnassign(
                          slotA.booking_id,
                        );
                      }
                    }}
                    onSelectBooking={
                      onSelectBooking
                    }
                  />
                  <DropSlot
                    label="B"
                    booking={
                      slotA?.slot_count === 2
                        ? slotA.booking
                        : slotB?.booking || null
                    }
                    occupiedByFull={
                      slotA?.slot_count === 2
                    }
                    canAssign={canAssign}
                    selectedBookingId={
                      selectedBookingId
                    }
                    onDropBooking={async (
                      bookingId,
                    ) => {
                      await onAssign(
                        bookingId,
                        table.id,
                        2,
                      );
                    }}
                    onClickSlot={async () => {
                      if (selectedBookingId) {
                        await onAssign(
                          selectedBookingId,
                          table.id,
                          2,
                        );
                      }
                    }}
                    onUnassign={async () => {
                      if (
                        slotA?.slot_count === 2
                      ) {
                        await onUnassign(
                          slotA.booking_id,
                        );
                      } else if (slotB) {
                        await onUnassign(
                          slotB.booking_id,
                        );
                      }
                    }}
                    onSelectBooking={
                      onSelectBooking
                    }
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DropSlot({
  label,
  booking,
  occupiedByFull,
  canAssign,
  selectedBookingId,
  onDropBooking,
  onClickSlot,
  onUnassign,
  onSelectBooking,
}: {
  label: string;
  booking: BookingRecord | null;
  occupiedByFull: boolean;
  canAssign: boolean;
  selectedBookingId: string | null;
  onDropBooking: (
    bookingId: string,
  ) => Promise<void>;
  onClickSlot: () => Promise<void>;
  onUnassign: () => Promise<void>;
  onSelectBooking: (
    bookingId: string | null,
  ) => void;
}) {
  const selected =
    booking && booking.id === selectedBookingId;

  return (
    <button
      type="button"
      className={
        occupiedByFull
          ? "layout-slot full"
          : "layout-slot"
      }
      onClick={() => {
        if (selectedBookingId && canAssign) {
          void onClickSlot();
        } else if (booking) {
          onSelectBooking(booking.id);
        }
      }}
      onDragOver={(event) => {
        if (canAssign)
          event.preventDefault();
      }}
      onDrop={async (event) => {
        if (!canAssign) return;
        event.preventDefault();
        const raw =
          event.dataTransfer.getData(
            "application/json",
          );
        if (!raw) return;
        const payload = JSON.parse(
          raw,
        ) as DragPayload;
        await onDropBooking(payload.bookingId);
      }}
    >
      <div className="layout-slot-label">
        {label}
      </div>

      {!booking ? (
        <div className="layout-slot-empty">
          {selectedBookingId
            ? "нажмите для размещения"
            : "свободно"}
        </div>
      ) : (
        <div
          className={
            booking.booking_type === "FULL"
              ? selected
                ? "slot-booking full selected"
                : "slot-booking full"
              : selected
                ? "slot-booking selected"
                : "slot-booking"
          }
          draggable
          onDragStart={(event) => {
            event.dataTransfer.setData(
              "application/json",
              JSON.stringify({
                bookingId: booking.id,
              } satisfies DragPayload),
            );
            onSelectBooking(booking.id);
          }}
        >
          <div>
            <strong>
              {bookingDisplayName(booking)}
            </strong>
            <span>
              {booking.code} ·{" "}
              {booking.booking_type}
            </span>
          </div>
          <button
            type="button"
            className="icon-button slot-remove"
            onClick={(event) => {
              event.stopPropagation();
              void onUnassign();
            }}
            title="Снять со стола"
          >
            ×
          </button>
        </div>
      )}
    </button>
  );
}

function ZoneManagementTab({
  zones,
  selectedZone,
  selectedZoneId,
  setSelectedZoneId,
  canEdit,
  busy,
  snapMode,
  gridSize,
  onCreate,
  onUpdate,
  onMoveZone,
  movingZoneId,
}: {
  zones: LayoutZoneRecord[];
  selectedZone: LayoutZoneRecord | null;
  selectedZoneId: string | null;
  setSelectedZoneId: (value: string | null) => void;
  canEdit: boolean;
  busy: boolean;
  snapMode: boolean;
  gridSize: number;
  onCreate: (payload: object) => Promise<void>;
  onUpdate: (
    zoneId: string,
    payload: object,
  ) => Promise<void>;
  onMoveZone: (
    zone: LayoutZoneRecord,
    nextX: number,
    nextY: number,
  ) => Promise<void>;
  movingZoneId: string | null;
}) {
  const stageRef = useRef<HTMLDivElement | null>(
    null,
  );
  const dragRef = useRef<{
    zone: LayoutZoneRecord;
    offsetX: number;
    offsetY: number;
  } | null>(null);

  useEffect(() => {
    function move(event: MouseEvent) {
      if (!dragRef.current || !stageRef.current)
        return;
      const stage =
        stageRef.current.getBoundingClientRect();
      const nextX = Math.max(
        0,
        Math.round(
          event.clientX -
            stage.left -
            dragRef.current.offsetX,
        ),
      );
      const nextY = Math.max(
        0,
        Math.round(
          event.clientY -
            stage.top -
            dragRef.current.offsetY,
        ),
      );
      const el = document.querySelector(
        `[data-zone-id="${dragRef.current.zone.id}"]`,
      ) as HTMLElement | null;
      if (el) {
        el.style.left = `${nextX}px`;
        el.style.top = `${nextY}px`;
      }
    }

    async function up(event: MouseEvent) {
      if (!dragRef.current || !stageRef.current)
        return;
      const stage =
        stageRef.current.getBoundingClientRect();
      const nextX = Math.max(
        0,
        Math.round(
          event.clientX -
            stage.left -
            dragRef.current.offsetX,
        ),
      );
      const nextY = Math.max(
        0,
        Math.round(
          event.clientY -
            stage.top -
            dragRef.current.offsetY,
        ),
      );
      const zone = dragRef.current.zone;
      dragRef.current = null;
      await onMoveZone(zone, nextX, nextY);
    }

    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener(
        "mousemove",
        move,
      );
      window.removeEventListener("mouseup", up);
    };
  }, [onMoveZone]);

  return (
    <div className="zone-manager-grid">
      <section className="zone-manager-side">
        {canEdit && (
          <section className="panel zone-editor-panel">
            <div className="panel-heading">
              <div>
                <h2>Создать зону</h2>
                <p className="muted compact">
                  Параметры создания вынесены
                  отдельно от карты.
                </p>
              </div>
            </div>

            <form
              className="stack"
              onSubmit={async (
                event: FormEvent<HTMLFormElement>,
              ) => {
                event.preventDefault();
                const data = new FormData(
                  event.currentTarget,
                );
                await onCreate({
                  zone_name: text(
                    data,
                    "zone_name",
                  ),
                  zone_type: text(
                    data,
                    "zone_type",
                  ),
                  color: text(data, "color"),
                  x: Number(text(data, "x")),
                  y: Number(text(data, "y")),
                  width: Number(
                    text(data, "width"),
                  ),
                  height: Number(
                    text(data, "height"),
                  ),
                });
                event.currentTarget.reset();
              }}
            >
              <label>
                <span>Название</span>
                <input
                  name="zone_name"
                  placeholder="Зона настолок"
                  required
                />
              </label>

              <div className="form-grid two">
                <label>
                  <span>Тип</span>
                  <input
                    name="zone_type"
                    defaultValue="SPECIAL"
                  />
                </label>
                <label>
                  <span>Цвет</span>
                  <input
                    name="color"
                    defaultValue="#B8C5FF"
                  />
                </label>
                <label>
                  <span>X</span>
                  <input
                    name="x"
                    type="number"
                    defaultValue="24"
                  />
                </label>
                <label>
                  <span>Y</span>
                  <input
                    name="y"
                    type="number"
                    defaultValue="24"
                  />
                </label>
                <label>
                  <span>Ширина</span>
                  <input
                    name="width"
                    type="number"
                    defaultValue="280"
                  />
                </label>
                <label>
                  <span>Высота</span>
                  <input
                    name="height"
                    type="number"
                    defaultValue="160"
                  />
                </label>
              </div>

              <button
                className="button secondary full"
                type="submit"
                disabled={busy}
              >
                + Зона
              </button>
            </form>
          </section>
        )}

        <section className="panel zone-editor-panel">
          <div className="panel-heading">
            <div>
              <h2>Список зон</h2>
              <p className="muted compact">
                Выберите зону для
                редактирования.
              </p>
            </div>
          </div>

          <div className="zone-list">
            {zones.map((zone) => (
              <button
                type="button"
                className={
                  zone.id === selectedZoneId
                    ? "zone-list-item active"
                    : "zone-list-item"
                }
                key={zone.id}
                onClick={() =>
                  setSelectedZoneId(zone.id)
                }
              >
                <strong>{zone.zone_name}</strong>
                <span>
                  {zone.zone_type} · {zone.width} ×{" "}
                  {zone.height}
                </span>
              </button>
            ))}
          </div>
        </section>

        {selectedZone && canEdit && (
          <section className="panel zone-editor-panel">
            <div className="panel-heading">
              <div>
                <h2>Редактирование зоны</h2>
                <p className="muted compact">
                  Можно двигать на карте и
                  править координаты вручную.
                </p>
              </div>
            </div>

            <form
              className="stack"
              onSubmit={async (
                event: FormEvent<HTMLFormElement>,
              ) => {
                event.preventDefault();
                const data = new FormData(
                  event.currentTarget,
                );
                await onUpdate(selectedZone.id, {
                  zone_name: text(
                    data,
                    "zone_name",
                  ),
                  zone_type: text(
                    data,
                    "zone_type",
                  ),
                  color: text(data, "color"),
                  x: Number(text(data, "x")),
                  y: Number(text(data, "y")),
                  width: Number(
                    text(data, "width"),
                  ),
                  height: Number(
                    text(data, "height"),
                  ),
                });
              }}
            >
              <label>
                <span>Название</span>
                <input
                  name="zone_name"
                  defaultValue={
                    selectedZone.zone_name
                  }
                  required
                />
              </label>

              <div className="form-grid two">
                <label>
                  <span>Тип</span>
                  <input
                    name="zone_type"
                    defaultValue={
                      selectedZone.zone_type
                    }
                  />
                </label>
                <label>
                  <span>Цвет</span>
                  <input
                    name="color"
                    defaultValue={
                      selectedZone.color || ""
                    }
                  />
                </label>
                <label>
                  <span>X</span>
                  <input
                    name="x"
                    type="number"
                    defaultValue={selectedZone.x}
                  />
                </label>
                <label>
                  <span>Y</span>
                  <input
                    name="y"
                    type="number"
                    defaultValue={selectedZone.y}
                  />
                </label>
                <label>
                  <span>Ширина</span>
                  <input
                    name="width"
                    type="number"
                    defaultValue={
                      selectedZone.width
                    }
                  />
                </label>
                <label>
                  <span>Высота</span>
                  <input
                    name="height"
                    type="number"
                    defaultValue={
                      selectedZone.height
                    }
                  />
                </label>
              </div>

              <button
                className="button secondary full"
                type="submit"
                disabled={busy}
              >
                Сохранить зону
              </button>
            </form>
          </section>
        )}
      </section>

      <section className="panel candy-panel zone-canvas-panel">
        <div className="panel-heading">
          <div>
            <h2>Карта зон</h2>
            <p className="muted compact">
              Режим:{" "}
              {snapMode
                ? `сетка ${gridSize}px`
                : "свободное перемещение"}
              .
            </p>
          </div>
        </div>

        <div
          className="zone-stage"
          ref={stageRef}
        >
          {zones.map((zone) => (
            <button
              type="button"
              key={zone.id}
              data-zone-id={zone.id}
              className={
                zone.id === selectedZoneId
                  ? movingZoneId === zone.id
                    ? "zone-box selected moving"
                    : "zone-box selected"
                  : movingZoneId === zone.id
                    ? "zone-box moving"
                    : "zone-box"
              }
              style={{
                left: zone.x,
                top: zone.y,
                width: zone.width,
                height: zone.height,
                borderColor:
                  zone.color || "#cbd4ff",
                background:
                  zone.color
                    ? `${zone.color}28`
                    : undefined,
              }}
              onClick={() =>
                setSelectedZoneId(zone.id)
              }
              onMouseDown={(event) => {
                if (!canEdit) return;
                const rect = (
                  event.currentTarget as HTMLElement
                ).getBoundingClientRect();
                dragRef.current = {
                  zone,
                  offsetX:
                    event.clientX - rect.left,
                  offsetY:
                    event.clientY - rect.top,
                };
              }}
            >
              <strong>{zone.zone_name}</strong>
              <span>{zone.zone_type}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

function AuthorsPreview({
  groups,
}: {
  groups: SeatingOverview["authors_groups"];
}) {
  return (
    <div className="authors-board">
      {(groups || []).map((group) => (
        <section
          className="authors-card"
          key={group.title}
        >
          <h3>{group.title}</h3>
          <div className="authors-items">
            {group.items.map((item) => (
              <div
                className="authors-item"
                key={`${group.title}-${item.label}`}
              >
                <strong>
                  {item.label}.
                </strong>
                <span>{item.vendor_name}</span>
              </div>
            ))}
          </div>
        </section>
      ))}

      {(groups || []).length === 0 && (
        <div className="empty-state">
          Пока нет рассаженных авторов.
        </div>
      )}
    </div>
  );
}

function TableEditModal({
  table,
  zones,
  onClose,
  onSave,
  busy,
}: {
  table: LayoutTableRecord;
  zones: LayoutZoneRecord[];
  onClose: () => void;
  onSave: (payload: object) => Promise<void>;
  busy: boolean;
}) {
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <div>
            <div className="eyebrow">
              Table editor
            </div>
            <h2>
              Стол {table.table_label}
            </h2>
          </div>

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
            const data = new FormData(
              event.currentTarget,
            );

            await onSave({
              table_label: text(
                data,
                "table_label",
              ),
              zone_id:
                text(data, "zone_id") || null,
              capacity_slots: Number(
                text(data, "capacity_slots"),
              ),
              x: Number(text(data, "x")),
              y: Number(text(data, "y")),
              width: Number(
                text(data, "width"),
              ),
              height: Number(
                text(data, "height"),
              ),
              notes:
                text(data, "notes") || null,
            });
          }}
        >
          <div className="form-grid two">
            <label>
              <span>Подпись стола</span>
              <input
                name="table_label"
                defaultValue={
                  table.table_label
                }
                required
              />
            </label>

            <label>
              <span>Зона</span>
              <select
                name="zone_id"
                defaultValue={
                  table.zone_id || ""
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
            </label>

            <label>
              <span>Слоты</span>
              <select
                name="capacity_slots"
                defaultValue={String(
                  table.capacity_slots,
                )}
              >
                <option value="2">
                  A / B
                </option>
                <option value="1">
                  Один
                </option>
              </select>
            </label>

            <label>
              <span>X</span>
              <input
                name="x"
                type="number"
                defaultValue={table.x}
              />
            </label>

            <label>
              <span>Y</span>
              <input
                name="y"
                type="number"
                defaultValue={table.y}
              />
            </label>

            <label>
              <span>Ширина</span>
              <input
                name="width"
                type="number"
                min="80"
                defaultValue={table.width}
              />
            </label>

            <label>
              <span>Высота</span>
              <input
                name="height"
                type="number"
                min="48"
                defaultValue={table.height}
              />
            </label>
          </div>

          <label>
            <span>Комментарий</span>
            <textarea
              name="notes"
              rows={3}
              defaultValue={
                table.notes || ""
              }
            />
          </label>

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

function TableSettingsModal({
  preset,
  zones,
  onClose,
  onSave,
}: {
  preset: TablePreset;
  zones: LayoutZoneRecord[];
  onClose: () => void;
  onSave: (next: TablePreset) => void;
}) {
  const [draft, setDraft] =
    useState<TablePreset>(preset);

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <div>
            <div className="eyebrow">
              Seating preset
            </div>
            <h2>Параметры создания столов</h2>
          </div>

          <button
            type="button"
            className="icon-button"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="form-grid two">
          <label>
            <span>Зона</span>
            <select
              value={draft.zoneId}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  zoneId:
                    event.target.value,
                }))
              }
            >
              <option value="">
                Без зоны
              </option>
              {zones.map((zone) => (
                <option
                  value={zone.id}
                  key={zone.id}
                >
                  {zone.zone_name}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Префикс</span>
            <input
              value={draft.numberingPrefix}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  numberingPrefix:
                    event.target.value,
                }))
              }
            />
          </label>

          <label>
            <span>Колонок</span>
            <input
              type="number"
              value={draft.columns}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  columns: Math.max(
                    1,
                    Number(
                      event.target.value,
                    ) || 1,
                  ),
                }))
              }
            />
          </label>

          <label>
            <span>Слоты</span>
            <select
              value={draft.capacitySlots}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  capacitySlots: Number(
                    event.target.value,
                  ),
                }))
              }
            >
              <option value="2">
                2 слота (A/B)
              </option>
              <option value="1">
                1 слот
              </option>
            </select>
          </label>

          <label>
            <span>Начальный X</span>
            <input
              type="number"
              value={draft.startX}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  startX: Number(
                    event.target.value,
                  ) || 0,
                }))
              }
            />
          </label>

          <label>
            <span>Начальный Y</span>
            <input
              type="number"
              value={draft.startY}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  startY: Number(
                    event.target.value,
                  ) || 0,
                }))
              }
            />
          </label>

          <label>
            <span>Ширина стола</span>
            <input
              type="number"
              value={draft.width}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  width: Math.max(
                    80,
                    Number(
                      event.target.value,
                    ) || 80,
                  ),
                }))
              }
            />
          </label>

          <label>
            <span>Высота стола</span>
            <input
              type="number"
              value={draft.height}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  height: Math.max(
                    46,
                    Number(
                      event.target.value,
                    ) || 46,
                  ),
                }))
              }
            />
          </label>

          <label>
            <span>Шаг X</span>
            <input
              type="number"
              value={draft.xGap}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  xGap: Math.max(
                    0,
                    Number(
                      event.target.value,
                    ) || 0,
                  ),
                }))
              }
            />
          </label>

          <label>
            <span>Шаг Y</span>
            <input
              type="number"
              value={draft.yGap}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  yGap: Math.max(
                    0,
                    Number(
                      event.target.value,
                    ) || 0,
                  ),
                }))
              }
            />
          </label>
        </div>

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
            type="button"
            onClick={() => onSave(draft)}
          >
            Сохранить
          </button>
        </div>
      </div>
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
  children: string;
}) {
  return (
    <button
      type="button"
      className={
        active
          ? "application-tab active"
          : "application-tab"
      }
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="public-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function normalizePoint(
  x: number,
  y: number,
  snap: boolean,
  gridSize: number,
): [number, number] {
  if (!snap) return [x, y];
  return [
    Math.round(x / gridSize) * gridSize,
    Math.round(y / gridSize) * gridSize,
  ];
}

function bookingDisplayName(
  booking: BookingRecord,
) {
  return (
    booking.vendor?.vendor_name ||
    booking.vendor_name ||
    booking.code
  );
}

function bookingSearchText(
  booking: BookingRecord,
) {
  const participantText = (
    booking.participants || []
  )
    .map(participantSearchText)
    .join(" ");

  return [
    booking.code,
    booking.vendor?.vendor_name,
    booking.vendor_name,
    participantText,
  ]
    .filter(Boolean)
    .join(" ");
}

function participantSearchText(
  item: BookingParticipantRecord,
) {
  const participant = item.participant;
  return [
    participant.nickname,
    participant.first_name,
    participant.last_name,
    participant.middle_name,
  ]
    .filter(Boolean)
    .join(" ");
}

function bookingParticipantsSummary(
  booking: BookingRecord,
) {
  const participants =
    booking.participants || [];

  if (!participants.length) {
    return "Участники не указаны";
  }

  return participants
    .map((item) => {
      const person = item.participant;
      const name = [
        person.nickname
          ? `@${person.nickname}`
          : null,
        person.first_name,
        person.last_name,
      ]
        .filter(Boolean)
        .join(" ");

      return `${item.role}: ${name}`;
    })
    .join(" · ");
}

function formatMoney(value: number) {
  return Number(value || 0).toLocaleString(
    "ru-RU",
    {
      maximumFractionDigits: 2,
    },
  );
}

function text(data: FormData, key: string) {
  return String(data.get(key) || "").trim();
}

function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}

function readTablePreset(): TablePreset {
  try {
    const raw =
      window.localStorage.getItem(
        TABLE_PRESET_STORAGE_KEY,
      );
    if (!raw) return DEFAULT_TABLE_PRESET;
    const parsed = JSON.parse(raw) as Partial<TablePreset>;
    return {
      ...DEFAULT_TABLE_PRESET,
      ...parsed,
    };
  } catch {
    return DEFAULT_TABLE_PRESET;
  }
}

function persistTablePreset(
  preset: TablePreset,
) {
  try {
    window.localStorage.setItem(
      TABLE_PRESET_STORAGE_KEY,
      JSON.stringify(preset),
    );
  } catch {
    // ignore storage errors
  }
}
