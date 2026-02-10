import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { upload } from "@vercel/blob/client";

const APP_BASE_URL = process.env.APP_BASE_URL ?? "http://localhost:3000";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const DEFAULT_PDF_PATH = "/Users/non/dev/opilot/ψ/lab/exam-gen/data/input1.pdf";

const filePath = process.argv[2] ?? DEFAULT_PDF_PATH;
const questionCount = Number(process.argv[3] ?? 5);

async function uploadPdf(fileBuffer, filename) {
  const file = new File([fileBuffer], filename, { type: "application/pdf" });
  const result = await upload(filename, file, {
    access: "public",
    handleUploadUrl: `${APP_BASE_URL}/api/upload`,
  });
  return result.url;
}

async function cleanupBlob(url) {
  await fetch(`${APP_BASE_URL}/api/upload/cleanup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

async function analyzePdf(blobUrl) {
  const form = new FormData();
  form.append("file_url", blobUrl);
  form.append("instruction", "ขอข้อสอบแนววิเคราะห์");
  form.append("question_count", String(questionCount));
  form.append("language", "ไทย");
  form.append("exam_type", "auto");

  const response = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Analyze failed");
  }

  return response.json();
}

async function generateBatch(blobUrl, designBrief) {
  const form = new FormData();
  form.append("file_url", blobUrl);
  form.append("instruction", "ขอข้อสอบแนววิเคราะห์");
  form.append("question_count", String(questionCount));
  form.append("language", "ไทย");
  form.append("design_brief", designBrief);
  form.append("batch_info", "Batch 1/1");
  form.append("avoid_topics", "ไม่มี");
  form.append("exam_type", "auto");

  const response = await fetch(`${API_BASE_URL}/api/generate-batch`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? "Generate batch failed");
  }

  return response.json();
}

async function run() {
  const buffer = await readFile(filePath);
  const filename = basename(filePath);

  let blobUrl = null;
  try {
    console.log("Uploading to blob...", { filePath });
    blobUrl = await uploadPdf(buffer, filename);
    console.log("Blob URL:", blobUrl);

    console.log("Analyzing PDF...");
    const analyzeData = await analyzePdf(blobUrl);
    console.log("Analyze OK");

    console.log("Generating batch...");
    const batchData = await generateBatch(blobUrl, analyzeData.brief ?? "");
    const itemCount = batchData?.worksheet?.items?.length ?? 0;
    console.log("Generate batch OK", { itemCount });
  } finally {
    if (blobUrl) {
      try {
        console.log("Cleaning up blob...");
        await cleanupBlob(blobUrl);
        console.log("Cleanup OK");
      } catch (error) {
        console.warn("Cleanup failed", error);
      }
    }
  }
}

run().catch((error) => {
  console.error("Blob warp verification failed", error);
  process.exit(1);
});
