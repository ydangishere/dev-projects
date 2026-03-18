import { NextResponse } from "next/server";
import db from "@/lib/db";

export async function POST() {
  const id = Date.now().toString();

  return new Promise<NextResponse>((resolve) => {
    db.run(
      "INSERT INTO orders (id, status) VALUES (?, ?)",
      [id, "pending"],
      (err) => {
        if (err) {
          resolve(NextResponse.json({ error: "Failed to create order" }, { status: 500 }));
          return;
        }
        resolve(
          NextResponse.json({
            paymentUrl: `/payment?id=${id}`,
          })
        );
      }
    );
  });
}
