import { FormEvent, useState } from "react";
import type { BootstrapPayload } from "./types";
import BrandLogo from "./components/BrandLogo";

export default function FirstAdminPage({
  onCreate,
}: {
  onCreate: (payload: BootstrapPayload) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") || "");
    setError(null);
    if (password !== data.get("confirmation")) {
      setError("Пароли не совпадают.");
      return;
    }
    const displayName = String(data.get("display_name") || "").trim();
    if (!displayName) {
      setError("Укажите имя администратора.");
      return;
    }
    setBusy(true);
    try {
      await onCreate({
        email: String(data.get("email") || "").trim(),
        display_name: displayName,
        password,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать администратора.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <BrandLogo variant="stacked" />
        <h1>Первый запуск</h1>
        <p className="muted">
          Создайте администратора для управления ConMan. После создания учётной
          записи вы автоматически войдёте в систему.
        </p>
        {error && <div className="alert error" role="alert">{error}</div>}
        <form onSubmit={submit}>
          <label className="field">
            <span>Имя администратора</span>
            <input name="display_name" autoComplete="name" maxLength={200} required disabled={busy} />
          </label>
          <label className="field">
            <span>E-mail</span>
            <input name="email" type="email" autoComplete="username" maxLength={320} required disabled={busy} />
          </label>
          <label className="field">
            <span>Пароль (не менее 10 символов)</span>
            <input name="password" type="password" autoComplete="new-password" minLength={10} maxLength={200} required disabled={busy} />
          </label>
          <label className="field">
            <span>Повторите пароль</span>
            <input name="confirmation" type="password" autoComplete="new-password" minLength={10} maxLength={200} required disabled={busy} />
          </label>
          <button className="button primary full" type="submit" disabled={busy}>
            {busy ? "Создаём…" : "Создать администратора"}
          </button>
        </form>
      </div>
    </div>
  );
}
