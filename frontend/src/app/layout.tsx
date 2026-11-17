import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible, Big_Shoulders_Display } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { Providers } from "@/components/Providers";
import { ServiceWorker } from "@/components/ServiceWorker";

const display = Big_Shoulders_Display({ subsets: ["latin"], weight: ["700", "800", "900"], variable: "--font-display", display: "swap" });
const body = Atkinson_Hyperlegible({ subsets: ["latin"], weight: ["400", "700"], variable: "--font-body", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Biashara Score", template: "%s · Biashara Score" },
  description: "Know your duka's real profit, track Kitabu ya Deni, and get a lender-ready Biashara Score.",
  applicationName: "Biashara Score",
  appleWebApp: { capable: true, title: "Biashara", statusBarStyle: "default" },
  icons: {
    icon: [
      { url: "/icons/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#F2C230",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable}`}>
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
        <ServiceWorker />
      </body>
    </html>
  );
}
