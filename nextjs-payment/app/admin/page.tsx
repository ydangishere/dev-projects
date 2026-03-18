"use client";

import Link from "next/link";
import { useState } from "react";

type Order = { id: string; status: string };

export default function AdminPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const viewOrders = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/orders", {
        headers: { Authorization: "Bearer admin123" },
      });
      if (!res.ok) {
        setError("Unauthorized. Admin token required.");
        setOrders([]);
        return;
      }
      const data = await res.json();
      setOrders(data);
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center gap-6 bg-zinc-50 p-10 dark:bg-zinc-900">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        Admin – View DB
      </h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        This page sends admin token when calling API. Only valid token can view orders.
      </p>
      <div className="flex gap-4">
        <button
          onClick={viewOrders}
          disabled={loading}
          className="rounded-lg bg-zinc-900 px-6 py-3 font-medium text-white hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          {loading ? "Loading..." : "View Orders"}
        </button>
        <Link
          href="/"
          className="rounded-lg border border-zinc-300 px-6 py-3 font-medium hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-800"
        >
          Return
        </Link>
      </div>
      {error && (
        <p className="rounded-lg bg-red-100 px-4 py-2 text-red-700 dark:bg-red-900/30 dark:text-red-400">
          {error}
        </p>
      )}
      {orders.length > 0 && (
        <table className="w-full max-w-md border border-zinc-200 dark:border-zinc-700">
          <thead>
            <tr className="bg-zinc-100 dark:bg-zinc-800">
              <th className="border-b p-2 text-left">ID</th>
              <th className="border-b p-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} className="border-b dark:border-zinc-700">
                <td className="p-2">{o.id}</td>
                <td className="p-2 capitalize">{o.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
