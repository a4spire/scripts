"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Item } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const [lowStock, setLowStock] = useState<Item[] | null>(null);

  useEffect(() => {
    if (!user) return;
    api.get<Item[]>("/api/items?lowStock=true").then(setLowStock);
  }, [user]);

  if (loading) return <p>Lädt…</p>;
  if (!user) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      <section className="card">
        <h2 className="font-medium mb-3">Mindestbestand unterschritten</h2>
        {lowStock === null && <p className="text-sm text-gray-500">Lädt…</p>}
        {lowStock?.length === 0 && (
          <p className="text-sm text-gray-500">Alles im grünen Bereich, keine Warnungen.</p>
        )}
        <ul className="divide-y">
          {lowStock?.map((item) => (
            <li key={item.id} className="py-2 flex items-center justify-between">
              <div>
                <Link href={`/items/${item.id}`} className="font-medium text-blue-600 hover:underline">
                  {item.name}
                </Link>
                <p className="text-sm text-gray-500">
                  {item.location?.name ?? "Kein Lagerort"}
                </p>
              </div>
              <span className="text-sm text-red-600">
                {item.quantity} / min {item.minQuantity} {item.unit}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Link href="/items/new" className="card text-center hover:bg-gray-50">
          + Artikel anlegen
        </Link>
        <Link href="/locations" className="card text-center hover:bg-gray-50">
          Lagerorte
        </Link>
        <Link href="/projects" className="card text-center hover:bg-gray-50">
          Projekte
        </Link>
        <Link href="/scan" className="card text-center hover:bg-gray-50">
          Scannen
        </Link>
        <Link href="/capture" className="card text-center hover:bg-gray-50">
          KI-Erfassung
        </Link>
      </section>
    </div>
  );
}
