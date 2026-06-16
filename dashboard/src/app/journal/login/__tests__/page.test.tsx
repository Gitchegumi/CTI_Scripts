import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JournalLoginPage, { getRedirectTarget } from "../page";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(),
}));

const fetchMock = vi.fn();
global.fetch = fetchMock as unknown as typeof global.fetch;

beforeEach(() => {
  push.mockClear();
  fetchMock.mockClear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getRedirectTarget", () => {
  it("defaults to /journal when no redirect param is present", () => {
    expect(getRedirectTarget(new URLSearchParams())).toBe("/journal");
  });

  it("honors from", () => {
    expect(getRedirectTarget(new URLSearchParams("from=/manual-trades"))).toBe("/manual-trades");
  });

  it("honors redirect", () => {
    expect(getRedirectTarget(new URLSearchParams("redirect=/journal"))).toBe("/journal");
  });

  it("honors returnTo", () => {
    expect(getRedirectTarget(new URLSearchParams("returnTo=/settings"))).toBe("/settings");
  });

  it("falls back for absolute URLs and open-redirect patterns", () => {
    expect(getRedirectTarget(new URLSearchParams("from=https://evil.example"))).toBe("/journal");
    expect(getRedirectTarget(new URLSearchParams("from=//evil.example"))).toBe("/journal");
    expect(getRedirectTarget(new URLSearchParams("from=javascript:alert(1)"))).toBe("/journal");
  });

  it("uses provided fallback", () => {
    expect(getRedirectTarget(new URLSearchParams(), "/")).toBe("/");
  });
});

describe("JournalLoginPage", () => {
  it("redirects to /journal after successful cookie auth triggered by Enter key", async () => {
    fetchMock.mockResolvedValueOnce({ ok: true } as Response);
    render(<JournalLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Journal token");
    await userEvent.type(passwordInput, "correct-token");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(push).toHaveBeenCalledWith("/journal"));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: "correct-token" }),
    });
  });

  it("stays on the login page and shows an error when auth fails", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false } as Response);
    render(<JournalLoginPage />);

    const passwordInput = screen.getByPlaceholderText("Journal token");
    await userEvent.type(passwordInput, "wrong-token");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => screen.getByText("Invalid token"));
    expect(push).not.toHaveBeenCalled();
  });
});
