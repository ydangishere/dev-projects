"use client";

export default function Home() {
  const pay = async () => {
    const res = await fetch("/api/create-payment", {
      method: "POST",
    });
    const data = await res.json();
    window.location.href = data.paymentUrl;
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-900">
      <main className="flex flex-col items-center gap-6 p-10">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Mini Payment Demo
        </h1>
        <button
          onClick={pay}
          className="rounded-lg bg-zinc-900 px-6 py-3 font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Pay Now
        </button>
      </main>
    </div>
  );
}
