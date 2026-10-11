import { useEffect, useRef, useState } from "react";
import type { CurrentUser, UserRole } from "../types";
import BrandLogo from "./BrandLogo";

export type View = "dashboard" | "applications" | "events" | "vendors" | "planning" |
  "seating" | "checkin" | "reports" | "management" | "users";

type NavigationItem = { view: View; label: string; roles: readonly UserRole[] };
const allRoles: readonly UserRole[] = ["ADMIN", "MANAGER", "REGISTRATION", "VIEWER"];
const organizerRoles: readonly UserRole[] = ["ADMIN", "MANAGER", "VIEWER"];

// These are the original shell's visibility rules, including VIEWER access.
const navigation: readonly NavigationItem[] = [
  { view: "dashboard", label: "Dashboard", roles: allRoles },
  { view: "events", label: "Мероприятия", roles: allRoles },
  { view: "vendors", label: "Вендоры", roles: allRoles },
  { view: "applications", label: "Заявки", roles: organizerRoles },
  { view: "planning", label: "Планирование", roles: organizerRoles },
  { view: "seating", label: "Рассадка", roles: allRoles },
  { view: "checkin", label: "Check-in", roles: allRoles },
  { view: "reports", label: "Отчёты", roles: allRoles },
  { view: "management", label: "Управление", roles: ["ADMIN", "MANAGER"] },
  { view: "users", label: "Пользователи", roles: ["ADMIN"] },
];

export default function AppNavigation({
  user, currentEventName, view, onSelect, onLogout,
}: {
  user: CurrentUser;
  currentEventName: string;
  view: View;
  onSelect: (view: View) => void;
  onLogout: () => Promise<void>;
}) {
  const items = navigation.filter(item => item.roles.includes(user.role));
  const primary = items.slice(0, 6);
  const overflow = items.slice(6);
  const selectedOverflow = overflow.find(item => item.view === view);
  const [moreOpen, setMoreOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const mobileButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!moreOpen) return;
    function dismiss(event: PointerEvent) {
      if (!moreRef.current?.contains(event.target as Node)) setMoreOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMoreOpen(false);
        moreButtonRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [moreOpen]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!mobileOpen) {
      if (dialog.open) {
        dialog.close();
        mobileButtonRef.current?.focus();
      }
      return;
    }
    dialog.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [mobileOpen]);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    function resize() {
      setMoreOpen(false);
      if (desktop.matches) setMobileOpen(false);
    }
    desktop.addEventListener("change", resize);
    return () => desktop.removeEventListener("change", resize);
  }, []);

  function select(next: View, source: "primary" | "overflow" | "mobile") {
    onSelect(next);
    setMoreOpen(false);
    setMobileOpen(false);
    if (source === "overflow") moreButtonRef.current?.focus();
  }

  function buttons(list: readonly NavigationItem[], source: "primary" | "overflow" | "mobile") {
    return list.map(item => (
      <button
        key={item.view}
        type="button"
        className={`cm-nav-button${view === item.view ? " active" : ""}`}
        aria-current={view === item.view ? "page" : undefined}
        onClick={() => select(item.view, source)}
      >
        {item.label}
      </button>
    ));
  }

  return (
    <header className="cm-header">
      <a className="skip-link" href="#main-content">К содержимому</a>
      <div className="cm-header-row">
        <div className="cm-desktop-brand"><BrandLogo /></div>
        <div className="cm-mobile-brand">
          <BrandLogo variant="mark" decorative />
          <strong>ConMan</strong>
        </div>
        <div className="cm-event-context">
          <span>Текущее мероприятие</span>
          <strong title={currentEventName}>{currentEventName}</strong>
        </div>
        <div className="cm-account">
          <div className="cm-account-name">
            <strong title={user.display_name}>{user.display_name}</strong>
            <span>{user.role}</span>
          </div>
          <button type="button" className="button secondary" onClick={onLogout}>Выйти</button>
        </div>
        <button
          ref={mobileButtonRef}
          type="button"
          className="button secondary cm-mobile-toggle"
          aria-expanded={mobileOpen}
          aria-controls="cm-mobile-navigation"
          aria-haspopup="dialog"
          onClick={() => setMobileOpen(true)}
        >
          <span aria-hidden="true">☰</span> Меню
        </button>
      </div>
      <nav className="cm-desktop-nav" aria-label="Основные разделы">
        {buttons(primary, "primary")}
        {overflow.length > 0 && (
          <div className="cm-nav-overflow" ref={moreRef}>
            <button
              ref={moreButtonRef}
              type="button"
              className={`cm-nav-button${selectedOverflow ? " active" : ""}`}
              aria-expanded={moreOpen}
              aria-controls="cm-overflow-navigation"
              onClick={() => setMoreOpen(!moreOpen)}
            >
              {selectedOverflow ? `Ещё: ${selectedOverflow.label}` : "Ещё"}
              <span aria-hidden="true">▾</span>
            </button>
            {moreOpen && (
              <div id="cm-overflow-navigation" className="cm-overflow-panel" role="group" aria-label="Дополнительные разделы">
                {buttons(overflow, "overflow")}
              </div>
            )}
          </div>
        )}
      </nav>
      <dialog
        ref={dialogRef}
        id="cm-mobile-navigation"
        className="cm-mobile-dialog"
        aria-labelledby="cm-mobile-title"
        onCancel={event => { event.preventDefault(); setMobileOpen(false); }}
        onClose={() => setMobileOpen(false)}
        onClick={event => { if (event.target === dialogRef.current) setMobileOpen(false); }}
      >
        <div className="cm-drawer-content">
          <div className="cm-drawer-heading">
            <h2 id="cm-mobile-title">Разделы ConMan</h2>
            <button type="button" className="button secondary" autoFocus aria-label="Закрыть меню" onClick={() => setMobileOpen(false)}>×</button>
          </div>
          <nav aria-label="Разделы в мобильном меню">{buttons(items, "mobile")}</nav>
        </div>
      </dialog>
    </header>
  );
}
