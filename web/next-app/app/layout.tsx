import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chakravyuh — Payment Fraud Defence Lab",
  description: "GenAI payment-fraud simulation and decision-time defence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
