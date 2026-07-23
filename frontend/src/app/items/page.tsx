"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Item } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export default function ItemsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Item[] | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!user) return;
    const params = search ? `?search=${encodeURIComponent(search)}` : "";
    api.get<Item[]>(`/api/items${params}`).then(setItems);
  }, [user, search]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Artikel</h1>
        <Link href="/items/new" className="btn">
          + Neuer Artikel
        </Link>
      </div>
      <input
        placeholder="Suche nach Name…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />
      <div className="card">
        {items === null && <p className="text-sm text-gray-500">Lädt…</p>}
        {items?.length === 0 && <p className="text-sm text-gray-500">Keine Artikel gefunden.</p>}
        <ul className="divide-y">
          {items?.map((item) => (
            <li key={item.id} className="py-2 flex items-center justify-between">
              <div>
                <Link href={`/items/${item.id}`} className="font-medium text-blue-600 hover:underline">
                  {item.name}
                </Link>
                <p className="text-sm text-gray-500">
                  {item.category?.name ?? "Ohne Kategorie"} · {item.location?.name ?? "Ohne Lagerort"}
                </p>
              </div>
              <span className="text-sm">
                {item.quantity} {item.unit}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
