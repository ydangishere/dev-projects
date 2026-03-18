"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

function ResultContent() {
  const params = useSearchParams();
  const id = params.get("id");
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    if (!id) return;
    fetch(`/api/get-status?id=${id}`)
      .then((res) => res.json())
      .then((data) => setStatus(data.status));
  }, [id]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-zinc-50 p-10 dark:bg-zinc-900">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        Payment Result
      </h1>
      <p className="text-zinc-600 dark:text-zinc-400">Order ID: {id}</p>
      <p className="text-lg font-medium">
        Status: <span className="capitalize">{status}</span>
      </p>
      <Link
        href="/"
        className="rounded-lg bg-zinc-900 px-6 py-3 font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        Return
      </Link>
    </div>
  );
}

export default function ResultPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading...</div>}>
      <ResultContent />
    </Suspense>
  );
}
