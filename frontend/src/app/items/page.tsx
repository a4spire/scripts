"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, Item, Location } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

function ItemsPageContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const locationId = searchParams.get("locationId");

  const [items, setItems] = useState<Item[] | null>(null);
  const [location, setLocation] = useState<Location | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!user) return;
    const timeout = setTimeout(() => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (locationId) params.set("locationId", locationId);
      const qs = params.toString();
      api.get<Item[]>(`/api/items${qs ? `?${qs}` : ""}`).then(setItems);
    }, 250);
    return () => clearTimeout(timeout);
  }, [user, search, locationId]);

  useEffect(() => {
    if (!locationId) {
      setLocation(null);
      return;
    }
    api.get<Location>(`/api/locations/${locationId}`).then(setLocation).catch(() => setLocation(null));
  }, [locationId]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Artikel</h1>
        <Link href="/items/new" className="btn">
          + Neuer Artikel
        </Link>
      </div>

      {locationId && (
        <div className="flex items-center gap-2 text-sm bg-blue-50 text-blue-800 rounded-md px-3 py-2">
          <span>Gefiltert nach Lagerort: {location?.name ?? locationId}</span>
          <Link href="/items" className="underline">
            Filter entfernen
          </Link>
        </div>
      )}

      <input
        placeholder="Suche (Name, Beschreibung, Hersteller, Specs, Barcode)…"
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

export default function ItemsPage() {
  return (
    <Suspense fallback={<p>Lädt…</p>}>
      <ItemsPageContent />
    </Suspense>
  );
}
