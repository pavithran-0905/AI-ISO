"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { ApiRequestError } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/data-display/card";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { useConfigureConnector } from "@/features/settings/hooks/use-integrations";
import { isSensitiveMetadataKey, maskMetadataValue } from "@/features/infrastructure/lib/sensitive-metadata";
import { toast } from "@/state/toast-store";

interface ConfigRow {
  key: string;
  value: string;
}

function toRows(config: Record<string, unknown>): ConfigRow[] {
  return Object.entries(config).map(([key, value]) => ({ key, value: typeof value === "string" ? value : JSON.stringify(value) }));
}

/**
 * `PUT /integrations/connectors/{id}` — a full replace of the whole
 * `config` dict (confirmed: no `PATCH` exists for this route). A
 * connector has no defined config sub-schema (it's a free-form
 * `dict[str, Any]`), so this is a plain key/value editor rather than
 * grouped Connection/Authentication/Options fields — grouping would
 * mean inventing a schema this backend doesn't define. Sensitive-
 * looking keys are masked in the *display* rows, matching Prompt
 * 011's precedent — a value is only ever revealed by deliberately
 * editing that specific row.
 */
export function ConnectorConfigForm({ connectorId, config }: { connectorId: string; config: Record<string, unknown> }) {
  const configureConnector = useConfigureConnector(connectorId);
  const [rows, setRows] = useState<ConfigRow[]>(toRows(config));
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());

  function updateRow(index: number, field: "key" | "value", value: string) {
    setRows((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)));
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, rowIndex) => rowIndex !== index));
  }

  function addRow() {
    setRows((current) => [...current, { key: "", value: "" }]);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const nextConfig: Record<string, unknown> = {};
    for (const row of rows) {
      if (row.key) nextConfig[row.key] = row.value;
    }
    try {
      await configureConnector.mutateAsync({ config: nextConfig });
      toast.success("Configuration saved");
    } catch (error) {
      const message = error instanceof ApiRequestError ? error.message : "Please try again.";
      toast.danger("Could not save configuration", message);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration</CardTitle>
        <CardDescription>Free-form key/value config sent to this connector.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {rows.map((row, index) => {
            const isSensitive = isSensitiveMetadataKey(row.key);
            const isRevealed = revealedKeys.has(row.key) || row.key === "";
            return (
              <div key={index} className="flex items-end gap-2">
                <div className="flex-1">
                  <Label htmlFor={`config-key-${index}`}>Key</Label>
                  <Input id={`config-key-${index}`} value={row.key} onChange={(event) => updateRow(index, "key", event.target.value)} />
                </div>
                <div className="flex-1">
                  <Label htmlFor={`config-value-${index}`}>Value</Label>
                  {isSensitive && !isRevealed ? (
                    <button
                      type="button"
                      onClick={() => setRevealedKeys((current) => new Set(current).add(row.key))}
                      className="border-border bg-input hover:border-muted-foreground/50 h-9 w-full rounded-md border px-3 text-left font-mono text-sm"
                    >
                      {maskMetadataValue(row.key, row.value)}
                    </button>
                  ) : (
                    <Input id={`config-value-${index}`} value={row.value} onChange={(event) => updateRow(index, "value", event.target.value)} />
                  )}
                </div>
                <IconButton icon={Trash2} aria-label="Remove field" variant="ghost" onClick={() => removeRow(index)} />
              </div>
            );
          })}
          <Button type="button" variant="outline" onClick={addRow} className="w-fit gap-1.5">
            <Plus className="size-4" aria-hidden="true" />
            Add field
          </Button>
          <Button type="submit" loading={configureConnector.isPending} className="w-fit">
            Save configuration
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
