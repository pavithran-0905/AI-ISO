import { useMutation } from "@tanstack/react-query";

import { invitationsApi } from "@/features/administration/api/invitations-api";
import type { CreateOrganizationInvitationInput } from "@/features/administration/types";

/** No list query exists — see `invitationsApi`'s own docstring for
 * why (no route lists pending invitations on this service). */
export function useCreateInvitation() {
  return useMutation({
    mutationFn: (input: CreateOrganizationInvitationInput) => invitationsApi.create(input),
  });
}
