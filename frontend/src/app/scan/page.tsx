"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Item, Location } from "@/lib/api";

const SCANNER_ELEMENT_ID = "qr-scanner-region";

type ScanState = "idle" | "starting" | "scanning" | "resolving" | "error";

export default function ScanPage() {
  const router = useRouter();
  const [state, setState] = useState<ScanState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [manualCode, setManualCode] = useState("");
  const scannerRef = useRef<import("html5-qrcode").Html5Qrcode | null>(null);
  const resolvingRef = useRef(false);

  useEffect(() => {
    return () => {
      scannerRef.current?.stop().catch(() => undefined);
    };
  }, []);

  async function resolveCode(code: string) {
    if (resolvingRef.current) return;
    resolvingRef.current = true;
    setState("resolving");
    await scannerRef.current?.stop().catch(() => undefined);

    try {
      const item = await api.get<Item>(`/api/items/barcode/${encodeURIComponent(code)}`);
      router.push(`/items/${item.id}`);
      return;
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        setError(err instanceof ApiError ? err.message : "Suche fehlgeschlagen");
        setState("error");
        resolvingRef.current = false;
        return;
      }
    }

    try {
      const location = await api.get<Location>(`/api/locations/qr/${encodeURIComponent(code)}`);
      router.push(`/items?locationId=${location.id}`);
      return;
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        setError(err instanceof ApiError ? err.message : "Suche fehlgeschlagen");
        setState("error");
        resolvingRef.current = false;
        return;
      }
    }

    // Unbekannter Code: Fallback in die Foto-Erfassung, Code wird dort vorausgefüllt.
    router.push(`/capture?barcode=${encodeURIComponent(code)}`);
  }

  async function startScanning() {
    setError(null);
    setState("starting");
    try {
      const { Html5Qrcode, Html5QrcodeSupportedFormats } = await import("html5-qrcode");
      const scanner = new Html5Qrcode(SCANNER_ELEMENT_ID, {
        formatsToSupport: [
          Html5QrcodeSupportedFormats.QR_CODE,
          Html5QrcodeSupportedFormats.EAN_13,
          Html5QrcodeSupportedFormats.EAN_8,
          Html5QrcodeSupportedFormats.CODE_128,
          Html5QrcodeSupportedFormats.CODE_39,
          Html5QrcodeSupportedFormats.UPC_A,
          Html5QrcodeSupportedFormats.UPC_E,
        ],
        verbose: false,
      });
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText) => resolveCode(decodedText),
        () => undefined
      );
      setState("scanning");
    } catch (err) {
      setError(
        "Kamera konnte nicht gestartet werden. Bitte Kamera-Berechtigung erlauben (erfordert HTTPS oder localhost) " +
          "oder den Code unten manuell eingeben."
      );
      setState("error");
    }
  }

  function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!manualCode.trim()) return;
    resolveCode(manualCode.trim());
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Code scannen</h1>
      <p className="text-sm text-gray-500">
        Scanne einen Artikel-Barcode oder einen Lagerort-QR-Code. Bekannte Codes führen direkt zum
        Artikel bzw. zur gefilterten Artikelliste des Lagerorts. Unbekannte Codes landen in der
        Foto-Erfassung zur Neuanlage.
      </p>

      <section className="card space-y-3">
        {state === "idle" && (
          <button className="btn" onClick={startScanning}>
            Kamera starten
          </button>
        )}
        {state === "starting" && <p className="text-sm text-gray-500">Kamera wird gestartet…</p>}
        {state === "resolving" && <p className="text-sm text-gray-500">Code wird zugeordnet…</p>}
        <div id={SCANNER_ELEMENT_ID} className="w-full max-w-sm mx-auto" />
        {error && <p className="text-sm text-red-600">{error}</p>}
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Code manuell eingeben</h2>
        <form onSubmit={handleManualSubmit} className="flex gap-2">
          <input
            value={manualCode}
            onChange={(e) => setManualCode(e.target.value)}
            placeholder="z.B. EAN oder Lagerort-Code"
          />
          <button type="submit" className="btn-secondary shrink-0">
            Suchen
          </button>
        </form>
      </section>
    </div>
  );
}
