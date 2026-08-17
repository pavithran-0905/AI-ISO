import type { Metadata } from "next";
import { JetBrains_Mono, Inter } from "next/font/google";

import { AppProviders } from "@/providers/app-providers";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "AI-IOS",
  description: "AI Infrastructure Operating System",
};

/**
 * The root Next.js layout: HTML shell and app-wide providers only. The
 * visible chrome (nav/header/footer) is applied per route group — see
 * `app/(app)/layout.tsx` (`MainLayout`) — so route groups that need a
 * different shell (e.g. a future `(auth)` group with `AuthLayout`) don't
 * inherit navigation they shouldn't render. See
 * docs/frontend/architecture/routing.md.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
