"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useUpdateOrganizationIdentity } from "@/features/settings/hooks/use-organization-settings";
import type { OrganizationIdentity } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /organizations/{id}` — a full-replace `PUT` (confirmed: no
 * `PATCH` exists), so every save resends the complete object. Read-only
 * for members; `canEdit` (mapped from the coarse `isAdministrative`
 * role heuristic) gates the form, since this route's real backend
 * check is per-organization Administrator rank — something this
 * frontend cannot verify without a live membership lookup. See the
 * developer guide's Permissions section.
 */
export function OrganizationIdentityForm({ identity, canEdit }: { identity: OrganizationIdentity; canEdit: boolean }) {
  const updateIdentity = useUpdateOrganizationIdentity(identity.id);
  const [name, setName] = useState(identity.name);
  const [displayName, setDisplayName] = useState(identity.displayName ?? "");
  const [primaryDomain, setPrimaryDomain] = useState(identity.primaryDomain ?? "");
  const [primaryContactEmail, setPrimaryContactEmail] = useState(identity.primaryContactEmail ?? "");
  const [website, setWebsite] = useState(identity.website ?? "");
  const [industry, setIndustry] = useState(identity.industry ?? "");
  const [country, setCountry] = useState(identity.country ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateIdentity.mutateAsync({
        name,
        displayName: displayName || null,
        shortName: identity.shortName,
        description: identity.description,
        status: identity.status,
        primaryDomain: primaryDomain || null,
        primaryContactEmail: primaryContactEmail || null,
        logoUrl: identity.logoUrl,
        website: website || null,
        industry: industry || null,
        timezone: identity.timezone,
        language: identity.language,
        country: country || null,
        currency: identity.currency,
        metadata: identity.metadata,
      });
      toast.success("Organization identity updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update organization", message);
    }
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Your role doesn&apos;t allow editing organization identity — showing current values.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Field label="Name" value={identity.name} />
            <Field label="Display name" value={identity.displayName} />
            <Field label="Primary domain" value={identity.primaryDomain} />
            <Field label="Primary contact" value={identity.primaryContactEmail} />
            <Field label="Website" value={identity.website} />
            <Field label="Industry" value={identity.industry} />
            <Field label="Country" value={identity.country} />
          </dl>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Identity</CardTitle>
        <CardDescription>Real name, domain, and contact details for this organization.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Name" required>
              {(fieldProps) => <Input {...fieldProps} value={name} onChange={(event) => setName(event.target.value)} required />}
            </FormField>
            <FormField label="Display name">
              {(fieldProps) => <Input {...fieldProps} value={displayName} onChange={(event) => setDisplayName(event.target.value)} />}
            </FormField>
            <FormField label="Primary domain">
              {(fieldProps) => <Input {...fieldProps} value={primaryDomain} onChange={(event) => setPrimaryDomain(event.target.value)} />}
            </FormField>
            <FormField label="Primary contact email">
              {(fieldProps) => <Input {...fieldProps} type="email" value={primaryContactEmail} onChange={(event) => setPrimaryContactEmail(event.target.value)} />}
            </FormField>
            <FormField label="Website">
              {(fieldProps) => <Input {...fieldProps} value={website} onChange={(event) => setWebsite(event.target.value)} />}
            </FormField>
            <FormField label="Industry">
              {(fieldProps) => <Input {...fieldProps} value={industry} onChange={(event) => setIndustry(event.target.value)} />}
            </FormField>
            <FormField label="Country">
              {(fieldProps) => <Input {...fieldProps} value={country} onChange={(event) => setCountry(event.target.value)} />}
            </FormField>
          </div>
          <Button type="submit" loading={updateIdentity.isPending} className="w-fit">
            Save identity
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
