"use client";
import { WifiOff } from "lucide-react";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/StateViews";

export default function OfflinePage() {
  return (
    <div className="panel mt-8">
      <EmptyState
        icon={WifiOff}
        title="No connection"
        body="Biashara Score needs data to load your shop. Check your bundles or Wi-Fi."
        action={<Button onClick={() => window.location.reload()}>Try again</Button>}
      />
    </div>
  );
}
