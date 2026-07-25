"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, apiUrl, ApiError, Item, ShoppingListItem } from "@/lib/api";

export default function ShoppingListPage() {
  const [entries, setEntries] = useState<ShoppingListItem[] | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ itemId: "", customName: "", quantity: "1", note: "" });

  async function load() {
    setEntries(await api.get<ShoppingListItem[]>("/api/shopping-list"));
  }

  useEffect(() => {
    load();
    api.get<Item[]>("/api/items").then(setItems);
  }, []);

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ created: number }>("/api/shopping-list/generate");
      if (res.created === 0) {
        setError(null);
      }
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Vorschläge konnten nicht generiert werden");
    } finally {
      setBusy(false);
    }
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/shopping-list", {
        itemId: form.itemId || null,
        customName: form.itemId ? null : form.customName || null,
        quantity: Number(form.quantity),
        note: form.note || null,
      });
      setForm({ itemId: "", customName: "", quantity: "1", note: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Hinzufügen fehlgeschlagen");
    }
  }

  async function setStatus(id: string, status: ShoppingListItem["status"]) {
    await api.patch(`/api/shopping-list/${id}`, { status });
    await load();
  }

  async function remove(id: string) {
    await api.delete(`/api/shopping-list/${id}`);
    await load();
  }

  if (!entries) return <p>Lädt…</p>;

  const open = entries.filter((e) => e.status === "OPEN");
  const ordered = entries.filter((e) => e.status === "ORDERED");
  const done = entries.filter((e) => e.status === "DONE");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Einkaufsliste</h1>
        <div className="flex gap-2">
          <button className="btn-secondary text-sm" onClick={handleGenerate} disabled={busy}>
            {busy ? "Prüft…" : "Vorschläge aus Mindestbestand"}
          </button>
          <a href={apiUrl("/api/shopping-list/export")} className="btn text-sm">
            Liste exportieren (CSV)
          </a>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <section className="card space-y-3">
        <h2 className="font-medium">Position hinzufügen</h2>
        <form onSubmit={handleAdd} className="grid grid-cols-2 gap-3 items-end">
          <div>
            <label className="block text-sm mb-1">Vorhandener Artikel</label>
            <select value={form.itemId} onChange={(e) => setForm({ ...form, itemId: e.target.value })}>
              <option value="">– oder freien Text unten eintragen –</option>
              {items.map((it) => (
                <option key={it.id} value={it.id}>
                  {it.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">Menge</label>
            <input
              type="number"
              step="0.001"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            />
          </div>
          {!form.itemId && (
            <div className="col-span-2">
              <label className="block text-sm mb-1">Freitext (z.B. Werkzeug, kein Lagerartikel)</label>
              <input
                value={form.customName}
                onChange={(e) => setForm({ ...form, customName: e.target.value })}
              />
            </div>
          )}
          <div className="col-span-2">
            <label className="block text-sm mb-1">Notiz</label>
            <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          <button type="submit" className="btn col-span-2">
            Hinzufügen
          </button>
        </form>
      </section>

      <ShoppingListSection
        title="Offen"
        entries={open}
        onOrdered={(id) => setStatus(id, "ORDERED")}
        onDone={(id) => setStatus(id, "DONE")}
        onDelete={remove}
      />
      <ShoppingListSection
        title="Bestellt"
        entries={ordered}
        onDone={(id) => setStatus(id, "DONE")}
        onReopen={(id) => setStatus(id, "OPEN")}
        onDelete={remove}
      />
      <ShoppingListSection
        title="Erledigt"
        entries={done}
        onReopen={(id) => setStatus(id, "OPEN")}
        onDelete={remove}
        collapsedByDefault
      />
    </div>
  );
}

function ShoppingListSection({
  title,
  entries,
  onOrdered,
  onDone,
  onReopen,
  onDelete,
  collapsedByDefault,
}: {
  title: string;
  entries: ShoppingListItem[];
  onOrdered?: (id: string) => void;
  onDone?: (id: string) => void;
  onReopen?: (id: string) => void;
  onDelete: (id: string) => void;
  collapsedByDefault?: boolean;
}) {
  const [open, setOpen] = useState(!collapsedByDefault);

  return (
    <section className="card space-y-3">
      <button className="font-medium flex items-center gap-2" onClick={() => setOpen(!open)}>
        {title} ({entries.length}) <span className="text-gray-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <ul className="divide-y text-sm">
          {entries.map((e) => (
            <li key={e.id} className="py-2 flex items-center justify-between gap-3">
              <div>
                {e.item ? (
                  <Link href={`/items/${e.item.id}`} className="font-medium text-blue-600 hover:underline">
                    {e.item.name}
                  </Link>
                ) : (
                  <span className="font-medium">{e.customName}</span>
                )}
                <p className="text-gray-500">
                  {e.quantity} {e.item?.unit ?? ""}
                  {e.note && ` · ${e.note}`}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {onOrdered && (
                  <button className="btn-secondary text-xs" onClick={() => onOrdered(e.id)}>
                    Bestellt
                  </button>
                )}
                {onDone && (
                  <button className="btn-secondary text-xs" onClick={() => onDone(e.id)}>
                    Erledigt
                  </button>
                )}
                {onReopen && (
                  <button className="btn-secondary text-xs" onClick={() => onReopen(e.id)}>
                    Zurücksetzen
                  </button>
                )}
                <button className="text-red-600 text-xs" onClick={() => onDelete(e.id)}>
                  Entfernen
                </button>
              </div>
            </li>
          ))}
          {entries.length === 0 && <p className="text-gray-500">Keine Einträge.</p>}
        </ul>
      )}
    </section>
  );
}
