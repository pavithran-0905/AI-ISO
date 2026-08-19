"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useSession } from "@/auth/session";
import { usePatchUserIdentity } from "@/features/settings/hooks/use-preferences";
import { toast } from "@/state/toast-store";

/**
 * `PATCH /users/{id}` — the real, genuinely partial-safe edit path for
 * name/phone fields, distinct from `/users/profile`'s own full-replace
 * `PUT`. **Security note**: this route has no ownership check on the
 * backend (confirmed absent) — always called here with the caller's
 * own id from `useSession`, never anything the user could type in.
 */
export function IdentityForm() {
  const { user, userId } = useSession();
  const patchIdentity = usePatchUserIdentity();
  const [displayName, setDisplayName] = useState(user?.displayName ?? "");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!userId) return;
    try {
      await patchIdentity.mutateAsync({
        userId,
        input: {
          displayName: displayName || undefined,
          firstName: firstName || undefined,
          lastName: lastName || undefined,
          phoneNumber: phoneNumber || undefined,
        },
      });
      toast.success("Identity updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update identity", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
        <CardDescription>Your display name and contact details, as shown elsewhere in AI-IOS.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Display name" description="Shown in the account menu and anywhere you're attributed.">
              {(fieldProps) => <Input {...fieldProps} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />}
            </FormField>
            <FormField label="Phone number">
              {(fieldProps) => <Input {...fieldProps} value={phoneNumber} onChange={(event) => setPhoneNumber(event.target.value)} />}
            </FormField>
            <FormField label="First name">
              {(fieldProps) => <Input {...fieldProps} value={firstName} onChange={(event) => setFirstName(event.target.value)} />}
            </FormField>
            <FormField label="Last name">
              {(fieldProps) => <Input {...fieldProps} value={lastName} onChange={(event) => setLastName(event.target.value)} />}
            </FormField>
          </div>
          <Button type="submit" loading={patchIdentity.isPending} className="w-fit">
            Save identity
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
