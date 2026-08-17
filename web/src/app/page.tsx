"use client";

import Link from "next/link";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md w-full text-center p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">
          FurrowCast
        </h1>
        <p className="text-gray-600 mb-6">
          County-level planting-window &amp; water-budget advisories
        </p>
        <Link
          href="/dashboard"
          className="inline-block bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}