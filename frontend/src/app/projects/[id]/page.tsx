"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError, Project, StockMovement } from "@/lib/api";

type ProjectDetail = Project & { movements: StockMovement[] };

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [otherProjects, setOtherProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [transferForm, setTransferForm] = useState({ itemId: "", quantity: "1", toProjectId: "" });

  async function load() {
    const data = await api.get<ProjectDetail>(`/api/projects/${id}`);
    setProject(data);
  }

  useEffect(() => {
    load();
    api.get<Project[]>("/api/projects?status=ACTIVE").then((all) =>
      setOtherProjects(all.filter((p) => p.id !== id))
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function updateStatus(status: Project["status"]) {
    await api.patch(`/api/projects/${id}`, { status });
    await load();
  }

  async function handleTransfer(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/movements/transfer", {
        itemId: transferForm.itemId,
        quantity: Number(transferForm.quantity),
        fromProjectId: id,
        toProjectId: transferForm.toProjectId || null,
        reason: "Umbuchung aus Projektansicht",
      });
      setTransferForm({ itemId: "", quantity: "1", toProjectId: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Umbuchung fehlgeschlagen");
    }
  }

  if (!project) return <p>Lädt…</p>;

  const itemsInProject = Array.from(
    new Map(project.movements.map((m) => [m.itemId, m.item!])).values()
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{project.name}</h1>
          {project.description && <p className="text-sm text-gray-500">{project.description}</p>}
        </div>
        <select
          value={project.status}
          onChange={(e) => updateStatus(e.target.value as Project["status"])}
          className="w-auto"
        >
          <option value="ACTIVE">Aktiv</option>
          <option value="COMPLETED">Abgeschlossen</option>
          <option value="ARCHIVED">Archiviert</option>
        </select>
      </div>

      <section className="card">
        <h2 className="font-medium mb-2">Materialkosten (Summe)</h2>
        <p className="text-2xl font-semibold">{project.totalCost} €</p>
        <p className="text-xs text-gray-500">
          Bewertet mit dem aktuellen Einkaufspreis je Artikel (kein historischer Preis).
        </p>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Material zurückbuchen / umbuchen</h2>
        <form onSubmit={handleTransfer} className="grid grid-cols-2 gap-3 items-end">
          <div className="col-span-2">
            <label className="block text-sm mb-1">Artikel</label>
            <select
              required
              value={transferForm.itemId}
              onChange={(e) => setTransferForm({ ...transferForm, itemId: e.target.value })}
            >
              <option value="">– wählen –</option>
              {itemsInProject.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">Menge</label>
            <input
              type="number"
              step="0.001"
              value={transferForm.quantity}
              onChange={(e) => setTransferForm({ ...transferForm, quantity: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Ziel</label>
            <select
              value={transferForm.toProjectId}
              onChange={(e) => setTransferForm({ ...transferForm, toProjectId: e.target.value })}
            >
              <option value="">– zurück ins Lager (allgemein) –</option>
              {otherProjects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          {error && <p className="col-span-2 text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn col-span-2">
            Umbuchen
          </button>
        </form>
      </section>

      <section className="card">
        <h2 className="font-medium mb-3">Materialliste / Bewegungen</h2>
        <ul className="divide-y text-sm">
          {project.movements.map((m) => (
            <li key={m.id} className="py-2 flex items-center justify-between">
              <div>
                <span className="font-medium">{m.item?.name}</span>{" "}
                <span className="text-gray-500">
                  ({typeLabel(m.type)}, {m.quantity} {m.item?.unit})
                </span>
              </div>
              <span className="text-gray-400">{new Date(m.createdAt).toLocaleDateString("de-DE")}</span>
            </li>
          ))}
          {project.movements.length === 0 && <p className="text-gray-500">Noch kein Material entnommen.</p>}
        </ul>
      </section>
    </div>
  );
}

function typeLabel(type: StockMovement["type"]) {
  switch (type) {
    case "IN":
      return "Eingang";
    case "OUT":
      return "Entnahme";
    case "RETURN":
      return "Rückgabe";
    case "CORRECTION":
      return "Korrektur";
  }
}
