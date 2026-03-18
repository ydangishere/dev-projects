import { NextResponse } from "next/server";
import db from "@/lib/db";

const ADMIN_TOKEN = "admin123";

export async function GET(req: Request) {
  const auth = req.headers.get("Authorization");
  if (auth !== `Bearer ${ADMIN_TOKEN}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  return new Promise<NextResponse>((resolve) => {
    db.all("SELECT * FROM orders ORDER BY id DESC", [], (err, rows) => {
      if (err) {
        resolve(NextResponse.json({ error: "Database error" }, { status: 500 }));
        return;
      }
      resolve(NextResponse.json(rows || []));
    });
  });
}
