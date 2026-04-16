"use client";

import { useState } from "react";
import { TabIdentitas } from "./components/TabIdentitas";
import { TabSekolah } from "./components/TabSekolah";
import { TabSupplier } from "./components/TabSupplier";
import { TabAlokasi } from "./components/TabAlokasi";
import { TabTelegram } from "./components/TabTelegram";
import { TabImport } from "./components/TabImport";
import { TabUsers } from "./components/TabUsers";

type TabType = "identitas" | "sekolah" | "supplier" | "alokasi" | "telegram" | "import" | "users";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabType>("identitas");

  const tabs: { id: TabType; label: string }[] = [
    { id: "identitas", label: "Identitas SPPG" },
    { id: "sekolah", label: "Sekolah" },
    { id: "supplier", label: "Supplier" },
    { id: "alokasi", label: "Alokasi MBG" },
    { id: "telegram", label: "Telegram" },
    { id: "import", label: "Import Data" },
    { id: "users", label: "👥 Tim & Akses" },
  ];

  return (
    <div className="max-w-7xl mx-auto pb-20 animate-in mt-2">
      <div className="pt-2">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 bg-clip-text text-transparent bg-gradient-to-r from-gray-900 to-gray-600">
          Pengaturan Sistem
        </h1>
        <p className="text-gray-500 font-medium text-sm mt-1">Kelola data master dan konfigurasi aplikasi MBG.</p>
      </div>

      {/* Tab Navigation */}
      <div className="sticky top-16 z-10 pt-2 pb-2 mt-4 bg-gray-50/80 backdrop-blur-md">
        <div className="flex gap-2 bg-white/70 backdrop-blur-xl rounded-2xl p-2 overflow-x-auto flex-nowrap no-scrollbar border border-white shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)]">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap transition-all duration-300 ${activeTab === tab.id
                  ? "bg-white text-blue-700 shadow-sm ring-1 ring-gray-200/50"
                  : "text-gray-500 hover:text-gray-900 hover:bg-gray-100/50"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-white/80 backdrop-blur-xl p-6 sm:p-8 rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-white min-h-[500px]">
        {activeTab === "identitas" && <TabIdentitas />}
        {activeTab === "sekolah" && <TabSekolah />}
        {activeTab === "supplier" && <TabSupplier />}
        {activeTab === "alokasi" && <TabAlokasi />}
        {activeTab === "telegram" && <TabTelegram />}
        {activeTab === "import" && <TabImport />}
        {activeTab === "users" && <TabUsers />}
      </div>
    </div>
  );
}
