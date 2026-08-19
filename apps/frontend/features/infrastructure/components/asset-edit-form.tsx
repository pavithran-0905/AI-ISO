"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import {
  ASSET_HEALTH_STATUSES,
  ASSET_STATUSES,
  CRITICALITY_LEVELS,
  LIFECYCLE_STATES,
  type Asset,
  type AssetHealthValue,
  type AssetStatusValue,
  type CriticalityValue,
  type LifecycleStateValue,
  type PatchAssetInput,
} from "@/features/infrastructure/types";

/**
 * `PATCH /inventory/assets/{id}` (§21 "update") — see
 * `PatchAssetInput`'s own docstring for why `PUT` is never used.
 * `assetType`/`tags`/`organizationId`/`projectId` aren't shown: none
 * is patchable (confirmed absent from `AssetPatchRequest`). `metadata`
 * isn't editable here either — it's a genuinely free-form dict with no
 * defined shape to build a key/value editor against without inventing
 * one; it stays presentation-only (§16), consistent with this
 * platform's "don't invent a schema the backend doesn't declare"
 * discipline. Status is a normal field here rather than a separate
 * enable/disable action — no such dedicated route exists.
 */
export function AssetEditForm({
  asset,
  onSubmit,
  isSubmitting,
}: {
  asset: Asset;
  onSubmit: (input: PatchAssetInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState(asset.name);
  const [displayName, setDisplayName] = useState(asset.displayName ?? "");
  const [hostname, setHostname] = useState(asset.hostname ?? "");
  const [fqdn, setFqdn] = useState(asset.fqdn ?? "");
  const [ipAddress, setIpAddress] = useState(asset.ipAddress ?? "");
  const [macAddress, setMacAddress] = useState(asset.macAddress ?? "");
  const [serialNumber, setSerialNumber] = useState(asset.serialNumber ?? "");
  const [vendor, setVendor] = useState(asset.vendor ?? "");
  const [manufacturer, setManufacturer] = useState(asset.manufacturer ?? "");
  const [model, setModel] = useState(asset.model ?? "");
  const [firmwareVersion, setFirmwareVersion] = useState(asset.firmwareVersion ?? "");
  const [operatingSystem, setOperatingSystem] = useState(asset.operatingSystem ?? "");
  const [architecture, setArchitecture] = useState(asset.architecture ?? "");
  const [environment, setEnvironment] = useState(asset.environment ?? "");
  const [status, setStatus] = useState<AssetStatusValue>(asset.status);
  const [health, setHealth] = useState<AssetHealthValue>(asset.health);
  const [lifecycleState, setLifecycleState] = useState<LifecycleStateValue>(asset.lifecycleState);
  const [criticality, setCriticality] = useState<CriticalityValue>(asset.criticality);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    setError(null);
    onSubmit({
      name: name.trim(),
      displayName: displayName.trim() || undefined,
      hostname: hostname.trim() || undefined,
      fqdn: fqdn.trim() || undefined,
      ipAddress: ipAddress.trim() || undefined,
      macAddress: macAddress.trim() || undefined,
      serialNumber: serialNumber.trim() || undefined,
      vendor: vendor.trim() || undefined,
      manufacturer: manufacturer.trim() || undefined,
      model: model.trim() || undefined,
      firmwareVersion: firmwareVersion.trim() || undefined,
      operatingSystem: operatingSystem.trim() || undefined,
      architecture: architecture.trim() || undefined,
      environment: environment.trim() || undefined,
      status,
      health,
      lifecycleState,
      criticality,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Identity</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-name">Name</Label>
            <Input id="asset-edit-name" value={name} onChange={(event) => setName(event.target.value)} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-display-name">Display name</Label>
            <Input id="asset-edit-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-environment">Environment</Label>
            <Input id="asset-edit-environment" value={environment} onChange={(event) => setEnvironment(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-hostname">Hostname</Label>
            <Input id="asset-edit-hostname" value={hostname} onChange={(event) => setHostname(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-fqdn">FQDN</Label>
            <Input id="asset-edit-fqdn" value={fqdn} onChange={(event) => setFqdn(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-ip">IP address</Label>
            <Input id="asset-edit-ip" value={ipAddress} onChange={(event) => setIpAddress(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-mac">MAC address</Label>
            <Input id="asset-edit-mac" value={macAddress} onChange={(event) => setMacAddress(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-serial">Serial number</Label>
            <Input id="asset-edit-serial" value={serialNumber} onChange={(event) => setSerialNumber(event.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Hardware / software</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-vendor">Vendor</Label>
            <Input id="asset-edit-vendor" value={vendor} onChange={(event) => setVendor(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-manufacturer">Manufacturer</Label>
            <Input id="asset-edit-manufacturer" value={manufacturer} onChange={(event) => setManufacturer(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-model">Model</Label>
            <Input id="asset-edit-model" value={model} onChange={(event) => setModel(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-firmware">Firmware version</Label>
            <Input id="asset-edit-firmware" value={firmwareVersion} onChange={(event) => setFirmwareVersion(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-os">Operating system</Label>
            <Input id="asset-edit-os" value={operatingSystem} onChange={(event) => setOperatingSystem(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-architecture">Architecture</Label>
            <Input id="asset-edit-architecture" value={architecture} onChange={(event) => setArchitecture(event.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">State</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-status">Status</Label>
            <Select id="asset-edit-status" value={status} onChange={(event) => setStatus(event.target.value as AssetStatusValue)}>
              {ASSET_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-health">Health</Label>
            <Select id="asset-edit-health" value={health} onChange={(event) => setHealth(event.target.value as AssetHealthValue)}>
              {ASSET_HEALTH_STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-lifecycle">Lifecycle</Label>
            <Select id="asset-edit-lifecycle" value={lifecycleState} onChange={(event) => setLifecycleState(event.target.value as LifecycleStateValue)}>
              {LIFECYCLE_STATES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-edit-criticality">Criticality</Label>
            <Select id="asset-edit-criticality" value={criticality} onChange={(event) => setCriticality(event.target.value as CriticalityValue)}>
              {CRITICALITY_LEVELS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={isSubmitting} className="w-fit">
        Save changes
      </Button>
    </form>
  );
}
