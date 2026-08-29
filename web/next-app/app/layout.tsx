import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Chakravyuh — Payment Fraud Defence Lab",
  description: "GenAI payment-fraud simulation and decision-time defence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable}`}>
      <body className="bg-[#0B0B0C] text-[#EDEDEF] min-h-screen antialiased font-sans selection:bg-[#D9500B]/30 selection:text-orange-200">
        {children}
      </body>
    </html>
  );
}

