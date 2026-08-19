"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { useUpdateOrganizationBranding } from "@/features/settings/hooks/use-organization-settings";
import type { OrganizationBranding } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/** `GET/PUT /organizations/{id}/branding` — full-replace `PUT`.
 * `emailTemplates`/`loginScreenBranding`/`dashboardBranding` are
 * opaque JSON blobs, round-tripped unchanged, same reasoning as the
 * policy form's own opaque fields. */
export function OrganizationBrandingForm({
  organizationId,
  branding,
  canEdit,
}: {
  organizationId: string;
  branding: OrganizationBranding;
  canEdit: boolean;
}) {
  const updateBranding = useUpdateOrganizationBranding(organizationId);
  const [logoUrl, setLogoUrl] = useState(branding.logoUrl ?? "");
  const [darkLogoUrl, setDarkLogoUrl] = useState(branding.darkLogoUrl ?? "");
  const [faviconUrl, setFaviconUrl] = useState(branding.faviconUrl ?? "");
  const [primaryColor, setPrimaryColor] = useState(branding.primaryColor ?? "");
  const [secondaryColor, setSecondaryColor] = useState(branding.secondaryColor ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateBranding.mutateAsync({
        logoUrl: logoUrl || null,
        darkLogoUrl: darkLogoUrl || null,
        faviconUrl: faviconUrl || null,
        primaryColor: primaryColor || null,
        secondaryColor: secondaryColor || null,
        theme: branding.theme,
        emailTemplates: branding.emailTemplates,
        loginScreenBranding: branding.loginScreenBranding,
        dashboardBranding: branding.dashboardBranding,
      });
      toast.success("Branding updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update branding", message);
    }
  }

  if (!canEdit) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Branding</CardTitle>
          <CardDescription>Your role doesn&apos;t allow editing branding.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm">
          <p>Primary color: {branding.primaryColor ?? "Not set"}</p>
          <p>Secondary color: {branding.secondaryColor ?? "Not set"}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Branding</CardTitle>
        <CardDescription>White-label appearance for this organization.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField label="Logo URL">
              {(fieldProps) => <Input {...fieldProps} value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} />}
            </FormField>
            <FormField label="Dark-mode logo URL">
              {(fieldProps) => <Input {...fieldProps} value={darkLogoUrl} onChange={(event) => setDarkLogoUrl(event.target.value)} />}
            </FormField>
            <FormField label="Favicon URL">
              {(fieldProps) => <Input {...fieldProps} value={faviconUrl} onChange={(event) => setFaviconUrl(event.target.value)} />}
            </FormField>
            <FormField label="Primary color">
              {(fieldProps) => <Input {...fieldProps} value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} placeholder="#1a73e8" />}
            </FormField>
            <FormField label="Secondary color">
              {(fieldProps) => <Input {...fieldProps} value={secondaryColor} onChange={(event) => setSecondaryColor(event.target.value)} placeholder="#5f6368" />}
            </FormField>
          </div>
          <Button type="submit" loading={updateBranding.isPending} className="w-fit">
            Save branding
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
