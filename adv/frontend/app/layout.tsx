import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ADV — Agentic Drawing Validator",
  description:
    "DWG-native, rule-grounded, sheet-locatable drawing validation. No confidence percentages.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
