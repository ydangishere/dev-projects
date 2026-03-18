import { NextResponse } from "next/server";
import db from "@/lib/db";

export async function POST(req: Request) {
  const body = await req.json();
  const { id, status, signature } = body;

  if (signature !== "secret123") {
    return NextResponse.json({ error: "invalid signature" }, { status: 400 });
  }

  return new Promise<NextResponse>((resolve) => {
    db.get(
      "SELECT status FROM orders WHERE id = ?",
      [id],
      (err, row: { status?: string } | undefined) => {
        if (err) {
          resolve(NextResponse.json({ error: "Database error" }, { status: 500 }));
          return;
        }
        if (!row || row.status !== "pending") {
          resolve(NextResponse.json({ ok: true }));
          return;
        }

        db.run(
          "UPDATE orders SET status = ? WHERE id = ?",
          [status, id],
          (updateErr) => {
            if (updateErr) {
              resolve(NextResponse.json({ error: "Update failed" }, { status: 500 }));
              return;
            }
            resolve(NextResponse.json({ ok: true }));
          }
        );
      }
    );
  });
}
