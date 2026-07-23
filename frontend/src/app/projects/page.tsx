"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", description: "" });

  async function load() {
    setProjects(await api.get<Project[]>("/api/projects"));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api/projects", { name: form.name, description: form.description || null });
      setForm({ name: "", description: "" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen");
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Projekte</h1>

      <section className="card space-y-3">
        <h2 className="font-medium">Neues Projekt</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm mb-1">Name *</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm mb-1">Beschreibung</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" className="btn">
            Anlegen
          </button>
        </form>
      </section>

      <section className="card">
        <ul className="divide-y">
          {projects.map((p) => (
            <li key={p.id} className="py-2 flex items-center justify-between">
              <div>
                <Link href={`/projects/${p.id}`} className="font-medium text-blue-600 hover:underline">
                  {p.name}
                </Link>
                {p.description && <p className="text-sm text-gray-500">{p.description}</p>}
              </div>
              <span
                className={`text-xs px-2 py-1 rounded-full ${
                  p.status === "ACTIVE"
                    ? "bg-green-100 text-green-700"
                    : p.status === "COMPLETED"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {statusLabel(p.status)}
              </span>
            </li>
          ))}
          {projects.length === 0 && <p className="text-gray-500">Noch keine Projekte angelegt.</p>}
        </ul>
      </section>
    </div>
  );
}

function statusLabel(status: Project["status"]) {
  switch (status) {
    case "ACTIVE":
      return "Aktiv";
    case "COMPLETED":
      return "Abgeschlossen";
    case "ARCHIVED":
      return "Archiviert";
  }
}
