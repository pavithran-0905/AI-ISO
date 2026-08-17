import { notFound } from "next/navigation";

import { env } from "@/config/env";

import { DesignSystemShowcase } from "./showcase";

/**
 * The internal design-system showcase (docs/frontend Prompt 002 §25) —
 * NOT the product Dashboard, and not a business feature. Gated behind
 * `appEnv !== "production"` (§25: "protect it appropriately so it is
 * not accidentally exposed as a production business feature") rather
 * than a route-level permission check, since it has nothing to do with
 * who's logged in — it simply shouldn't exist as a reachable route in
 * a production build at all.
 */
export default function DesignSystemPage() {
  if (env.appEnv === "production") notFound();
  return <DesignSystemShowcase />;
}
