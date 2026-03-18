import { NextResponse } from "next/server";
import db from "@/lib/db";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");

  return new Promise<NextResponse>((resolve) => {
    db.get(
      "SELECT status FROM orders WHERE id = ?",
      [id],
      (err, row: { status?: string } | undefined) => {
        resolve(
          NextResponse.json({ status: row?.status || "unknown" })
        );
      }
    );
  });
}
