"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Textarea } from "@/components/forms/textarea";
import { useUpdateUserProfile } from "@/features/settings/hooks/use-preferences";
import type { UserProfile } from "@/features/settings/types";
import { toast } from "@/state/toast-store";

/**
 * `GET/PUT /users/profile` — a full-replace `PUT` (confirmed: no
 * `PATCH` exists for this resource), so every save resends the
 * complete object, including `customFields`, unchanged from what was
 * last fetched — omitting it would silently wipe it to `{}`.
 */
export function ProfileForm({ profile }: { profile: UserProfile }) {
  const updateProfile = useUpdateUserProfile();
  const [biography, setBiography] = useState(profile.biography ?? "");
  const [jobTitle, setJobTitle] = useState(profile.jobTitle ?? "");
  const [department, setDepartment] = useState(profile.department ?? "");
  const [employeeId, setEmployeeId] = useState(profile.employeeId ?? "");
  const [managerId, setManagerId] = useState(profile.managerId ?? "");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await updateProfile.mutateAsync({
        biography: biography || null,
        jobTitle: jobTitle || null,
        department: department || null,
        employeeId: employeeId || null,
        managerId: managerId || null,
        customFields: profile.customFields,
      });
      toast.success("Profile updated");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not update profile", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>Workplace details, visible to teammates who look up your profile.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <FormField label="Biography">
            {(fieldProps) => <Textarea {...fieldProps} value={biography} onChange={(event) => setBiography(event.target.value)} />}
          </FormField>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <FormField label="Job title">
              {(fieldProps) => <Input {...fieldProps} value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} />}
            </FormField>
            <FormField label="Department">
              {(fieldProps) => <Input {...fieldProps} value={department} onChange={(event) => setDepartment(event.target.value)} />}
            </FormField>
            <FormField label="Employee ID">
              {(fieldProps) => <Input {...fieldProps} value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} />}
            </FormField>
          </div>
          <FormField label="Manager ID" description="Shown as a raw id — no directory lookup exists to resolve it to a name.">
            {(fieldProps) => <Input {...fieldProps} value={managerId} onChange={(event) => setManagerId(event.target.value)} className="font-mono" />}
          </FormField>
          <Button type="submit" loading={updateProfile.isPending} className="w-fit">
            Save profile
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
