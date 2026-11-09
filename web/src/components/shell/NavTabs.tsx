"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "@/lib/i18n/LocaleProvider";

export const VIEWS = [
  { href: "/", key: "agent" },
  { href: "/knowledge", key: "knowledge" },
  { href: "/benchmark", key: "benchmark" },
  { href: "/architecture", key: "architecture" },
] as const;

export function NavTabs() {
  const pathname = usePathname();
  const { t } = useLocale();
  return (
    <nav className="nav" aria-label={t.shell.navLabel}>
      {VIEWS.map((view) => (
        <Link key={view.href} href={view.href} aria-current={pathname === view.href ? "page" : undefined}>
          {t.shell.nav[view.key]}
        </Link>
      ))}
    </nav>
  );
}
