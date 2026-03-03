"use client";

import { useState } from "react";

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
    <div className="max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Pengaturan</h1>

      {/* Tab Navigation */}
      <div className="border-b border-gray-300 mb-8">
        <div className="flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 font-medium border-b-2 ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-white p-6 rounded-lg shadow">
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

function TabIdentitas() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Identitas SPPG</h2>
      <p className="text-gray-600">Form identitas SPPG akan ditampilkan di sini.</p>
    </div>
  );
}

function TabSekolah() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Daftar Sekolah</h2>
      <button className="mb-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
        + Tambah Sekolah
      </button>
      <p className="text-gray-600">Tabel daftar sekolah akan ditampilkan di sini.</p>
    </div>
  );
}

function TabSupplier() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Daftar Supplier</h2>
      <button className="mb-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
        + Tambah Supplier
      </button>
      <p className="text-gray-600">Tabel daftar supplier akan ditampilkan di sini.</p>
    </div>
  );
}

function TabBahan() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Bahan & BOM</h2>
      <div className="space-y-6">
        <div>
          <h3 className="text-xl font-semibold mb-4">Bahan Baku</h3>
          <button className="mb-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            + Tambah Bahan
          </button>
          <p className="text-gray-600">Tabel bahan baku akan ditampilkan di sini.</p>
        </div>
        <div>
          <h3 className="text-xl font-semibold mb-4">Resep / BOM</h3>
          <button className="mb-4 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
            + Tambah Resep
          </button>
          <p className="text-gray-600">Tabel resep akan ditampilkan di sini.</p>
        </div>
      </div>
    </div>
  );
}

function TabAlokasi() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Alokasi MBG</h2>
      <p className="text-gray-600 mb-4">
        Atur alokasi dana per porsi untuk Bahan, Upah, dan Operasional.
      </p>
      <div className="space-y-4">
        <input
          type="number"
          placeholder="Harga per Porsi (Rp)"
          className="w-full px-4 py-2 border rounded"
        />
        <input
          type="number"
          placeholder="Alokasi Bahan (Rp)"
          className="w-full px-4 py-2 border rounded"
        />
        <input
          type="number"
          placeholder="Alokasi Upah (Rp)"
          className="w-full px-4 py-2 border rounded"
        />
        <input
          type="number"
          placeholder="Alokasi Operasional (Rp)"
          className="w-full px-4 py-2 border rounded"
        />
        <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          Simpan Alokasi
        </button>
      </div>
    </div>
  );
}

function TabTelegram() {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Koneksi Telegram</h2>
      <div className="bg-gray-100 p-4 rounded mb-4">
        <p className="text-gray-600">❌ Belum terhubung ke Telegram Bot</p>
      </div>
      <button className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
        Generate Kode Linking
      </button>
      <p className="text-sm text-gray-600 mt-4">
        Kode akan berlaku selama 10 menit. Bagikan ke pengguna Telegram Bot
        dengan perintah: /start [kode]
      </p>
    </div>
  );
}
