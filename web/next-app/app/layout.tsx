import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chakravyuh — Analyst Portal",
  description: "GenAI payment fraud detection — closed-loop demo",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
