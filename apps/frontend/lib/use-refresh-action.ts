"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

/**
 * The shared "manual refresh" behavior every data-heavy page needs
 * (Dashboard Prompt 005 §32, Monitoring Prompt 006 §22): re-fetch every
 * active query, track a loading state for the refresh control, and
 * record when it last completed. Extracted here once a second page
 * (Monitoring) needed the exact same three lines Dashboard already had.
 */
export function useRefreshAction() {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string>(() => new Date().toISOString());

  async function refresh() {
    setIsRefreshing(true);
    await queryClient.invalidateQueries();
    setLastRefreshedAt(new Date().toISOString());
    setIsRefreshing(false);
  }

  return { refresh, isRefreshing, lastRefreshedAt };
}
