"use client";

import { Download, Edit, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Alert } from "@/components/feedback/alert";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { LoadingState } from "@/components/feedback/loading-state";
import { OfflineState } from "@/components/feedback/offline-state";
import { Skeleton } from "@/components/feedback/skeleton";
import { StatusBadge, type StatusTone } from "@/components/feedback/status-badge";
import { Accordion } from "@/components/navigation/accordion";
import { Tabs } from "@/components/navigation/tabs";
import { Dialog } from "@/components/overlays/dialog";
import { Drawer } from "@/components/overlays/drawer";
import { Dropdown } from "@/components/overlays/dropdown";
import { Popover } from "@/components/overlays/popover";
import { Tooltip } from "@/components/overlays/tooltip";
import { Badge } from "@/components/ui/badge";
import { Button, type ButtonVariant } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Separator } from "@/components/ui/separator";
import { Surface } from "@/components/ui/surface";
import { StatusIndicator } from "@/components/data-display/status-indicator";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/data-display/card";
import { Checkbox } from "@/components/forms/checkbox";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Radio } from "@/components/forms/radio";
import { Select } from "@/components/forms/select";
import { Switch } from "@/components/forms/switch";
import { Textarea } from "@/components/forms/textarea";
import { STATUS_STATES } from "@/lib/status";
import { typography } from "@/lib/typography";
import { toast } from "@/state/toast-store";

const BUTTON_VARIANTS: ButtonVariant[] = ["primary", "secondary", "outline", "ghost", "danger"];
const STATUS_TONES: StatusTone[] = [
  "success",
  "warning",
  "danger",
  "info",
  "neutral",
  "pending",
  "running",
  "stopped",
  "degraded",
  "unknown",
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className={typography.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}

/**
 * Every built primitive, in both themes (toggle via the header's own
 * `ThemeToggle`) — the visual contract every future frontend prompt
 * should check its work against. Not the product Dashboard.
 */
export function DesignSystemShowcase() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("one");
  const [switchOn, setSwitchOn] = useState(false);

  return (
    <div className="flex flex-col gap-10 pb-16">
      <div>
        <h1 className={typography.pageTitle}>Design System Showcase</h1>
        <p className="text-muted-foreground text-sm">
          Internal only — not a product page. See docs/frontend/design-system/.
        </p>
      </div>

      <Section title="Typography">
        <div className="flex flex-col gap-2">
          <p className={typography.display}>Display text</p>
          <p className={typography.pageTitle}>Page title</p>
          <p className={typography.sectionTitle}>Section title</p>
          <p className={typography.cardTitle}>Card title</p>
          <p className={typography.body}>Body text — the default for most copy in the app.</p>
          <p className={typography.bodySmall}>Body small — supporting copy.</p>
          <p className={typography.label}>Label text</p>
          <p className={typography.caption}>Caption / metadata text</p>
          <p className={typography.code}>const code = &quot;monospace&quot;;</p>
          <p className={typography.metric}>42,918</p>
        </div>
      </Section>

      <Section title="Colour & status tones">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {STATUS_TONES.map((tone) => (
            <StatusBadge key={tone} tone={tone} label={tone} />
          ))}
        </div>
      </Section>

      <Section title="Status taxonomy (named states)">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STATUS_STATES.map((state) => (
            <StatusIndicator key={state} state={state} />
          ))}
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-2">
          {BUTTON_VARIANTS.map((variant) => (
            <Button key={variant} variant={variant}>
              {variant}
            </Button>
          ))}
          <Button loading>Loading</Button>
          <Button disabled>Disabled</Button>
        </div>
        <div className="flex items-center gap-2">
          <IconButton icon={Edit} aria-label="Edit" />
          <IconButton icon={Trash2} aria-label="Delete" variant="danger" />
          <IconButton icon={Download} aria-label="Download" variant="outline" />
          <Tooltip label="Tooltip content">
            <IconButton icon={Plus} aria-label="Add (hover me)" variant="ghost" />
          </Tooltip>
        </div>
      </Section>

      <Section title="Badges">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>default</Badge>
          <Badge variant="outline">outline</Badge>
          <Badge variant="primary">primary</Badge>
        </div>
      </Section>

      <Section title="Cards & surfaces">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Card title</CardTitle>
              <CardDescription>A titled content block.</CardDescription>
            </CardHeader>
            <CardContent>Body content.</CardContent>
          </Card>
          <Surface elevation="raised" className="p-4 text-sm">
            Raised surface
          </Surface>
          <Surface elevation="overlay" className="p-4 text-sm">
            Overlay surface
          </Surface>
        </div>
        <Separator />
      </Section>

      <Section title="Form controls">
        <div className="grid max-w-md grid-cols-1 gap-4">
          <FormField label="Name" required description="Shown on your profile.">
            {(fieldProps) => <Input placeholder="Jane Doe" {...fieldProps} />}
          </FormField>
          <FormField label="Notes" error="This field is required.">
            {(fieldProps) => <Textarea placeholder="Optional notes" {...fieldProps} />}
          </FormField>
          <FormField label="Region">
            {(fieldProps) => (
              <Select {...fieldProps}>
                <option>us-east-1</option>
                <option>eu-west-1</option>
              </Select>
            )}
          </FormField>
          <div className="flex items-center gap-2">
            <Checkbox id="showcase-checkbox" defaultChecked />
            <label htmlFor="showcase-checkbox" className="text-sm">
              Checkbox
            </label>
          </div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-2">
              <Radio name="showcase-radio" id="showcase-radio-1" defaultChecked />
              <label htmlFor="showcase-radio-1" className="text-sm">
                Option A
              </label>
            </span>
            <span className="flex items-center gap-2">
              <Radio name="showcase-radio" id="showcase-radio-2" />
              <label htmlFor="showcase-radio-2" className="text-sm">
                Option B
              </label>
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={switchOn} onChange={(event) => setSwitchOn(event.target.checked)} aria-label="Toggle example" />
            <span className="text-sm">Switch ({switchOn ? "on" : "off"})</span>
          </div>
        </div>
      </Section>

      <Section title="Overlays">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => setDialogOpen(true)}>Open dialog</Button>
          <Button variant="outline" onClick={() => setDrawerOpen(true)}>
            Open drawer
          </Button>
          <Popover
            open={popoverOpen}
            onClose={() => setPopoverOpen(false)}
            trigger={
              <Button variant="outline" onClick={() => setPopoverOpen((value) => !value)}>
                Popover
              </Button>
            }
          >
            <p className="text-sm">Arbitrary popover content.</p>
          </Popover>
          <Dropdown
            open={dropdownOpen}
            onClose={() => setDropdownOpen(false)}
            trigger={
              <Button variant="outline" onClick={() => setDropdownOpen((value) => !value)}>
                Dropdown
              </Button>
            }
            items={[
              { label: "Edit", icon: Edit, onSelect: () => toast.info("Edit selected") },
              { label: "Delete", icon: Trash2, destructive: true, onSelect: () => toast.danger("Delete selected") },
            ]}
          />
          <Button variant="ghost" onClick={() => toast.success("Saved", "Your changes were saved.")}>
            Trigger toast
          </Button>
        </div>
        <Dialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          title="Example dialog"
          description="A modal built on the native <dialog> element."
          footer={
            <>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={() => setDialogOpen(false)}>Confirm</Button>
            </>
          }
        >
          <p className="text-sm">Dialog body content.</p>
        </Dialog>
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Example drawer">
          <p className="text-sm">Drawer body content.</p>
        </Drawer>
      </Section>

      <Section title="Tabs & accordion">
        <Tabs
          items={[
            { id: "one", label: "Tab one" },
            { id: "two", label: "Tab two" },
          ]}
          activeId={activeTab}
          onChange={setActiveTab}
        >
          <p className="text-sm">Content for {activeTab}.</p>
        </Tabs>
        <Accordion
          items={[
            { id: "a", title: "First item", content: "First item's content." },
            { id: "b", title: "Second item", content: "Second item's content." },
          ]}
        />
      </Section>

      <Section title="Alerts">
        <div className="flex flex-col gap-2">
          <Alert tone="info" title="Informational alert">
            Supporting detail text.
          </Alert>
          <Alert tone="success" title="Success alert" />
          <Alert tone="warning" title="Warning alert" />
          <Alert tone="danger" title="Danger alert" />
        </div>
      </Section>

      <Section title="Loading, empty, error, offline">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Surface className="p-2">
            <LoadingState />
          </Surface>
          <Surface className="p-2">
            <EmptyState title="No items yet" description="Create your first item to get started." />
          </Surface>
          <Surface className="p-2">
            <ErrorState onRetry={() => {}} />
          </Surface>
          <Surface className="p-2">
            <OfflineState onRetry={() => {}} />
          </Surface>
        </div>
        <div className="flex flex-col gap-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </Section>
    </div>
  );
}
