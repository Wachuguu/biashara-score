import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Biashara Score",
    short_name: "Biashara",
    description: "Know your shop's real profit, track customer debts, and get a lender-ready score.",
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#F6F7F2",
    theme_color: "#F2C230",
    lang: "en-KE",
    categories: ["business", "finance"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Customer Debts", short_name: "Debts", url: "/deni", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Import M-Pesa", short_name: "Import", url: "/import", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  };
}
