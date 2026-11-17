"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getActiveId } from "@/utils/profile";
import { LoadingBlock } from "@/components/StateViews";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getActiveId() ? "/dashboard" : "/setup");
  }, [router]);
  return <LoadingBlock label="Opening your duka" />;
}
