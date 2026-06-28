import Link from "next/link";

const PAGES = [
  { href: "/journal",          label: "Signal Journal" },
  { href: "/manual-trades",    label: "Manual Trades" },
  { href: "/strategy-metrics", label: "Strategy Metrics" },
] as const;

type PageHref = (typeof PAGES)[number]["href"];

export function PageSubNav({
  currentPage,
  actions,
}: {
  currentPage: PageHref;
  actions?: React.ReactNode;
}) {
  return (
    <header className="border-b border-border px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-1">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Dashboard
        </Link>
        <span className="text-muted-foreground/30 mx-2 select-none">/</span>
        <nav className="flex items-center gap-0.5" aria-label="Analysis tools">
          {PAGES.map(({ href, label }) =>
            href === currentPage ? (
              <span
                key={href}
                aria-current="page"
                className="text-sm font-semibold text-foreground px-2 py-1 rounded"
              >
                {label}
              </span>
            ) : (
              <Link
                key={href}
                href={href}
                className="text-sm text-muted-foreground hover:text-foreground px-2 py-1 rounded transition-colors"
              >
                {label}
              </Link>
            )
          )}
        </nav>
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      )}
    </header>
  );
}
