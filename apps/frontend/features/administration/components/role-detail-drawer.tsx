"use client";

import { Drawer } from "@/components/overlays/drawer";
import { StatusBadge } from "@/components/feedback/status-badge";
import type { RbacRole } from "@/features/administration/types";

/** Metadata only — no route returns a role's granted permissions or
 * its assigned users (both confirmed absent; write-only grant/revoke
 * and assign/remove exist, with no matching read) — see the developer
 * guide. */
export function RoleDetailDrawer({ role, onClose }: { role: RbacRole | null; onClose: () => void }) {
  return (
    <Drawer open={role !== null} onClose={onClose} title={role?.name ?? "Role"}>
      {role && (
        <div className="flex flex-col gap-4 text-sm">
          <div className="flex items-center gap-2">
            <StatusBadge tone={role.isSystem ? "info" : "neutral"} label={role.isSystem ? "System role" : "Custom role"} />
            <StatusBadge tone={role.status === "active" ? "success" : "neutral"} label={role.status} />
          </div>
          <Field label="Code" value={role.code} mono />
          <Field label="Description" value={role.description} />
          <Field label="Type" value={role.roleType} />
          <Field label="Priority" value={String(role.priority)} />
          <Field label="Organization scope" value={role.organizationId} mono />
          <Field label="Project scope" value={role.projectId} mono />
          <p className="text-muted-foreground text-xs">
            No endpoint returns this role&apos;s granted permissions or assigned users — both are write-only on this
            backend (grant/revoke, assign/remove), with no matching read route.
          </p>
        </div>
      )}
    </Drawer>
  );
}

function Field({ label, value, mono = false }: { label: string; value: string | null; mono?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={mono ? "font-mono text-xs" : ""}>{value}</p>
    </div>
  );
}
