import {
  FormEvent,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "./api";
import type {
  EventRecord,
  ReportData,
} from "./types";


type ReportName =
  | "vendors"
  | "participants"
  | "seating"
  | "finance"
  | "checkin";


const reportTabs: {
  name: ReportName;
  label: string;
}[] = [
  {
    name: "vendors",
    label: "Вендоры",
  },
  {
    name: "participants",
    label: "Участники",
  },
  {
    name: "seating",
    label: "Рассадка",
  },
  {
    name: "finance",
    label: "Финансы",
  },
  {
    name: "checkin",
    label: "Check-in",
  },
];


export default function ReportsPage({
  currentEvent,
}: {
  currentEvent: EventRecord | null;
}) {
  const [reportName, setReportName] =
    useState<ReportName>("vendors");
  const [data, setData] =
    useState<ReportData | null>(null);
  const [query, setQuery] =
    useState("");
  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  async function reload(
    name = reportName,
  ) {
    if (!currentEvent) {
      setData(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setData(
        await api.report(
          name,
          currentEvent.id,
        ),
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload(reportName);
  }, [
    currentEvent?.id,
    reportName,
  ]);

  const filteredRows = useMemo(() => {
    const rows = data?.rows || [];
    const needle =
      query.trim().toLowerCase();

    if (!needle) return rows;

    return rows.filter((row) =>
      Object.values(row)
        .map((value) =>
          String(value ?? ""),
        )
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [data, query]);

  return (
    <>
      <header className="page-header">
        <div>
          <div className="eyebrow">
            Analytics · Step 6
          </div>
          <h1>Отчёты</h1>
          <p className="muted header-subtitle">
            Те же основные срезы, что были в
            Google Sheets, но напрямую из
            PostgreSQL.
          </p>
        </div>

        {data && (
          <button
            className="button primary"
            type="button"
            onClick={() =>
              exportCsv(
                data,
                filteredRows,
              )
            }
          >
            Экспорт CSV
          </button>
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
        <section className="panel report-panel">
          <div className="report-toolbar">
            <div className="report-tabs">
              {reportTabs.map((item) => (
                <button
                  type="button"
                  key={item.name}
                  className={
                    reportName ===
                    item.name
                      ? "management-tab active"
                      : "management-tab"
                  }
                  onClick={() =>
                    setReportName(
                      item.name,
                    )
                  }
                >
                  {item.label}
                </button>
              ))}
            </div>

            <form
              className="report-search"
              onSubmit={(
                event: FormEvent<HTMLFormElement>,
              ) => {
                event.preventDefault();
              }}
            >
              <input
                value={query}
                onChange={(event) =>
                  setQuery(
                    event.target.value,
                  )
                }
                placeholder="Фильтр по текущему отчёту..."
              />
              {query && (
                <button
                  className="button secondary"
                  type="button"
                  onClick={() =>
                    setQuery("")
                  }
                >
                  Сбросить
                </button>
              )}
            </form>
          </div>

          <div className="report-meta">
            <div>
              <strong>
                {data?.title ||
                  "Загрузка..."}
              </strong>
              <span>
                {currentEvent.event_name}
              </span>
            </div>

            <div>
              Строк:{" "}
              <strong>
                {filteredRows.length}
              </strong>
            </div>
          </div>

          {loading ? (
            <div className="empty-state">
              Загрузка отчёта…
            </div>
          ) : (
            <div className="data-table-wrap report-table-wrap">
              <table className="data-table report-table">
                <thead>
                  <tr>
                    {(data?.columns || []).map(
                      (column) => (
                        <th key={column.key}>
                          {column.label}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map(
                    (row, rowIndex) => (
                      <tr key={rowIndex}>
                        {(data?.columns ||
                          []).map(
                          (column) => (
                            <td
                              key={
                                column.key
                              }
                            >
                              {renderValue(
                                row[
                                  column
                                    .key
                                ],
                                column.key,
                                currentEvent.currency,
                              )}
                            </td>
                          ),
                        )}
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}


function renderValue(
  value:
    | string
    | number
    | boolean
    | null,
  key: string,
  currency: string,
) {
  if (
    typeof value === "number" &&
    [
      "Total",
      "Paid",
      "Balance",
      "Charged",
    ].includes(key)
  ) {
    try {
      return new Intl.NumberFormat(
        "ru-RU",
        {
          style: "currency",
          currency,
          maximumFractionDigits: 2,
        },
      ).format(value);
    } catch {
      return value;
    }
  }

  if (value === null) return "";
  return String(value);
}


function exportCsv(
  report: ReportData,
  rows: ReportData["rows"],
) {
  const separator = ";";
  const columns = report.columns;

  const lines = [
    columns
      .map((column) =>
        csvCell(column.label),
      )
      .join(separator),
    ...rows.map((row) =>
      columns
        .map((column) =>
          csvCell(
            row[column.key],
          ),
        )
        .join(separator),
    ),
  ];

  const content =
    "\uFEFF" + lines.join("\r\n");
  const blob = new Blob(
    [content],
    {
      type: "text/csv;charset=utf-8",
    },
  );
  const url =
    URL.createObjectURL(blob);
  const anchor =
    document.createElement("a");

  anchor.href = url;
  anchor.download =
    `${report.report}_${report.event.code}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}


function csvCell(
  value: unknown,
) {
  const text = String(value ?? "");
  return `"${text.replace(
    /"/g,
    '""',
  )}"`;
}


function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Неизвестная ошибка";
}
