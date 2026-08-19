"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { GROUP_TYPES, type CreateGroupInput, type GroupTypeValue } from "@/features/infrastructure/types";

/** `AssetGroupCreateRequest` (§24-adjacent: only real V1 group
 * capability). Member selection at creation time only — no
 * add/remove-member route exists once a group is created (confirmed
 * absent), so this is the one chance to set static membership. */
export function GroupCreateForm({
  organizationId,
  onSubmit,
  isSubmitting,
}: {
  organizationId: string;
  onSubmit: (input: CreateGroupInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [groupType, setGroupType] = useState<GroupTypeValue>("static");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setError(null);
    onSubmit({ organizationId, name: name.trim(), description: description.trim() || undefined, groupType });
    setName("");
    setDescription("");
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-col gap-1.5">
        <Label htmlFor="group-name">Name</Label>
        <Input id="group-name" value={name} onChange={(event) => setName(event.target.value)} required />
      </div>
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="group-description">Description</Label>
        <Input id="group-description" value={description} onChange={(event) => setDescription(event.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="group-type">Type</Label>
        <Select id="group-type" value={groupType} onChange={(event) => setGroupType(event.target.value as GroupTypeValue)} className="w-36">
          {GROUP_TYPES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </Select>
      </div>
      {error && <p className="text-danger w-full text-sm">{error}</p>}
      <Button type="submit" loading={isSubmitting}>
        Create group
      </Button>
    </form>
  );
}
