"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Category, Location } from "@/lib/api";

export default function NewItemPage() {
  const router = useRouter();
  const [locations, setLocations] = useState<Location[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    name: "",
    description: "",
    unit: "Stk",
    minQuantity: "0",
    locationId: "",
    categoryId: "",
    manufacturer: "",
    purchasePrice: "",
    purchaseSource: "",
  });

  useEffect(() => {
    api.get<Location[]>("/api/locations").then(setLocations);
    api.get<Category[]>("/api/categories").then(setCategories);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const item = await api.post<{ id: string }>("/api/items", {
        name: form.name,
        description: form.description || undefined,
        unit: form.unit,
        minQuantity: Number(form.minQuantity),
        locationId: form.locationId || null,
        categoryId: form.categoryId || null,
        manufacturer: form.manufacturer || null,
        purchasePrice: form.purchasePrice ? Number(form.purchasePrice) : null,
        purchaseSource: form.purchaseSource || null,
      });
      router.replace(`/items/${item.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <h1 className="text-xl font-semibold">Neuer Artikel</h1>
      <form onSubmit={handleSubmit} className="card space-y-4">
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
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm mb-1">Einheit</label>
            <input value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm mb-1">Mindestbestand</label>
            <input
              type="number"
              value={form.minQuantity}
              onChange={(e) => setForm({ ...form, minQuantity: e.target.value })}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm mb-1">Lagerort</label>
          <select
            value={form.locationId}
            onChange={(e) => setForm({ ...form, locationId: e.target.value })}
          >
            <option value="">– kein Lagerort –</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm mb-1">Kategorie</label>
          <select
            value={form.categoryId}
            onChange={(e) => setForm({ ...form, categoryId: e.target.value })}
          >
            <option value="">– keine Kategorie –</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm mb-1">Hersteller</label>
            <input
              value={form.manufacturer}
              onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">Einkaufspreis (€)</label>
            <input
              type="number"
              step="0.01"
              value={form.purchasePrice}
              onChange={(e) => setForm({ ...form, purchasePrice: e.target.value })}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm mb-1">Einkaufsquelle</label>
          <input
            value={form.purchaseSource}
            onChange={(e) => setForm({ ...form, purchaseSource: e.target.value })}
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" className="btn" disabled={submitting}>
          {submitting ? "Speichert…" : "Artikel anlegen"}
        </button>
      </form>
    </div>
  );
}
