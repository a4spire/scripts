"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError, Category, Item, Location, Project } from "@/lib/api";

type CreateItemOp = {
  kind: "create_item";
  name: string;
  description: string | null;
  manufacturer: string | null;
  specs: Record<string, unknown> | null;
  unit: string;
  categoryId: string | null;
  locationId: string | null;
  minQuantity: number;
  initialQuantity: number | null;
  usePendingPhoto?: boolean;
  barcode?: string | null;
};

type BookMovementOp = {
  kind: "book_movement";
  itemId: string;
  movementType: "IN" | "OUT" | "RETURN" | "CORRECTION";
  quantity: number;
  projectId: string | null;
  reason: string | null;
};

type Op = CreateItemOp | BookMovementOp;

interface TextActionResponse {
  type: "create_item" | "book_movement";
  item?: {
    name: string;
    categoryName?: string | null;
    description?: string | null;
    manufacturer?: string | null;
    specs?: Record<string, unknown> | null;
    unit: string;
  };
  locationName?: string | null;
  initialQuantity?: number | null;
  itemId?: string | null;
  itemName?: string;
  movementType?: "IN" | "OUT" | "RETURN" | "CORRECTION";
  quantity?: number;
  projectName?: string | null;
  reason?: string | null;
}

interface CaptureResponse {
  capture: { id: string };
  proposal: {
    summary?: string;
    action?: "create_item";
    item?: {
      name: string;
      categoryName?: string | null;
      description?: string | null;
      manufacturer?: string | null;
      specs?: Record<string, unknown> | null;
      unit: string;
    };
    confidence?: number;
    actions?: TextActionResponse[];
  };
  transcript?: string;
}

const RECORDER_MIME_TYPES = ["audio/webm", "audio/ogg", "audio/mp4"];

function pickSupportedMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  return RECORDER_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

function findIdByName<T extends { id: string; name: string }>(list: T[], name?: string | null) {
  if (!name) return null;
  const match = list.find((x) => x.name.toLowerCase() === name.toLowerCase());
  return match?.id ?? null;
}

function mapActionsToOps(
  actions: TextActionResponse[],
  categories: Category[],
  locations: Location[],
  projects: Project[],
  items: Item[],
  pendingBarcode: string | null
): Op[] {
  return actions.map((a): Op => {
    if (a.type === "create_item" && a.item) {
      return {
        kind: "create_item",
        name: a.item.name,
        description: a.item.description ?? null,
        manufacturer: a.item.manufacturer ?? null,
        specs: a.item.specs ?? null,
        unit: a.item.unit ?? "Stk",
        categoryId: findIdByName(categories, a.item.categoryName),
        locationId: findIdByName(locations, a.locationName),
        minQuantity: 0,
        initialQuantity: a.initialQuantity ?? null,
        barcode: pendingBarcode,
      };
    }
    return {
      kind: "book_movement",
      itemId: a.itemId ?? findIdByName(items, a.itemName) ?? "",
      movementType: a.movementType ?? "OUT",
      quantity: a.quantity ?? 1,
      projectId: findIdByName(projects, a.projectName),
      reason: a.reason ?? null,
    };
  });
}

function CapturePageContent() {
  const searchParams = useSearchParams();
  const pendingBarcode = searchParams.get("barcode");

  const [categories, setCategories] = useState<Category[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [items, setItems] = useState<Item[]>([]);

  const [text, setText] = useState("");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [captureId, setCaptureId] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [ops, setOps] = useState<Op[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const [recordingState, setRecordingState] = useState<"idle" | "recording" | "recorded">("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.get<Category[]>("/api/categories").then(setCategories);
    api.get<Location[]>("/api/locations").then(setLocations);
    api.get<Project[]>("/api/projects?status=ACTIVE").then(setProjects);
    api.get<Item[]>("/api/items").then(setItems);
  }, []);

  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) clearInterval(recordingIntervalRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl]);

  function reset() {
    setCaptureId(null);
    setSummary(null);
    setOps([]);
    setDone(null);
    setError(null);
    setTranscript(null);
  }

  async function handleTextSubmit(e: React.FormEvent) {
    e.preventDefault();
    reset();
    setBusy(true);
    try {
      const res = await api.post<CaptureResponse>("/api/ai/text", { text });
      setCaptureId(res.capture.id);
      setSummary(res.proposal.summary ?? null);
      setOps(mapActionsToOps(res.proposal.actions ?? [], categories, locations, projects, items, pendingBarcode));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erfassung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handlePhotoSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!photoFile) return;
    reset();
    setBusy(true);
    try {
      const body = new FormData();
      body.append("file", photoFile);
      const res = await api.post<CaptureResponse>("/api/ai/photo", body);
      setCaptureId(res.capture.id);
      const item = res.proposal.item!;
      setOps([
        {
          kind: "create_item",
          name: item.name,
          description: item.description ?? null,
          manufacturer: item.manufacturer ?? null,
          specs: item.specs ?? null,
          unit: item.unit ?? "Stk",
          categoryId: findIdByName(categories, item.categoryName),
          locationId: null,
          minQuantity: 0,
          initialQuantity: null,
          usePendingPhoto: true,
          barcode: pendingBarcode,
        },
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Foto-Erkennung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    if (!captureId) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/ai/captures/${captureId}/confirm`, { operations: ops });
      setDone("Übernommen — Bestand/Artikel wurde aktualisiert.");
      setOps([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bestätigen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    if (!captureId) return;
    await api.post(`/api/ai/captures/${captureId}/reject`);
    reset();
    setText("");
    setPhotoFile(null);
    discardRecording();
  }

  function discardRecording() {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingState("idle");
    setRecordingSeconds(0);
  }

  async function startRecording() {
    setError(null);
    discardRecording();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickSupportedMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recordedChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(recordedChunksRef.current, { type: mimeType ?? recorder.mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setRecordingState("recorded");
        if (recordingIntervalRef.current) {
          clearInterval(recordingIntervalRef.current);
          recordingIntervalRef.current = null;
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecordingState("recording");
      setRecordingSeconds(0);
      recordingIntervalRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch {
      setError(
        "Mikrofon konnte nicht gestartet werden. Bitte Berechtigung erlauben (erfordert HTTPS oder localhost)."
      );
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
  }

  async function handleVoiceSubmit() {
    if (!audioBlob) return;
    reset();
    setBusy(true);
    try {
      const body = new FormData();
      const extension = audioBlob.type.includes("ogg") ? "ogg" : audioBlob.type.includes("mp4") ? "mp4" : "webm";
      body.append("file", audioBlob, `sprachnotiz.${extension}`);
      const res = await api.post<CaptureResponse>("/api/ai/voice", body);
      setCaptureId(res.capture.id);
      setSummary(res.proposal.summary ?? null);
      setTranscript(res.transcript ?? null);
      setOps(mapActionsToOps(res.proposal.actions ?? [], categories, locations, projects, items, pendingBarcode));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sprachnotiz-Verarbeitung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">KI-Erfassung</h1>
      <p className="text-sm text-gray-500">
        Nichts wird gebucht, bevor du den Vorschlag unten geprüft und bestätigt hast.
      </p>

      {pendingBarcode && (
        <p className="text-sm bg-blue-50 text-blue-800 rounded-md px-3 py-2">
          Unbekannter gescannter Code <span className="font-mono">{pendingBarcode}</span> — wird bei
          Anlage des neuen Artikels automatisch als Barcode übernommen.
        </p>
      )}

      <section className="card space-y-3">
        <h2 className="font-medium">Freitext-Eingabe</h2>
        <form onSubmit={handleTextSubmit} className="space-y-3">
          <textarea
            placeholder='z.B. "10x M4 Schrauben 20mm ins Regal A3" oder "3x Kabelbinder für Projekt Bühnenbau X entnommen"'
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
          />
          <button type="submit" className="btn" disabled={busy || !text}>
            {busy ? "Verarbeitet…" : "Analysieren"}
          </button>
        </form>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Foto-Erfassung</h2>
        <form onSubmit={handlePhotoSubmit} className="space-y-3">
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => setPhotoFile(e.target.files?.[0] ?? null)}
          />
          <button type="submit" className="btn" disabled={busy || !photoFile}>
            {busy ? "Analysiert…" : "Foto analysieren"}
          </button>
        </form>
      </section>

      <section className="card space-y-3">
        <h2 className="font-medium">Sprachnotiz</h2>
        <div className="flex items-center gap-3">
          {recordingState === "idle" && (
            <button type="button" className="btn" onClick={startRecording}>
              Aufnahme starten
            </button>
          )}
          {recordingState === "recording" && (
            <>
              <button type="button" className="btn" onClick={stopRecording}>
                Aufnahme stoppen
              </button>
              <span className="text-sm text-red-600">● {recordingSeconds}s</span>
            </>
          )}
          {recordingState === "recorded" && audioUrl && (
            <>
              <audio controls src={audioUrl} className="h-9" />
              <button type="button" className="btn" onClick={handleVoiceSubmit} disabled={busy}>
                {busy ? "Verarbeitet…" : "Analysieren"}
              </button>
              <button type="button" className="btn-secondary" onClick={discardRecording} disabled={busy}>
                Neu aufnehmen
              </button>
            </>
          )}
        </div>
        {transcript && (
          <p className="text-sm text-gray-500">
            Transkript: <span className="italic">„{transcript}“</span>
          </p>
        )}
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {done && <p className="text-sm text-green-700">{done}</p>}

      {ops.length > 0 && (
        <section className="card space-y-4">
          <h2 className="font-medium">Vorschlag prüfen {summary && `— ${summary}`}</h2>
          {ops.map((op, idx) =>
            op.kind === "create_item" ? (
              <div key={idx} className="border rounded-md p-3 space-y-2">
                <p className="text-xs uppercase text-gray-400">Neuer Artikel</p>
                <input
                  value={op.name}
                  onChange={(e) => updateOp(idx, { ...op, name: e.target.value })}
                  placeholder="Name"
                />
                <textarea
                  value={op.description ?? ""}
                  onChange={(e) => updateOp(idx, { ...op, description: e.target.value })}
                  placeholder="Beschreibung"
                />
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={op.categoryId ?? ""}
                    onChange={(e) => updateOp(idx, { ...op, categoryId: e.target.value || null })}
                  >
                    <option value="">– keine Kategorie –</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  <select
                    value={op.locationId ?? ""}
                    onChange={(e) => updateOp(idx, { ...op, locationId: e.target.value || null })}
                  >
                    <option value="">– kein Lagerort –</option>
                    {locations.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    placeholder="Erstbestand"
                    value={op.initialQuantity ?? ""}
                    onChange={(e) =>
                      updateOp(idx, {
                        ...op,
                        initialQuantity: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                  <input
                    placeholder="Einheit"
                    value={op.unit}
                    onChange={(e) => updateOp(idx, { ...op, unit: e.target.value })}
                  />
                </div>
                <input
                  placeholder="Barcode (optional)"
                  value={op.barcode ?? ""}
                  onChange={(e) => updateOp(idx, { ...op, barcode: e.target.value || null })}
                />
              </div>
            ) : (
              <div key={idx} className="border rounded-md p-3 space-y-2">
                <p className="text-xs uppercase text-gray-400">Bestandsbewegung</p>
                <select
                  value={op.itemId}
                  onChange={(e) => updateOp(idx, { ...op, itemId: e.target.value })}
                >
                  <option value="">– Artikel wählen –</option>
                  {items.map((it) => (
                    <option key={it.id} value={it.id}>
                      {it.name}
                    </option>
                  ))}
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={op.movementType}
                    onChange={(e) => updateOp(idx, { ...op, movementType: e.target.value as never })}
                  >
                    <option value="IN">Wareneingang</option>
                    <option value="OUT">Entnahme</option>
                    <option value="RETURN">Rückgabe</option>
                    <option value="CORRECTION">Korrektur</option>
                  </select>
                  <input
                    type="number"
                    value={op.quantity}
                    onChange={(e) => updateOp(idx, { ...op, quantity: Number(e.target.value) })}
                  />
                </div>
                {op.movementType === "OUT" && (
                  <select
                    value={op.projectId ?? ""}
                    onChange={(e) => updateOp(idx, { ...op, projectId: e.target.value || null })}
                  >
                    <option value="">– kein Projekt / allgemein –</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )
          )}
          <div className="flex gap-2">
            <button className="btn" onClick={handleConfirm} disabled={busy}>
              Bestätigen &amp; speichern
            </button>
            <button className="btn-secondary" onClick={handleReject} disabled={busy}>
              Verwerfen
            </button>
          </div>
        </section>
      )}
    </div>
  );

  function updateOp(idx: number, next: Op) {
    setOps((prev) => prev.map((o, i) => (i === idx ? next : o)));
  }
}

export default function CapturePage() {
  return (
    <Suspense fallback={<p>Lädt…</p>}>
      <CapturePageContent />
    </Suspense>
  );
}
