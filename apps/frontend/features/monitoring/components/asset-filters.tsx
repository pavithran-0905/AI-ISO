"use client";

import { AlignJustify, Rows3, Search, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ASSET_STATUSES, ASSET_TYPES, type AssetStatusValue, type AssetTypeValue } from "@/features/monitoring/types";
import { useTableDensityStore } from "@/state/table-density-store";

export interface AssetFilterValues {
  query: string;
  status: AssetStatusValue | "";
  assetType: AssetTypeValue | "";
}

/**
 * Real filters (§14), backed entirely by `GET /inventory/search`'s own
 * server-side `q`/`status`/`asset_type` params — never a decorative
 * filter that does nothing. Every input is a real `<label>`-associated
 * control (§31) and keyboard-operable (native `<input>`/`<select>`).
 */
export function AssetFilters({
  values,
  onChange,
  onReset,
}: {
  values: AssetFilterValues;
  onChange: (values: AssetFilterValues) => void;
  onReset: () => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const setDensity = useTableDensityStore((state) => state.setDensity);
  const activeFilterCount = [values.query, values.status, values.assetType].filter(Boolean).length;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex min-w-48 flex-1 flex-col gap-1.5">
        <Label htmlFor="asset-search">Search</Label>
        <div className="relative">
          <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" aria-hidden="true" />
          <Input
            id="asset-search"
            value={values.query}
            onChange={(event) => onChange({ ...values, query: event.target.value })}
            placeholder="Name, hostname, IP, serial…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="asset-status-filter">Status</Label>
        <Select
          id="asset-status-filter"
          value={values.status}
          onChange={(event) => onChange({ ...values, status: event.target.value as AssetStatusValue | "" })}
          className="w-40"
        >
          <option value="">All statuses</option>
          {ASSET_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="asset-type-filter">Type</Label>
        <Select
          id="asset-type-filter"
          value={values.assetType}
          onChange={(event) => onChange({ ...values, assetType: event.target.value as AssetTypeValue | "" })}
          className="w-44"
        >
          <option value="">All types</option>
          {ASSET_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </Select>
      </div>

      {activeFilterCount > 0 && (
        <Button variant="ghost" onClick={onReset} className="gap-1.5">
          <X className="size-4" aria-hidden="true" />
          Reset
          <Badge variant="outline">{activeFilterCount}</Badge>
        </Button>
      )}

      <div className="ml-auto flex items-center gap-1" role="group" aria-label="Table density">
        <IconButton
          icon={Rows3}
          aria-label="Comfortable density"
          aria-pressed={density === "comfortable"}
          variant={density === "comfortable" ? "secondary" : "ghost"}
          onClick={() => setDensity("comfortable")}
        />
        <IconButton
          icon={AlignJustify}
          aria-label="Compact density"
          aria-pressed={density === "compact"}
          variant={density === "compact" ? "secondary" : "ghost"}
          onClick={() => setDensity("compact")}
        />
      </div>
    </div>
  );
}

export const EMPTY_FILTERS: AssetFilterValues = { query: "", status: "", assetType: "" };
