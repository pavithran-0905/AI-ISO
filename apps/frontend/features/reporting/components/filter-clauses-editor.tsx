"use client";

import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { FILTER_OPERATORS, type FilterClause, type FilterOperatorValue } from "@/features/reporting/types";

const NO_OPERAND_OPERATORS = new Set<FilterOperatorValue>(["is_null", "is_not_null"]);

/**
 * One row per `{field, operator, value}` clause (§8/§24) — the real
 * grammar `app/filters/engine.py#FilterClause` applies, matched
 * against already-fetched rows server-side, not pushed to a data
 * source's own query string.
 */
export function FilterClausesEditor({
  clauses,
  onChange,
}: {
  clauses: FilterClause[];
  onChange: (clauses: FilterClause[]) => void;
}) {
  function updateClause(index: number, patch: Partial<FilterClause>) {
    onChange(clauses.map((clause, i) => (i === index ? { ...clause, ...patch } : clause)));
  }

  function removeClause(index: number) {
    onChange(clauses.filter((_, i) => i !== index));
  }

  function addClause() {
    onChange([...clauses, { field: "", operator: "eq", value: "" }]);
  }

  return (
    <div className="flex flex-col gap-3">
      {clauses.map((clause, index) => (
        <div key={index} className="flex flex-wrap items-end gap-2">
          <div className="flex flex-1 flex-col gap-1.5">
            {index === 0 && <Label htmlFor={`filter-field-${index}`}>Field</Label>}
            <Input
              id={`filter-field-${index}`}
              value={clause.field}
              onChange={(event) => updateClause(index, { field: event.target.value })}
              placeholder="e.g. status"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            {index === 0 && <Label htmlFor={`filter-operator-${index}`}>Operator</Label>}
            <Select
              id={`filter-operator-${index}`}
              value={clause.operator}
              onChange={(event) => updateClause(index, { operator: event.target.value as FilterOperatorValue })}
              className="w-36"
            >
              {FILTER_OPERATORS.map((operator) => (
                <option key={operator} value={operator}>
                  {operator}
                </option>
              ))}
            </Select>
          </div>
          {!NO_OPERAND_OPERATORS.has(clause.operator) && (
            <div className="flex flex-1 flex-col gap-1.5">
              {index === 0 && <Label htmlFor={`filter-value-${index}`}>Value</Label>}
              <Input
                id={`filter-value-${index}`}
                value={clause.value === undefined ? "" : String(clause.value)}
                onChange={(event) => updateClause(index, { value: event.target.value })}
              />
            </div>
          )}
          <IconButton icon={X} aria-label="Remove filter" variant="ghost" onClick={() => removeClause(index)} />
        </div>
      ))}
      <Button variant="outline" onClick={addClause} className="w-fit gap-1.5">
        <Plus className="size-4" aria-hidden="true" />
        Add filter
      </Button>
    </div>
  );
}
