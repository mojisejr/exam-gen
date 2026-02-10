import { del } from "@vercel/blob";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

type CleanupRequest = {
  url?: string;
  urls?: string[];
};

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as CleanupRequest;
  const targets = body.urls ?? (body.url ? [body.url] : []);

  if (targets.length === 0) {
    return NextResponse.json(
      { error: "Missing blob url" },
      { status: 400 },
    );
  }

  await del(targets);
  return NextResponse.json({ status: "ok", deleted: targets.length });
}
