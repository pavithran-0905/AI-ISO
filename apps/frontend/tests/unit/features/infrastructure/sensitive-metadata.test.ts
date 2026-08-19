import { describe, expect, it } from "vitest";

import { isSensitiveMetadataKey, maskMetadataValue } from "@/features/infrastructure/lib/sensitive-metadata";

describe("isSensitiveMetadataKey", () => {
  it.each(["password", "api_key", "apiKey", "private_key", "secret_token", "credential", "auth_token"])(
    "flags %s as sensitive",
    (key) => {
      expect(isSensitiveMetadataKey(key)).toBe(true);
    },
  );

  it.each(["environment", "region", "rack_position", "notes"])("does not flag %s as sensitive", (key) => {
    expect(isSensitiveMetadataKey(key)).toBe(false);
  });
});

describe("maskMetadataValue", () => {
  it("masks a sensitive key's value regardless of its actual content", () => {
    expect(maskMetadataValue("api_key", "sk-real-value-123")).toBe("••••••••");
  });

  it("renders a non-sensitive string value as-is", () => {
    expect(maskMetadataValue("region", "us-east-1")).toBe("us-east-1");
  });

  it("stringifies a non-sensitive non-string value", () => {
    expect(maskMetadataValue("port", 8080)).toBe("8080");
  });
});
