import type { Metadata } from "next";
import "./globals.css";
import { SignInModal } from "@/components/auth/SignInModal";
import { UploadModal } from "@/components/upload/UploadModal";

export const metadata: Metadata = {
  title: "ADV — Agentic Drawing Validator · Mechanical GA ↔ Structural GA",
  description:
    "DWG-native, rule-grounded, sheet-locatable drawing validation. Every finding traces to a sheet, a gridline, an element, and an exact formula.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Fraunces:opsz,wght@9..144,500;9..144,700&display=swap"
        />
      </head>
      <body>
        {children}
        <SignInModal />
        <UploadModal />
      </body>
    </html>
  );
}
