"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "./AuthProvider";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/items", label: "Artikel" },
  { href: "/locations", label: "Lagerorte" },
  { href: "/projects", label: "Projekte" },
  { href: "/stats", label: "Statistik" },
  { href: "/shopping-list", label: "Einkaufsliste" },
  { href: "/scan", label: "Scannen" },
  { href: "/capture", label: "KI-Erfassung" },
];

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (pathname === "/login") return null;

  return (
    <nav className="border-b bg-white sticky top-0 z-10">
      <div className="mx-auto max-w-5xl flex items-center gap-1 px-4 py-2 overflow-x-auto">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`px-3 py-2 rounded-md text-sm whitespace-nowrap ${
              pathname === link.href ? "bg-blue-600 text-white" : "text-gray-700 hover:bg-gray-100"
            }`}
          >
            {link.label}
          </Link>
        ))}
        <div className="ml-auto flex items-center gap-2 text-sm text-gray-500 whitespace-nowrap">
          {user && <span>{user.displayName}</span>}
          {user && (
            <button onClick={logout} className="px-2 py-1 rounded hover:bg-gray-100">
              Abmelden
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
