import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettingsLayout } from "@/layouts/settings-layout";

const NAV_ITEMS = [
  { href: "/settings/profile", label: "Profile" },
  { href: "/settings/security", label: "Security" },
];

describe("SettingsLayout", () => {
  it("renders every nav item via the render prop and the content", () => {
    render(
      <SettingsLayout
        navItems={NAV_ITEMS}
        activeHref="/settings/profile"
        renderNavLink={(item, isActive) => (
          <a href={item.href} aria-current={isActive ? "page" : undefined}>
            {item.label}
          </a>
        )}
      >
        <p>settings content</p>
      </SettingsLayout>,
    );

    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Security" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("settings content")).toBeInTheDocument();
  });
});
