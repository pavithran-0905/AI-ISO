import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettingsLayout } from "@/layouts/settings-layout";

const NAV_ITEMS = [
  { href: "/settings/profile", label: "Profile" },
  { href: "/settings/security", label: "Security" },
];

function renderLink(item: (typeof NAV_ITEMS)[number], isActive: boolean) {
  return (
    <a href={item.href} aria-current={isActive ? "page" : undefined}>
      {item.label}
    </a>
  );
}

describe("SettingsLayout", () => {
  it("renders every nav item via the render prop, the title, and the content", () => {
    render(
      <SettingsLayout
        title="Profile"
        navItems={NAV_ITEMS}
        activeHref="/settings/profile"
        renderNavLink={renderLink}
      >
        <p>settings content</p>
      </SettingsLayout>,
    );

    expect(screen.getByRole("link", { name: "Profile" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Security" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("heading", { name: "Profile" })).toBeInTheDocument();
    expect(screen.getByText("settings content")).toBeInTheDocument();
  });

  it("renders the save/cancel action area when actions are provided", () => {
    render(
      <SettingsLayout
        title="Profile"
        navItems={NAV_ITEMS}
        activeHref="/settings/profile"
        renderNavLink={renderLink}
        actions={
          <>
            <button>Cancel</button>
            <button>Save</button>
          </>
        }
      >
        <p>settings content</p>
      </SettingsLayout>,
    );

    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("shows an unsaved-changes indicator and warns on tab close when dirty", () => {
    render(
      <SettingsLayout
        title="Profile"
        navItems={NAV_ITEMS}
        activeHref="/settings/profile"
        renderNavLink={renderLink}
        hasUnsavedChanges
      >
        <p>settings content</p>
      </SettingsLayout>,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();

    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it("omits the unsaved-changes indicator and beforeunload guard when not dirty", () => {
    render(
      <SettingsLayout title="Profile" navItems={NAV_ITEMS} activeHref="/settings/profile" renderNavLink={renderLink}>
        <p>settings content</p>
      </SettingsLayout>,
    );

    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();

    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});
