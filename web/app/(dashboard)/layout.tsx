"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthenticated, clearToken } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", icon: "🏠", label: "Dashboard" },
  { href: "/anggaran", icon: "📊", label: "Anggaran" },
  { href: "/pembukuan", icon: "📋", label: "Pembukuan" },
  { href: "/mbg", icon: "🍱", label: "MBG" },
  {
    href: "/stok", icon: "📦", label: "Stok",
    children: [
      { href: "/stok", label: "📦 Stok Utama" },
      { href: "/stok/riwayat", label: "📋 Riwayat" },
    ]
  },
  { href: "/piutang", icon: "💰", label: "Piutang" },
  { href: "/hutang", icon: "💸", label: "Hutang" },
  {
    href: "/harga", icon: "📈", label: "Track Harga",
    children: [
      { href: "/harga", label: "📊 Overview" },
      { href: "/harga/insight", label: "🤖 AI Insight" },
    ]
  },
  { href: "/jadwal", icon: "📅", label: "AI Jadwal" },
  { href: "/settings", icon: "⚙️", label: "Pengaturan" },
  { href: "/import", icon: "📥", label: "Import Data" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [isReady, setIsReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
    }
    setIsReady(true);
  }, [router]);

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  if (!isReady) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-100">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  const Sidebar = ({ mobile = false }: { mobile?: boolean }) => (
    <div
      className={`
        ${mobile ? "w-64" : collapsed ? "w-16" : "w-60"}
        bg-gray-900 text-white flex flex-col h-full
        ${mobile ? "" : "transition-all duration-200"}
      `}
    >
      {/* Logo */}
      <div className="p-4 border-b border-gray-700 flex items-center justify-between">
        {(!collapsed || mobile) && (
          <div>
            <h1 className="text-lg font-bold tracking-tight">MBG</h1>
            <p className="text-xs text-gray-400">Pembukuan</p>
          </div>
        )}
        {!mobile && (
          <button
            onClick={() => setCollapsed(c => !c)}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white ml-auto"
          >
            {collapsed ? "→" : "←"}
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-y-auto">
        {NAV_ITEMS.map(item => {
          const active = isActive(item.href);
          const hasChildren = (item as any).children && (!collapsed || mobile);
          return (
            <div key={item.href}>
              <a
                href={item.href}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  ${active
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"}
                `}
              >
                <span className="text-base flex-shrink-0">{item.icon}</span>
                {(!collapsed || mobile) && <span>{item.label}</span>}
              </a>
              {hasChildren && active && (
                <div className="ml-8 mt-0.5 space-y-0.5">
                  {((item as any).children as { href: string; label: string }[]).map(child => (
                    <a key={child.href} href={child.href}
                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                        ${pathname === child.href || pathname.startsWith(child.href + "/")
                          ? "bg-blue-500 text-white"
                          : "text-gray-400 hover:bg-gray-700 hover:text-white"}`}>
                      {child.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="p-2 border-t border-gray-700">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <span className="text-base flex-shrink-0">🚪</span>
          {(!collapsed || mobile) && <span>Logout</span>}
        </button>
      </div>
    </div>
  );

  // Current page title from nav
  const currentPage = NAV_ITEMS.find(n => isActive(n.href))?.label ?? "Dashboard";

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex flex-col h-full">
        <Sidebar />
      </div>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 h-full z-50">
            <Sidebar mobile />
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar */}
        <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              className="md:hidden p-1.5 rounded hover:bg-gray-100 text-gray-600"
              onClick={() => setMobileOpen(true)}
            >
              ☰
            </button>
            <h2 className="text-lg font-semibold text-gray-900">{currentPage}</h2>
          </div>
          <div className="text-xs text-gray-400 hidden sm:block">
            {new Date().toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 sm:p-6">
          {children}
        </div>
      </div>
    </div>
  );
}
