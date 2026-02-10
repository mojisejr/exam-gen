import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = (await request.json()) as HandleUploadBody;
  const result = await handleUpload({
    request,
    body,
    onBeforeGenerateToken: async () => ({
      allowedContentTypes: ["application/pdf"],
      tokenPayload: JSON.stringify({
        scope: "exam-gen",
      }),
    }),
    onUploadCompleted: async () => undefined,
  });

  return NextResponse.json(result);
}
