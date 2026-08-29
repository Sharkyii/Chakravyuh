import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chakravyuh — Payment Fraud Defence Lab",
  description: "GenAI payment-fraud simulation and decision-time defence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#08090b] text-zinc-100 min-h-screen antialiased selection:bg-orange-500/30 selection:text-orange-200">
        {children}
      </body>
    </html>
  );
}

