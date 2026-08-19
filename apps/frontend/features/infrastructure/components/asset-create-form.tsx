"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { Label } from "@/components/forms/label";
import { Select } from "@/components/forms/select";
import { ASSET_TYPES, CRITICALITY_LEVELS, type AssetTypeValue, type CreateAssetInput, type CriticalityValue } from "@/features/infrastructure/types";

/**
 * `AssetCreateRequest` (§21 "create") — every field it accepts, no
 * more. `assetType` has no server-side default, so it's the one
 * required selection beyond `name`.
 */
export function AssetCreateForm({
  organizationId,
  onSubmit,
  isSubmitting,
}: {
  organizationId: string;
  onSubmit: (input: CreateAssetInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [assetType, setAssetType] = useState<AssetTypeValue | "">("");
  const [hostname, setHostname] = useState("");
  const [fqdn, setFqdn] = useState("");
  const [ipAddress, setIpAddress] = useState("");
  const [macAddress, setMacAddress] = useState("");
  const [serialNumber, setSerialNumber] = useState("");
  const [vendor, setVendor] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [model, setModel] = useState("");
  const [firmwareVersion, setFirmwareVersion] = useState("");
  const [operatingSystem, setOperatingSystem] = useState("");
  const [architecture, setArchitecture] = useState("");
  const [environment, setEnvironment] = useState("");
  const [criticality, setCriticality] = useState<CriticalityValue>("medium");
  const [tagsInput, setTagsInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !assetType) {
      setError("Name and asset type are required.");
      return;
    }
    setError(null);
    onSubmit({
      organizationId,
      name: name.trim(),
      displayName: displayName.trim() || undefined,
      assetType,
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
      criticality,
      tags: tagsInput
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Identity</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-name">Name</Label>
            <Input id="asset-name" value={name} onChange={(event) => setName(event.target.value)} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-display-name">Display name</Label>
            <Input id="asset-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-type">Type</Label>
            <Select id="asset-type" value={assetType} onChange={(event) => setAssetType(event.target.value as AssetTypeValue)} required>
              <option value="">Select…</option>
              {ASSET_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-environment">Environment</Label>
            <Input id="asset-environment" value={environment} onChange={(event) => setEnvironment(event.target.value)} placeholder="production, staging…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-hostname">Hostname</Label>
            <Input id="asset-hostname" value={hostname} onChange={(event) => setHostname(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-fqdn">FQDN</Label>
            <Input id="asset-fqdn" value={fqdn} onChange={(event) => setFqdn(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-ip">IP address</Label>
            <Input id="asset-ip" value={ipAddress} onChange={(event) => setIpAddress(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-mac">MAC address</Label>
            <Input id="asset-mac" value={macAddress} onChange={(event) => setMacAddress(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-serial">Serial number</Label>
            <Input id="asset-serial" value={serialNumber} onChange={(event) => setSerialNumber(event.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Hardware / software</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-vendor">Vendor</Label>
            <Input id="asset-vendor" value={vendor} onChange={(event) => setVendor(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-manufacturer">Manufacturer</Label>
            <Input id="asset-manufacturer" value={manufacturer} onChange={(event) => setManufacturer(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-model">Model</Label>
            <Input id="asset-model" value={model} onChange={(event) => setModel(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-firmware">Firmware version</Label>
            <Input id="asset-firmware" value={firmwareVersion} onChange={(event) => setFirmwareVersion(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-os">Operating system</Label>
            <Input id="asset-os" value={operatingSystem} onChange={(event) => setOperatingSystem(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-architecture">Architecture</Label>
            <Input id="asset-architecture" value={architecture} onChange={(event) => setArchitecture(event.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Classification</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-criticality">Criticality</Label>
            <Select id="asset-criticality" value={criticality} onChange={(event) => setCriticality(event.target.value as CriticalityValue)}>
              {CRITICALITY_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="asset-tags">Tags (comma-separated)</Label>
            <Input id="asset-tags" value={tagsInput} onChange={(event) => setTagsInput(event.target.value)} placeholder="prod, tier-1" />
          </div>
        </div>
      </div>

      {error && <p className="text-danger text-sm">{error}</p>}

      <Button type="submit" loading={isSubmitting} className="w-fit">
        Register asset
      </Button>
    </form>
  );
}
