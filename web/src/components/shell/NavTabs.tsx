"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const VIEWS = [
  { href: "/", label: "💬 Agent Studio" },
  { href: "/knowledge", label: "📚 Knowledge Base" },
  { href: "/benchmark", label: "📊 Benchmark Lab" },
  { href: "/architecture", label: "🏗️ Architecture & ADRs" },
] as const;

export function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="nav" aria-label="Views">
      {VIEWS.map((view) => (
        <Link key={view.href} href={view.href} aria-current={pathname === view.href ? "page" : undefined}>
          {view.label}
        </Link>
      ))}
    </nav>
  );
}
