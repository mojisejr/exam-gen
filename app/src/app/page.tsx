"use client";

import { useMemo, useState, type DragEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";

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
  const [instruction, setInstruction] = useState("ขอข้อสอบแนววิเคราะห์");
  const [questionCount, setQuestionCount] = useState(50);
  const [language, setLanguage] = useState<(typeof LANGUAGE_OPTIONS)[number]>("ไทย");
  const [examType, setExamType] = useState<ExamType>("auto");
  const [status, setStatus] = useState("Idle");
  const [brief, setBrief] = useState<string | null>(null);
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
    setBrief(null);
    setItems([]);
    setPreview("");
    setDownloadUrl(null);
    setError(null);
    setBatchIndex(0);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const dropped = event.dataTransfer.files?.[0] ?? null;
    if (dropped) handleFileChange(dropped);
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

    const analyzeResponse = await fetch(getApiUrl("/api/analyze"), {
      method: "POST",
      body: analyzeForm,
    });

    if (!analyzeResponse.ok) {
      const payload = await analyzeResponse.json().catch(() => ({}));
      setError(payload.detail ?? "วิเคราะห์เอกสารไม่สำเร็จ");
      setStatus("Failed");
      return;
    }

    const analyzeData = (await analyzeResponse.json()) as { brief: string };
    setBrief(analyzeData.brief);
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
      headers: { "Content-Type": "application/json" },
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
                className="glass-panel-dark flex min-h-[140px] flex-col items-center justify-center gap-2 border-dashed text-center"
                onDrop={handleDrop}
                onDragOver={(event) => event.preventDefault()}
              >
                <p className="text-sm text-zinc-700">
                  ลากไฟล์ PDF มาวาง หรือเลือกไฟล์ด้านล่าง
                </p>
                <Input
                  type="file"
                  accept="application/pdf"
                  onChange={(event) =>
                    handleFileChange(event.target.files?.[0] ?? null)
                  }
                />
                {file && (
                  <p className="text-xs text-zinc-500">ไฟล์: {file.name}</p>
                )}
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

              <div className="flex flex-col gap-3">
                <Button onClick={handleGenerate} size="lg">
                  Start Generation
                </Button>
                {error && <p className="text-sm text-red-500">{error}</p>}
                {brief && (
                  <div className="glass-panel-dark p-3 text-xs text-zinc-700">
                    <p className="font-semibold">Design Brief</p>
                    <p className="whitespace-pre-line">{brief}</p>
                  </div>
                )}
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
    </div>
  );
}
