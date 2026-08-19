"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { PageHeader } from "@/components/navigation/page-header";
import { Alert } from "@/components/feedback/alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { AdministrationSubNav } from "@/features/administration/components/administration-sub-nav";
import { useCreateInvitation } from "@/features/administration/hooks/use-invitations";
import { ORGANIZATION_MEMBER_ROLES, type OrganizationMemberRoleValue } from "@/features/administration/types";
import { NoOrganizationAccessState, OrganizationPicker } from "@/features/dashboard/components/organization-picker";
import { SectionState } from "@/features/dashboard/components/section-state";
import { useSelectedOrganization } from "@/organization/use-organizations";
import { toast } from "@/state/toast-store";

/**
 * Invitations — `/administration/invitations` (§15). Built against
 * `organization-service`'s `POST /organizations/{id}/invite` — the
 * one real invitation path that carries a role, unlike
 * `user-management-service`'s separate `/users/invite` (email/message
 * only, no role). **No route on either service lists pending
 * invitations, resends one, or revokes one** (organization-service's
 * `resend`/list methods are confirmed unrouted; a revoke method
 * doesn't exist in either service at all) — this page is a send-only
 * form, with success/failure feedback as the only signal, since
 * there's nothing to list afterward.
 */
export function InvitationsPage() {
  const { organizations, isLoading, isError, selectedOrganizationId, needsSelection, hasNoAccess } = useSelectedOrganization();
  const createInvitation = useCreateInvitation();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrganizationMemberRoleValue>("member");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedOrganizationId) return;
    try {
      await createInvitation.mutateAsync({ organizationId: selectedOrganizationId, email, role, message: message || undefined });
      toast.success("Invitation sent", `${email} was invited as ${role}.`);
      setEmail("");
      setMessage("");
    } catch (error) {
      const message_ = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not send invitation", message_);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Invitations" description="Invite someone to this organization." />
      <AdministrationSubNav />

      <Alert tone="warning" title="No pending-invitations list exists">
        Neither backend service that supports invitations has a route to list, resend, or revoke a pending one — sending
        is the only capability available here. Track what you&apos;ve sent outside AI-IOS if you need a record.
      </Alert>

      <SectionState isLoading={isLoading} isError={isError} skeletonClassName="h-24 w-full">
        {hasNoAccess && <NoOrganizationAccessState />}
        {needsSelection && organizations && <OrganizationPicker organizations={organizations} />}
        {selectedOrganizationId && (
          <Card>
            <CardHeader>
              <CardTitle>Send an invitation</CardTitle>
              <CardDescription>The invited email can join this organization at the role you choose.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField label="Email" required>
                    {(fieldProps) => <Input {...fieldProps} type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />}
                  </FormField>
                  <FormField label="Role" required>
                    {(fieldProps) => (
                      <Select {...fieldProps} value={role} onChange={(event) => setRole(event.target.value as OrganizationMemberRoleValue)}>
                        {ORGANIZATION_MEMBER_ROLES.map((value) => (
                          <option key={value} value={value}>
                            {value}
                          </option>
                        ))}
                      </Select>
                    )}
                  </FormField>
                </div>
                <FormField label="Message">
                  {(fieldProps) => <Textarea {...fieldProps} value={message} onChange={(event) => setMessage(event.target.value)} />}
                </FormField>
                <Button type="submit" loading={createInvitation.isPending} disabled={!email} className="w-fit">
                  Send invitation
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </SectionState>
    </div>
  );
}
