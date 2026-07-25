"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface TopItem {
  id: string;
  name: string;
  unit: string;
  totalOut: string;
}

interface ProjectCost {
  id: string;
  name: string;
  status: "ACTIVE" | "COMPLETED" | "ARCHIVED";
  cost: string;
}

interface StatsOverview {
  inventoryValue: string;
  itemCount: number;
  topItems: TopItem[];
  projectCosts: ProjectCost[];
}

function statusLabel(status: ProjectCost["status"]) {
  switch (status) {
    case "ACTIVE":
      return "Aktiv";
    case "COMPLETED":
      return "Abgeschlossen";
    case "ARCHIVED":
      return "Archiviert";
  }
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);

  useEffect(() => {
    api.get<StatsOverview>("/api/stats/overview").then(setStats);
  }, []);

  if (!stats) return <p>Lädt…</p>;

  const maxOut = Math.max(1, ...stats.topItems.map((i) => Number(i.totalOut)));
  const maxCost = Math.max(1, ...stats.projectCosts.map((p) => Number(p.cost)));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Statistik</h1>

      <section className="card">
        <h2 className="font-medium mb-1">Lagerwert</h2>
        <p className="text-2xl font-semibold">{stats.inventoryValue} €</p>
        <p className="text-xs text-gray-500">
          Summe aus Bestand × Einkaufspreis über {stats.itemCount} Artikel (nur Artikel mit hinterlegtem
          Einkaufspreis fließen ein).
        </p>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Meistgenutzte Teile</h2>
        {stats.topItems.length === 0 && (
          <p className="text-sm text-gray-500">Noch keine Entnahmen gebucht.</p>
        )}
        <ul className="space-y-2">
          {stats.topItems.map((item) => (
            <li key={item.id}>
              <div className="flex items-center justify-between text-sm mb-1">
                <Link href={`/items/${item.id}`} className="text-blue-600 hover:underline">
                  {item.name}
                </Link>
                <span className="text-gray-500">
                  {item.totalOut} {item.unit}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500"
                  style={{ width: `${(Number(item.totalOut) / maxOut) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Projektkosten-Übersicht</h2>
        {stats.projectCosts.length === 0 && (
          <p className="text-sm text-gray-500">Noch keine Projekte mit Materialverbrauch.</p>
        )}
        <ul className="space-y-2">
          {stats.projectCosts.map((project) => (
            <li key={project.id}>
              <div className="flex items-center justify-between text-sm mb-1">
                <Link href={`/projects/${project.id}`} className="text-blue-600 hover:underline">
                  {project.name}
                </Link>
                <span className="text-gray-500">
                  {project.cost} € · {statusLabel(project.status)}
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500"
                  style={{ width: `${(Math.max(0, Number(project.cost)) / maxCost) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
