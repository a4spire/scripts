"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, Item, photoUrl, Project, StockMovement } from "@/lib/api";

type ItemDetail = Item & { movements: StockMovement[] };

export default function ItemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const [movementForm, setMovementForm] = useState({
    type: "IN" as StockMovement["type"],
    quantity: "1",
    projectId: "",
    reason: "",
  });

  async function load() {
    const data = await api.get<ItemDetail>(`/api/items/${id}`);
    setItem(data);
  }

  useEffect(() => {
    load();
    api.get<Project[]>("/api/projects?status=ACTIVE").then(setProjects);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      await api.post(`/api/items/${id}/photo`, body);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Foto-Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  }

  async function handleBookMovement(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/movements", {
        itemId: id,
        type: movementForm.type,
        quantity: Number(movementForm.quantity),
        projectId:
          movementForm.type === "OUT" && movementForm.projectId ? movementForm.projectId : null,
        reason: movementForm.reason || null,
      });
      setMovementForm({ ...movementForm, quantity: "1", reason: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Buchung fehlgeschlagen");
    }
  }

  if (!item) return <p>Lädt…</p>;

  const isLow = Number(item.quantity) <= Number(item.minQuantity);

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <div className="w-28 h-28 rounded-lg bg-gray-100 overflow-hidden flex items-center justify-center shrink-0">
          {item.photoPath ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={photoUrl(item.photoPath)!} alt={item.name} className="w-full h-full object-cover" />
          ) : (
            <span className="text-xs text-gray-400">kein Foto</span>
          )}
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-semibold">{item.name}</h1>
          <p className="text-sm text-gray-500">
            {item.category?.name ?? "Ohne Kategorie"} · {item.location?.name ?? "Ohne Lagerort"}
          </p>
          <p className={`text-sm mt-1 ${isLow ? "text-red-600" : "text-gray-700"}`}>
            Bestand: {item.quantity} {item.unit} (Mindestbestand {item.minQuantity})
          </p>
          <label className="btn-secondary mt-2 inline-block text-xs">
            {uploading ? "Lädt hoch…" : "Foto ändern"}
            <input type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
          </label>
        </div>
      </div>

      {item.description && <p className="card text-sm">{item.description}</p>}

      <section className="card space-y-3">
        <h2 className="font-medium">Bestandsbewegung buchen</h2>
        <form onSubmit={handleBookMovement} className="grid grid-cols-2 gap-3 items-end">
          <div>
            <label className="block text-sm mb-1">Typ</label>
            <select
              value={movementForm.type}
              onChange={(e) =>
                setMovementForm({ ...movementForm, type: e.target.value as StockMovement["type"] })
              }
            >
              <option value="IN">Wareneingang</option>
              <option value="OUT">Entnahme</option>
              <option value="RETURN">Rückgabe</option>
              <option value="CORRECTION">Korrektur</option>
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">Menge</label>
            <input
              type="number"
              step="0.001"
              value={movementForm.quantity}
              onChange={(e) => setMovementForm({ ...movementForm, quantity: e.target.value })}
            />
          </div>
          {movementForm.type === "OUT" && (
            <div className="col-span-2">
              <label className="block text-sm mb-1">Projekt</label>
              <select
                value={movementForm.projectId}
                onChange={(e) => setMovementForm({ ...movementForm, projectId: e.target.value })}
              >
                <option value="">– kein Projekt / allgemein –</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="col-span-2">
            <label className="block text-sm mb-1">Grund/Notiz</label>
            <input
              value={movementForm.reason}
              onChange={(e) => setMovementForm({ ...movementForm, reason: e.target.value })}
            />
          </div>
          {error && <p className="col-span-2 text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn col-span-2">
            Buchen
          </button>
        </form>
      </section>

      <section className="card">
        <h2 className="font-medium mb-3">Bewegungshistorie</h2>
        <ul className="divide-y text-sm">
          {item.movements.map((m) => (
            <li key={m.id} className="py-2 flex items-center justify-between">
              <div>
                <span className="font-medium">{typeLabel(m.type)}</span>{" "}
                <span>
                  {m.quantity} {item.unit}
                </span>
                {m.project && <span className="text-gray-500"> · Projekt: {m.project.name}</span>}
                {m.reason && <span className="text-gray-500"> · {m.reason}</span>}
              </div>
              <span className="text-gray-400">{new Date(m.createdAt).toLocaleString("de-DE")}</span>
            </li>
          ))}
          {item.movements.length === 0 && <p className="text-gray-500">Noch keine Bewegungen.</p>}
        </ul>
      </section>
    </div>
  );
}

function typeLabel(type: StockMovement["type"]) {
  switch (type) {
    case "IN":
      return "Wareneingang";
    case "OUT":
      return "Entnahme";
    case "RETURN":
      return "Rückgabe";
    case "CORRECTION":
      return "Korrektur";
  }
}
