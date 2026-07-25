"use client";

import { useEffect, useState } from "react";
import { api, apiUrl, ApiError, Location } from "@/lib/api";

export default function LocationsPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", type: "REGAL", parentId: "" });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  async function load() {
    setLocations(await api.get<Location[]>("/api/locations"));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/locations", {
        name: form.name,
        type: form.type,
        parentId: form.parentId || null,
      });
      setForm({ name: "", type: "REGAL", parentId: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen");
    }
  }

  function pathFor(loc: Location): string {
    if (!loc.parentId) return loc.name;
    const parent = locations.find((l) => l.id === loc.parentId);
    return parent ? `${pathFor(parent)} → ${loc.name}` : loc.name;
  }

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) => (prev.size === locations.length ? new Set() : new Set(locations.map((l) => l.id))));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Lagerorte</h1>
        <a href={apiUrl("/api/locations/labels/pdf")} className="btn-secondary text-sm">
          Alle Labels drucken (PDF)
        </a>
      </div>

      <section className="card space-y-3">
        <h2 className="font-medium">Neuer Lagerort</h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-3 items-end">
          <div>
            <label className="block text-sm mb-1">Name *</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm mb-1">Typ</label>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="WERKSTATT">Werkstatt</option>
              <option value="REGAL">Regal</option>
              <option value="FACH">Fach</option>
              <option value="BOX">Box</option>
              <option value="SONSTIGE">Sonstige</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-sm mb-1">Übergeordneter Lagerort</label>
            <select
              value={form.parentId}
              onChange={(e) => setForm({ ...form, parentId: e.target.value })}
            >
              <option value="">– kein übergeordneter Ort –</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {pathFor(loc)}
                </option>
              ))}
            </select>
          </div>
          {error && <p className="col-span-2 text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn col-span-2">
            Anlegen
          </button>
        </form>
      </section>

      <section className="card space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="w-auto"
              checked={locations.length > 0 && selectedIds.size === locations.length}
              onChange={toggleSelectAll}
            />
            Alle auswählen
          </label>
          {selectedIds.size > 0 && (
            <a
              href={apiUrl(`/api/locations/labels/pdf?ids=${Array.from(selectedIds).join(",")}`)}
              className="btn text-sm"
            >
              {selectedIds.size} ausgewählte Labels drucken
            </a>
          )}
        </div>
        <ul className="divide-y text-sm">
          {locations.map((loc) => (
            <li key={loc.id} className="py-2 flex items-center gap-3">
              <input
                type="checkbox"
                className="w-auto"
                checked={selectedIds.has(loc.id)}
                onChange={() => toggleSelected(loc.id)}
              />
              <span className="flex-1">{pathFor(loc)}</span>
              <span className="text-gray-400 font-mono text-xs">{loc.qrCode}</span>
            </li>
          ))}
          {locations.length === 0 && <p className="text-gray-500">Noch keine Lagerorte angelegt.</p>}
        </ul>
      </section>
    </div>
  );
}
