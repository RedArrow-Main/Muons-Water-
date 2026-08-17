import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FurrowCast - Agricultural Advisory",
  description: "County-level planting-window and water-budget advisories",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 font-mono antialiased">
        {children}
      </body>
    </html>
  );
}