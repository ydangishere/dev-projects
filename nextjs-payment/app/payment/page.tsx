"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

function PaymentContent() {
  const params = useSearchParams();
  const id = params.get("id");

  const handle = async (status: string) => {
    await fetch("/api/callback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id,
        status,
        signature: "secret123",
      }),
    });
    window.location.href = `/result?id=${id}`;
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 p-10 dark:bg-zinc-900">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        Fake Payment Gateway
      </h1>
      <p className="text-zinc-600 dark:text-zinc-400">Order ID: {id}</p>
      <div className="flex gap-4">
        <button
          onClick={() => handle("success")}
          className="rounded-lg bg-green-600 px-6 py-3 font-medium text-white transition-colors hover:bg-green-700"
        >
          Success
        </button>
        <button
          onClick={() => handle("fail")}
          className="rounded-lg bg-red-600 px-6 py-3 font-medium text-white transition-colors hover:bg-red-700"
        >
          Fail
        </button>
      </div>
    </div>
  );
}

export default function PaymentPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading...</div>}>
      <PaymentContent />
    </Suspense>
  );
}
