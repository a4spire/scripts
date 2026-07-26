"use client";

import { useEffect, useState } from "react";
import { api, ApiError, User } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const [profileForm, setProfileForm] = useState({
    displayName: "",
    email: "",
    currentPasswordForEmail: "",
  });
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileDone, setProfileDone] = useState<string | null>(null);
  const [profileBusy, setProfileBusy] = useState(false);

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordDone, setPasswordDone] = useState<string | null>(null);
  const [passwordBusy, setPasswordBusy] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileForm({ displayName: user.displayName, email: user.email, currentPasswordForEmail: "" });
    }
  }, [user]);

  if (!user) return <p>Lädt…</p>;

  const emailChanged = profileForm.email !== user.email;

  async function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    setProfileError(null);
    setProfileDone(null);
    setProfileBusy(true);
    try {
      const body: Record<string, string> = { displayName: profileForm.displayName };
      if (emailChanged) {
        body.email = profileForm.email;
        body.currentPassword = profileForm.currentPasswordForEmail;
      }
      await api.patch<User>("/api/auth/me", body);
      await refresh();
      setProfileDone("Gespeichert.");
    } catch (err) {
      setProfileError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setProfileBusy(false);
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setPasswordDone(null);

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError("Neue Passwörter stimmen nicht überein");
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      setPasswordError("Neues Passwort muss mindestens 8 Zeichen haben");
      return;
    }

    setPasswordBusy(true);
    try {
      await api.patch("/api/auth/me", {
        currentPassword: passwordForm.currentPassword,
        newPassword: passwordForm.newPassword,
      });
      setPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setPasswordDone("Passwort geändert.");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Ändern fehlgeschlagen");
    } finally {
      setPasswordBusy(false);
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="text-xl font-semibold">Einstellungen</h1>

      <section className="card space-y-4">
        <h2 className="font-medium">Profil</h2>
        <form onSubmit={handleProfileSubmit} className="space-y-3">
          <div>
            <label className="block text-sm mb-1">Anzeigename</label>
            <input
              required
              value={profileForm.displayName}
              onChange={(e) => setProfileForm({ ...profileForm, displayName: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">E-Mail</label>
            <input
              type="email"
              required
              value={profileForm.email}
              onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
            />
          </div>
          {emailChanged && (
            <div>
              <label className="block text-sm mb-1">Aktuelles Passwort (zur Bestätigung der E-Mail-Änderung)</label>
              <input
                type="password"
                required
                value={profileForm.currentPasswordForEmail}
                onChange={(e) =>
                  setProfileForm({ ...profileForm, currentPasswordForEmail: e.target.value })
                }
              />
            </div>
          )}
          {profileError && <p className="text-sm text-red-600">{profileError}</p>}
          {profileDone && <p className="text-sm text-green-700">{profileDone}</p>}
          <button type="submit" className="btn" disabled={profileBusy}>
            {profileBusy ? "Speichert…" : "Speichern"}
          </button>
        </form>
      </section>

      <section className="card space-y-4">
        <h2 className="font-medium">Passwort ändern</h2>
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <div>
            <label className="block text-sm mb-1">Aktuelles Passwort</label>
            <input
              type="password"
              required
              value={passwordForm.currentPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Neues Passwort</label>
            <input
              type="password"
              required
              minLength={8}
              value={passwordForm.newPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Neues Passwort bestätigen</label>
            <input
              type="password"
              required
              minLength={8}
              value={passwordForm.confirmPassword}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
            />
          </div>
          {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
          {passwordDone && <p className="text-sm text-green-700">{passwordDone}</p>}
          <button type="submit" className="btn" disabled={passwordBusy}>
            {passwordBusy ? "Ändert…" : "Passwort ändern"}
          </button>
        </form>
      </section>
    </div>
  );
}
