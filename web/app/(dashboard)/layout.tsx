"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthenticated, clearToken } from "@/lib/auth";

type NavItem = 
  | { type: "divider", label: string }
  | { href: string; icon: string; label: string; children?: { href: string; label: string }[] };

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", icon: "🏠", label: "Dashboard" },
  
  { type: "divider", label: "OPERASIONAL" },
  { href: "/pembukuan", icon: "📋", label: "Pembukuan" },
  { href: "/mbg", icon: "🍱", label: "MBG" },
  { href: "/stok", icon: "📦", label: "Stok", children: [{ href: "/stok", label: "📦 Stok Utama" }, { href: "/stok/riwayat", label: "📋 Riwayat" }] },
  { href: "/compliance", icon: "✅", label: "Compliance" },
  
  { type: "divider", label: "KEUANGAN" },
  { href: "/keuangan", icon: "💳", label: "Piutang & Hutang" },
  { href: "/anggaran", icon: "📊", label: "Anggaran" },
  
  { type: "divider", label: "SDM" },
  { href: "/karyawan", icon: "👥", label: "Karyawan" },
  
  { type: "divider", label: "ANALITIK" },
  { href: "/insights", icon: "📈", label: "Insights" },
  
  { type: "divider", label: "LAINNYA" },
  { href: "/settings", icon: "⚙️", label: "Pengaturan" },
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
        ${mobile ? "w-64" : collapsed ? "w-20" : "w-64"}
        bg-white border-r border-gray-200 flex flex-col h-full
        ${mobile ? "" : "transition-all duration-300 ease-in-out"}
      `}
    >
      {/* Logo */}
      <div className="h-16 border-b border-gray-100 flex items-center justify-between px-4">
        {(!collapsed || mobile) ? (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 bg-opacity-10 flex items-center justify-center text-blue-600 font-bold text-lg">M</div>
            <div>
              <h1 className="text-sm font-bold text-gray-900 leading-tight">MBG Catering</h1>
              <p className="text-[10px] text-gray-500 font-medium tracking-wide uppercase">Pembukuan</p>
            </div>
          </div>
        ) : (
          <div className="w-8 h-8 mx-auto rounded-lg bg-blue-600 bg-opacity-10 flex items-center justify-center text-blue-600 font-bold text-lg">M</div>
        )}
        {!mobile && (
          <button
            onClick={() => setCollapsed(c => !c)}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition"
          >
            {collapsed ? "→" : "←"}
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-3 overflow-y-auto no-scrollbar">
        {NAV_ITEMS.map((item, index) => {
          if ("type" in item && item.type === "divider") {
            if (collapsed && !mobile) return <div key={`div-${index}`} className="my-3 border-b border-gray-200 w-8 mx-auto" />;
            return (
              <div key={`div-${index}`} className="px-3 py-2 mt-4 text-[10px] font-bold text-gray-400 tracking-wider uppercase">
                {item.label}
              </div>
            );
          }
          if ("href" in item) {
            const active = isActive(item.href);
            const hasChildren = item.children && (!collapsed || mobile);
            return (
              <div key={item.href}>
                <a
                  href={item.href}
                  className={`
                    flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
                    ${active
                      ? "bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-100 ring-inset"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"}
                  `}
                >
                  <span className={`text-base flex-shrink-0 ${active ? 'grayscale-0' : 'grayscale'}`}>{item.icon}</span>
                  {(!collapsed || mobile) && <span>{item.label}</span>}
                </a>
                {hasChildren && active && (
                  <div className="ml-9 mt-1 space-y-1 border-l-2 border-gray-100 pl-2">
                    {item.children!.map(child => {
                      const childActive = pathname === child.href || pathname.startsWith(child.href + "/");
                      return (
                      <a key={child.href} href={child.href}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-colors
                          ${childActive
                            ? "text-blue-700 bg-blue-50/50 font-semibold"
                            : "text-gray-500 hover:text-gray-900 hover:bg-gray-50"}`}>
                        {child.label}
                      </a>
                    )})}
                  </div>
                )}
              </div>
            );
          }
          return null;
        })}
      </nav>

      {/* Logout */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
        >
          <span className="text-base flex-shrink-0">🚪</span>
          {(!collapsed || mobile) && <span>Logout</span>}
        </button>
      </div>
    </div>
  );

  // Current page title from nav
  const currentPageItem = NAV_ITEMS.find(n => "href" in n && isActive(n.href));
  const currentPage = currentPageItem && "label" in currentPageItem ? currentPageItem.label : "Dashboard";

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
        <div className="bg-white/80 backdrop-blur-md border-b border-gray-200/80 px-4 sm:px-8 h-16 flex items-center justify-between flex-shrink-0 sticky top-0 z-20">
          <div className="flex items-center gap-4">
            <button
              className="md:hidden p-2 -ml-2 rounded-lg hover:bg-gray-100 text-gray-600 transition"
              onClick={() => setMobileOpen(true)}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>
            </button>
            <h2 className="text-xl font-bold tracking-tight text-gray-900">{currentPage}</h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Hari Ini</span>
              <span className="text-sm font-medium text-gray-700">
                {new Date().toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "short", year: "numeric" })}
              </span>
            </div>
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
