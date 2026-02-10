"use client";

import { useMemo, useRef, useState, useSyncExternalStore, type DragEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { FileText, Loader2, X } from "lucide-react";

type ExamType = "auto" | "multiple_choice" | "true_false" | "subjective";

type ExamItem = {
  id: number;
  question: string;
  type: "multiple_choice" | "true_false" | "subjective";
  options?: { label: string; text: string }[] | null;
  correct_answer: string;
  explanation?: string | null;
  image_prompt?: string | null;
};

type Worksheet = {
  title: string;
  subject: string;
  target_level: string;
  items: ExamItem[];
};

type BatchResponse = {
  worksheet: Worksheet;
  new_topics: string[];
};

const QUESTION_COUNT_OPTIONS = [10, 20, 30, 50];
const LANGUAGE_OPTIONS = ["ไทย", "English"] as const;
const EXAM_TYPE_OPTIONS: { value: ExamType; label: string }[] = [
  { value: "auto", label: "อัตโนมัติ (AI เลือกให้)" },
  { value: "multiple_choice", label: "เฉพาะปรนัย (Multiple Choice)" },
  { value: "true_false", label: "เฉพาะถูก/ผิด (True/False)" },
  { value: "subjective", label: "เฉพาะอัตนัย (Subjective)" },
];

function buildBatches(total: number, size: number) {
  const batches: number[] = [];
  let remaining = total;
  while (remaining > 0) {
    const batch = Math.min(size, remaining);
    batches.push(batch);
    remaining -= batch;
  }
  return batches;
}

function getApiBase() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");
}

function getApiUrl(path: string) {
  const base = getApiBase();
  return `${base}${path}`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [instruction, setInstruction] = useState("ขอข้อสอบแนววิเคราะห์");
  const [questionCount, setQuestionCount] = useState(50);
  const [language, setLanguage] = useState<(typeof LANGUAGE_OPTIONS)[number]>("ไทย");
  const [examType, setExamType] = useState<ExamType>("auto");
  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [status, setStatus] = useState("Idle");
  const [items, setItems] = useState<ExamItem[]>([]);
  const [preview, setPreview] = useState<string>("");
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [batchIndex, setBatchIndex] = useState(0);

  const batches = useMemo(() => buildBatches(questionCount, 10), [questionCount]);
  const progressPercent = useMemo(() => {
    if (batches.length === 0) return 0;
    return Math.round((batchIndex / batches.length) * 100);
  }, [batchIndex, batches.length]);

  const handleFileChange = (nextFile: File | null) => {
    setFile(nextFile);
    setItems([]);
    setPreview("");
    setDownloadUrl(null);
    setError(null);
    setBatchIndex(0);
  };

  const openFileDialog = () => {
    fileInputRef.current?.click();
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) handleFileChange(dropped);
  };

  const apiKey = useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined") return () => undefined;
      const handler = (event: Event) => {
        if (event instanceof StorageEvent) {
          if (event.key && event.key !== "gemini_api_key") return;
        }
        onStoreChange();
      };
      window.addEventListener("storage", handler);
      window.addEventListener("byok-storage", handler as EventListener);
      return () => {
        window.removeEventListener("storage", handler);
        window.removeEventListener("byok-storage", handler as EventListener);
      };
    },
    () => window.localStorage.getItem("gemini_api_key") ?? "",
    () => "",
  );

  const notifyApiKeyChange = () => {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new Event("byok-storage"));
  };

  const openKeyModal = () => {
    setApiKeyDraft(apiKey);
    setIsKeyModalOpen(true);
  };

  const saveApiKey = () => {
    const nextKey = apiKeyDraft.trim();
    if (nextKey) {
      window.localStorage.setItem("gemini_api_key", nextKey);
    } else {
      window.localStorage.removeItem("gemini_api_key");
    }
    notifyApiKeyChange();
    setIsKeyModalOpen(false);
  };

  const clearApiKey = () => {
    window.localStorage.removeItem("gemini_api_key");
    setApiKeyDraft("");
    notifyApiKeyChange();
    setIsKeyModalOpen(false);
  };

  const handleGenerate = async () => {
    if (!file) {
      setError("กรุณาอัปโหลดไฟล์ PDF ก่อนเริ่ม");
      return;
    }

    setError(null);
    setStatus("Analyzing PDF");
    setBatchIndex(0);
    setItems([]);
    setPreview("");
    setDownloadUrl(null);

    const analyzeForm = new FormData();
    analyzeForm.append("file", file);
    analyzeForm.append("instruction", instruction);
    analyzeForm.append("question_count", String(questionCount));
    analyzeForm.append("language", language);
    analyzeForm.append("exam_type", examType);

    const apiKeyValue = apiKey.trim();
    const authHeaders: Record<string, string> = apiKeyValue
      ? { "X-Gemini-API-Key": apiKeyValue }
      : {};

    const analyzeResponse = await fetch(getApiUrl("/api/analyze"), {
      method: "POST",
      body: analyzeForm,
      headers: authHeaders,
    });

    if (!analyzeResponse.ok) {
      const payload = await analyzeResponse.json().catch(() => ({}));
      setError(payload.detail ?? "วิเคราะห์เอกสารไม่สำเร็จ");
      setStatus("Failed");
      return;
    }

    const analyzeData = (await analyzeResponse.json()) as { brief: string };
    setStatus("Generating batches");

    const collectedItems: ExamItem[] = [];
    let avoidTopics: string[] = [];
    let worksheetMeta: Omit<Worksheet, "items"> | null = null;

    for (let index = 0; index < batches.length; index += 1) {
      const batchSize = batches[index];
      const generateForm = new FormData();
      generateForm.append("file", file);
      generateForm.append("instruction", instruction);
      generateForm.append("question_count", String(batchSize));
      generateForm.append("language", language);
      generateForm.append("design_brief", analyzeData.brief);
      generateForm.append("batch_info", `Batch ${index + 1}/${batches.length}`);
      generateForm.append("avoid_topics", avoidTopics.join(", ") || "ไม่มี");
      generateForm.append("exam_type", examType);

      const batchResponse = await fetch(getApiUrl("/api/generate-batch"), {
        method: "POST",
        body: generateForm,
        headers: authHeaders,
      });

      if (!batchResponse.ok) {
        const payload = await batchResponse.json().catch(() => ({}));
        setError(payload.detail ?? "เจนข้อสอบบางรอบไม่สำเร็จ");
        setStatus("Failed");
        return;
      }

      const batchData = (await batchResponse.json()) as BatchResponse;
      if (!worksheetMeta) {
        const { title, subject, target_level } = batchData.worksheet;
        worksheetMeta = { title, subject, target_level };
      }
      collectedItems.push(...batchData.worksheet.items);
      avoidTopics = [...avoidTopics, ...batchData.new_topics];
      setItems([...collectedItems]);
      setPreview(JSON.stringify(batchData.worksheet.items, null, 2));
      setBatchIndex(index + 1);
    }

    if (!worksheetMeta) {
      setError("ไม่พบข้อมูล metadata จากการเจนข้อสอบ");
      setStatus("Failed");
      return;
    }

    setStatus("Rendering DOCX");
    const renderResponse = await fetch(getApiUrl("/api/render-docx"), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({
        worksheet: {
          ...worksheetMeta,
          items: collectedItems,
        },
      }),
    });

    if (!renderResponse.ok) {
      const payload = await renderResponse.json().catch(() => ({}));
      setError(payload.detail ?? "เรนเดอร์ไฟล์ไม่สำเร็จ");
      setStatus("Failed");
      return;
    }

    const blob = await renderResponse.blob();
    const url = URL.createObjectURL(blob);
    setDownloadUrl(url);
    setStatus("Done");
  };

  const isBusy = status !== "Idle" && status !== "Done" && status !== "Failed";
  const hasApiKey = apiKey.trim().length > 0;
  const currentBatchLabel =
    batches.length > 0
      ? Math.min(Math.max(batchIndex + 1, 1), batches.length)
      : 0;
  const buttonLabel = (() => {
    switch (status) {
      case "Analyzing PDF":
        return "Analyzing...";
      case "Generating batches":
        return batches.length > 0
          ? `Generating batch ${currentBatchLabel}/${batches.length}`
          : "Generating batches...";
      case "Rendering DOCX":
        return "Rendering DOCX...";
      case "Failed":
        return "Try Again";
      case "Done":
        return "Generate Again";
      default:
        return "Start Generation";
    }
  })();

  return (
    <div className="min-h-screen">
      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-12">
        <section className="glass-panel p-8">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <Badge variant="secondary">AI Exam Generator</Badge>
              <Badge variant="outline">Session 2: UI Mastery</Badge>
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
              Exam Gen Dashboard
            </h1>
            <p className="text-sm text-zinc-600">
              สร้างข้อสอบจาก PDF ด้วย AI แบบ Batch Orchestration พร้อม Preview และดาวน์โหลดไฟล์
            </p>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>Generator Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div
                className="glass-panel-dark flex min-h-[140px] cursor-pointer flex-col items-center justify-center gap-2 border-dashed text-center"
                onDrop={handleDrop}
                onDragOver={(event) => event.preventDefault()}
                onClick={() => {
                  if (!file) openFileDialog();
                }}
                onKeyDown={(event) => {
                  if (!file && (event.key === "Enter" || event.key === " ")) {
                    event.preventDefault();
                    openFileDialog();
                  }
                }}
                role="button"
                tabIndex={0}
              >
                {file ? (
                  <div className="flex w-full items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/70 p-3 text-left shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-zinc-700 shadow-sm">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-zinc-800">{file.name}</p>
                        <p className="text-xs text-zinc-500">PDF attached</p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="Remove file"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleFileChange(null);
                        if (fileInputRef.current) {
                          fileInputRef.current.value = "";
                        }
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-zinc-700">
                      ลากไฟล์ PDF มาวาง หรือคลิกที่นี่เพื่อเลือกไฟล์
                    </p>
                    <p className="text-xs text-zinc-500">รองรับเฉพาะไฟล์ .pdf</p>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="sr-only"
                  onChange={(event) =>
                    handleFileChange(event.target.files?.[0] ?? null)
                  }
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-zinc-600">จำนวนข้อ</label>
                  <div className="flex flex-wrap gap-2">
                    {QUESTION_COUNT_OPTIONS.map((count) => (
                      <Button
                        key={count}
                        type="button"
                        variant={count === questionCount ? "default" : "outline"}
                        size="sm"
                        onClick={() => setQuestionCount(count)}
                      >
                        {count} ข้อ
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-zinc-600">ภาษา</label>
                  <div className="flex flex-wrap gap-2">
                    {LANGUAGE_OPTIONS.map((option) => (
                      <Button
                        key={option}
                        type="button"
                        variant={option === language ? "default" : "outline"}
                        size="sm"
                        onClick={() => setLanguage(option)}
                      >
                        {option}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-600">รูปแบบข้อสอบ</label>
                <select
                  className="border-input bg-transparent text-zinc-900 shadow-xs focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] h-9 w-full rounded-md border px-3 text-sm"
                  value={examType}
                  onChange={(event) => setExamType(event.target.value as ExamType)}
                >
                  {EXAM_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-600">Instruction</label>
                <Textarea
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  rows={4}
                />
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-zinc-600">Gemini API Key</label>
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/70 p-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-zinc-800">
                      {hasApiKey ? "API Key stored" : "No API Key yet"}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {hasApiKey
                        ? "กำลังใช้ Key ส่วนตัวสำหรับการประมวลผล"
                        : "บันทึก Key ส่วนตัวเพื่อใช้งานแบบ BYOK"}
                    </p>
                  </div>
                  <Button type="button" variant="outline" size="sm" onClick={openKeyModal}>
                    {hasApiKey ? "Update Key" : "Add Key"}
                  </Button>
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <Button onClick={handleGenerate} size="lg" disabled={isBusy} className="gap-2">
                  {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
                  <span>{buttonLabel}</span>
                </Button>
                {error && <p className="text-sm text-red-500">{error}</p>}
              </div>
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardTitle>Batch Progress</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-zinc-600">
                  <span>Status: {status}</span>
                  <span>
                    {batchIndex}/{batches.length} batches
                  </span>
                </div>
                <Progress value={progressPercent} />
              </div>

              <div className="flex flex-wrap gap-2">
                {batches.map((_, index) => (
                  <Badge
                    key={`batch-${index}`}
                    variant={index < batchIndex ? "default" : "outline"}
                  >
                    Batch {index + 1}
                  </Badge>
                ))}
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium text-zinc-600">Live Preview</p>
                <div className="glass-panel-dark max-h-[320px] overflow-auto p-3 text-[11px] text-zinc-700">
                  {preview ? (
                    <pre className="whitespace-pre-wrap">{preview}</pre>
                  ) : (
                    <p className="text-zinc-500">
                      ผลลัพธ์จากแต่ละ Batch จะถูกแสดงที่นี่
                    </p>
                  )}
                </div>
              </div>

              {downloadUrl && (
                <Button asChild variant="secondary">
                  <a href={downloadUrl} download="worksheet.docx">
                    Download DOCX
                  </a>
                </Button>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="glass-panel p-6">
          <div className="flex flex-col gap-2 text-sm text-zinc-600">
            <p className="font-semibold text-zinc-700">Generated Items</p>
            <p>รวมทั้งหมด: {items.length} ข้อ</p>
          </div>
        </section>
      </main>
      {isKeyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-8">
          <div className="glass-panel w-full max-w-lg rounded-2xl p-6 shadow-2xl">
            <div className="space-y-2">
              <h2 className="text-xl font-semibold text-zinc-900">Gemini API Key</h2>
              <p className="text-sm text-zinc-600">
                Key นี้จะถูกบันทึกไว้บนเบราว์เซอร์ของคุณเท่านั้น
              </p>
            </div>
            <div className="mt-4 space-y-2">
              <label className="text-xs font-medium text-zinc-600">API Key</label>
              <Input
                type="password"
                placeholder="ใส่ Gemini API Key"
                value={apiKeyDraft}
                onChange={(event) => setApiKeyDraft(event.target.value)}
              />
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              {hasApiKey && (
                <Button type="button" variant="ghost" onClick={clearApiKey}>
                  Remove Key
                </Button>
              )}
              <Button type="button" variant="ghost" onClick={() => setIsKeyModalOpen(false)}>
                Cancel
              </Button>
              <Button type="button" onClick={saveApiKey}>
                Save Key
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
