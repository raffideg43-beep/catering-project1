"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthenticated, clearToken } from "@/lib/auth";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);
  const [userName, setUserName] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
    }
    setIsReady(true);
  }, [router]);

  if (!isReady) {
    return <div>Loading...</div>;
  }

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? "w-64" : "w-20"} bg-gray-900 text-white transition-all`}>
        <div className="p-4 border-b border-gray-700">
          <h1 className={sidebarOpen ? "text-xl font-bold" : "hidden"}>MBG</h1>
        </div>
        <nav className="mt-8 space-y-4 px-4">
          <a href="/dashboard/pembukuan" className="block p-3 hover:bg-gray-800 rounded">
            📊 {sidebarOpen && "Pembukuan"}
          </a>
          <a href="/dashboard/hutang-piutang" className="block p-3 hover:bg-gray-800 rounded">
            💸 {sidebarOpen && "Hutang & Piutang"}
          </a>
          <a href="/dashboard/stok" className="block p-3 hover:bg-gray-800 rounded">
            📦 {sidebarOpen && "Stok Gudang"}
          </a>
          <a href="/dashboard/jadwal" className="block p-3 hover:bg-gray-800 rounded">
            🤖 {sidebarOpen && "AI Jadwal"}
          </a>
          <a href="/dashboard/track-harga" className="block p-3 hover:bg-gray-800 rounded">
            📈 {sidebarOpen && "Track Harga"}
          </a>
          <a href="/dashboard/laporan" className="block p-3 hover:bg-gray-800 rounded">
            📄 {sidebarOpen && "Laporan"}
          </a>
          <a href="/dashboard/settings" className="block p-3 hover:bg-gray-800 rounded">
            ⚙️ {sidebarOpen && "Pengaturan"}
          </a>
        </nav>
        <div className="absolute bottom-4 left-4">
          <button
            onClick={handleLogout}
            className="p-3 hover:bg-gray-800 rounded w-full text-left"
          >
            🚪 {sidebarOpen && "Logout"}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Top Bar */}
        <div className="bg-white shadow px-8 py-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold">Dashboard</h2>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-gray-200 rounded"
          >
            ☰
          </button>
        </div>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-8">{children}</div>
      </div>
    </div>
  );
}
