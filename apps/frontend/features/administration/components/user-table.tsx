"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/data-display/card";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Button } from "@/components/ui/button";
import { USER_STATUS_TO_STATE } from "@/features/administration/lib/status-maps";
import type { UserSearchResult } from "@/features/administration/types";
import { useTableDensityStore } from "@/state/table-density-store";
import { cn } from "@/utils/cn";

/**
 * `GET /users` / `POST /users/search` — neither response includes a
 * total row count (confirmed: the route discards the pagination
 * metadata the service computes internally), so this is a real
 * Previous/Next pager, never a page-count picker that would have to
 * guess a total. `hasMore` is a heuristic (`items.length ===
 * pageSize`), documented in the type's own docstring.
 */
export function UserTable({
  result,
  onPageChange,
}: {
  result: UserSearchResult;
  onPageChange: (page: number) => void;
}) {
  const density = useTableDensityStore((state) => state.density);
  const cellPadding = density === "compact" ? "px-3 py-1.5" : "px-3 py-3";

  return (
    <div className="flex flex-col gap-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Name
              </th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Email
              </th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Status
              </th>
              <th scope="col" className={cn(cellPadding, "font-medium")}>
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {result.items.map((user) => (
              <tr key={user.id} className="border-border hover:bg-muted/50 border-b last:border-0">
                <td className={cellPadding}>
                  <Link
                    href={`/administration/users/${user.id}`}
                    className="focus-visible:ring-ring rounded font-medium hover:underline focus-visible:ring-2 focus-visible:outline-none"
                  >
                    {user.displayName ?? user.username}
                  </Link>
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>{user.email}</td>
                <td className={cellPadding}>
                  <StatusIndicator state={USER_STATUS_TO_STATE[user.status]} label={user.status} />
                </td>
                <td className={cn(cellPadding, "text-muted-foreground")}>
                  <time dateTime={user.createdAt}>{new Date(user.createdAt).toLocaleDateString()}</time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ul className="flex flex-col gap-2 md:hidden">
        {result.items.map((user) => (
          <li key={user.id}>
            <Link href={`/administration/users/${user.id}`} className="block">
              <Card className="hover:border-muted-foreground/50 transition-colors">
                <CardContent className="flex items-center justify-between gap-3 p-3">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-sm font-medium">{user.displayName ?? user.username}</p>
                    <p className="text-muted-foreground text-xs">{user.email}</p>
                  </div>
                  <StatusIndicator state={USER_STATUS_TO_STATE[user.status]} label={user.status} />
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <div className="flex items-center justify-between gap-3 text-sm">
        <p className="text-muted-foreground">
          Page {result.page} · {result.items.length} shown
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" disabled={result.page <= 1} onClick={() => onPageChange(result.page - 1)}>
            Previous
          </Button>
          <Button variant="outline" disabled={!result.hasMore} onClick={() => onPageChange(result.page + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
