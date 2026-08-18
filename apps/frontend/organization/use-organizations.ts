"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { organizationApi } from "@/organization/api";
import { useOrganizationStore } from "@/organization/store";

export function useOrganizations() {
  return useQuery({
    queryKey: ["organizations"],
    queryFn: organizationApi.list,
    staleTime: 5 * 60_000,
  });
}

export interface SelectedOrganizationResult {
  organizations: ReturnType<typeof useOrganizations>["data"];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  /** The organization the dashboard should show data for — only set
   * once resolved (auto-selected or explicitly chosen). */
  selectedOrganizationId: string | null;
  /** True once the list has loaded and the user has more than one
   * organization with none chosen yet — render a picker. */
  needsSelection: boolean;
  /** True once the list has loaded and is empty — the user has no
   * organization to show data for at all. */
  hasNoAccess: boolean;
}

/**
 * Resolves which organization's data to show (`@/organization/store`'s
 * own docstring explains why this exists at all): auto-selects when
 * exactly one organization is available, otherwise leaves
 * `selectedOrganizationId` `null` and sets `needsSelection` so the
 * caller can render `OrganizationPicker`. Never guesses when there's
 * a genuine choice to make.
 */
export function useSelectedOrganization(): SelectedOrganizationResult {
  const query = useOrganizations();
  const storedId = useOrganizationStore((state) => state.selectedOrganizationId);
  const setSelectedOrganizationId = useOrganizationStore((state) => state.setSelectedOrganizationId);

  const organizations = query.data;
  const hasNoAccess = organizations !== undefined && organizations.length === 0;

  const storedIsValid = organizations !== undefined && storedId !== null && organizations.some((org) => org.id === storedId);
  const autoSelectId = organizations && organizations.length === 1 ? organizations[0].id : null;
  const selectedOrganizationId = storedIsValid ? storedId : autoSelectId;

  // A real auto-selection side effect (persisting the sole org's id),
  // not a derived-render calculation — belongs in an effect, not
  // during render, so it doesn't mutate the external store mid-render.
  useEffect(() => {
    if (autoSelectId && storedId !== autoSelectId) setSelectedOrganizationId(autoSelectId);
  }, [autoSelectId, storedId, setSelectedOrganizationId]);

  const needsSelection = organizations !== undefined && organizations.length > 1 && selectedOrganizationId === null;

  return {
    organizations,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    selectedOrganizationId,
    needsSelection,
    hasNoAccess,
  };
}
