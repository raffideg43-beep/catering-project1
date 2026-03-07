"use client";

import { useState } from "react";
import { TabIdentitas } from "./components/TabIdentitas";
import { TabSekolah } from "./components/TabSekolah";
import { TabSupplier } from "./components/TabSupplier";
import { TabBahan } from "./components/TabBahan";
import { TabAlokasi } from "./components/TabAlokasi";
import { TabTelegram } from "./components/TabTelegram";

type TabType = "identitas" | "sekolah" | "supplier" | "bahan" | "alokasi" | "telegram";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabType>("identitas");

  const tabs: { id: TabType; label: string }[] = [
    { id: "identitas", label: "Identitas SPPG" },
    { id: "sekolah", label: "Sekolah" },
    { id: "supplier", label: "Supplier" },
    { id: "bahan", label: "Bahan & BOM" },
    { id: "alokasi", label: "Alokasi MBG" },
    { id: "telegram", label: "Telegram" },
  ];

  return (
    <div className="max-w-6xl mx-auto pb-20">
      <h1 className="text-3xl font-bold mb-8 text-gray-900">Pengaturan Sistem</h1>

      {/* Tab Navigation */}
      <div className="border-b border-gray-300 mb-8 sticky top-0 bg-gray-50 z-10 pt-4">
        <div className="flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 font-medium border-b-2 transition-colors duration-200 whitespace-nowrap ${activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-900"
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 min-h-[500px]">
        {activeTab === "identitas" && <TabIdentitas />}
        {activeTab === "sekolah" && <TabSekolah />}
        {activeTab === "supplier" && <TabSupplier />}
        {activeTab === "bahan" && <TabBahan />}
        {activeTab === "alokasi" && <TabAlokasi />}
        {activeTab === "telegram" && <TabTelegram />}
      </div>
    </div>
  );
}
