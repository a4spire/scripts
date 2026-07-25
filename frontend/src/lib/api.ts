const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers:
      options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json", ...options.headers }
        : options.headers,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    throw new ApiError(data?.error ?? `Anfrage fehlgeschlagen (${res.status})`, res.status);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function photoUrl(photoPath: string | null | undefined) {
  if (!photoPath) return null;
  return `${API_URL}/photos/${photoPath}`;
}

export function apiUrl(path: string) {
  return `${API_URL}${path}`;
}

export interface User {
  id: string;
  email: string;
  displayName: string;
  role: "ADMIN" | "MEMBER";
}

export interface Location {
  id: string;
  name: string;
  type: string;
  parentId: string | null;
  qrCode: string | null;
}

export interface Category {
  id: string;
  name: string;
  parentId: string | null;
}

export interface Item {
  id: string;
  name: string;
  description: string | null;
  unit: string;
  quantity: string;
  minQuantity: string;
  manufacturer: string | null;
  specs: Record<string, unknown> | null;
  purchasePrice: string | null;
  purchaseSource: string | null;
  photoPath: string | null;
  barcode: string | null;
  categoryId: string | null;
  locationId: string | null;
  category?: Category | null;
  location?: Location | null;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  status: "ACTIVE" | "COMPLETED" | "ARCHIVED";
  createdAt: string;
  completedAt: string | null;
  totalCost?: string;
}

export interface ShoppingListItem {
  id: string;
  itemId: string | null;
  customName: string | null;
  quantity: string;
  note: string | null;
  status: "OPEN" | "ORDERED" | "DONE";
  createdAt: string;
  resolvedAt: string | null;
  item?: (Item & { location?: Location | null }) | null;
}

export interface StockMovement {
  id: string;
  itemId: string;
  type: "IN" | "OUT" | "RETURN" | "CORRECTION";
  quantity: string;
  projectId: string | null;
  reason: string | null;
  createdAt: string;
  item?: Item;
  project?: Project | null;
  user?: { id: string; displayName: string };
}
