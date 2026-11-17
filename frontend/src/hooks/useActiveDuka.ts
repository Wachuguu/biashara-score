"use client";
import { useEffect, useState } from "react";
import { PROFILE_EVENT, getActiveId, getActiveProfile, type Profile } from "@/utils/profile";

/** Reads the active duka from localStorage after mount (avoids hydration mismatch). */
export function useActiveDuka(): { ready: boolean; id: string | null; profile: Profile | null } {
  const [state, setState] = useState<{ ready: boolean; id: string | null; profile: Profile | null }>({
    ready: false,
    id: null,
    profile: null,
  });

  useEffect(() => {
    const sync = () => setState({ ready: true, id: getActiveId(), profile: getActiveProfile() });
    sync();
    window.addEventListener(PROFILE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(PROFILE_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return state;
}
