"use client";

import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import { useCreatePrompt } from "@/features/ai-assistant/hooks/use-prompts";
import { toast } from "@/state/toast-store";

/** Variables are declared as a comma-separated list of names — the
 * backend stores them as `list[str]` with no further schema, so a
 * plain text field is a faithful match, not a simplification of
 * something richer. */
export function PromptCreateForm({ organizationId, onCreated }: { organizationId: string; onCreated: (promptId: string) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState("");
  const [variablesInput, setVariablesInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const createPrompt = useCreatePrompt();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !template.trim()) {
      setError("Name and template are required.");
      return;
    }
    setError(null);
    const variables = variablesInput.split(",").map((value) => value.trim()).filter(Boolean);
    try {
      const prompt = await createPrompt.mutateAsync({
        organizationId,
        name: name.trim(),
        description: description.trim() || undefined,
        template: template.trim(),
        variables,
      });
      toast.success("Prompt created");
      setName("");
      setDescription("");
      setTemplate("");
      setVariablesInput("");
      onCreated(prompt.id);
    } catch (submitError) {
      const message = submitError instanceof ApiRequestError ? submitError.message : "Please try again.";
      toast.danger("Could not create prompt", message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="prompt-name">Name</Label>
        <Input id="prompt-name" value={name} onChange={(event) => setName(event.target.value)} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="prompt-description">Description</Label>
        <Input id="prompt-description" value={description} onChange={(event) => setDescription(event.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="prompt-template">Template</Label>
        <Textarea id="prompt-template" value={template} onChange={(event) => setTemplate(event.target.value)} rows={5} required />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="prompt-variables">Variables (comma-separated)</Label>
        <Input id="prompt-variables" value={variablesInput} onChange={(event) => setVariablesInput(event.target.value)} placeholder="resource_name, environment" />
      </div>
      {error && <p className="text-danger text-sm">{error}</p>}
      <Button type="submit" loading={createPrompt.isPending} className="w-fit">
        Create prompt
      </Button>
    </form>
  );
}
