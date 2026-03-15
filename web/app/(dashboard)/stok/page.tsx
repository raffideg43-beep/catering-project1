"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiDelete, apiPut } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/ui/stat-card";

function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

interface Product {
    id: string;
    name: string;
    category?: string;
    unit: string;
    hpp: string;
    stock_qty: number;
    stock_min: number;
    is_low_stock: boolean;
}

interface HistoryRow {
    id: string;
    change_qty: string;
    running_balance: string;
    reason?: string;
    notes?: string;
    created_at: string;
}

function getStockStatus(qty: number, min: number): { label: string; className: string } {
    if (qty === 0) return { label: "⚫ Habis", className: "text-gray-700 bg-gray-100" };
    if (qty <= min) return { label: "🔴 Kritis", className: "text-red-700 bg-red-100" };
    if (qty <= min * 2) return { label: "⚠️ Menipis", className: "text-yellow-700 bg-yellow-100" };
    return { label: "✅ Aman", className: "text-green-700 bg-green-100" };
}

export default function StokPage() {
    const [category, setCategory] = useState("all");
    const [search, setSearch] = useState("");
    const [items, setItems] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [sortCol, setSortCol] = useState<"status" | "name" | "stock_qty" | "nilai">("status");
    const [sortAsc, setSortAsc] = useState(true);
    const [modalProduct, setModalProduct] = useState<Product | null>(null);
    const [history, setHistory] = useState<HistoryRow[]>([]);
    const [histLoading, setHistLoading] = useState(false);
    const [editingMinStockId, setEditingMinStockId] = useState<string | null>(null);
    const [editMinStockValue, setEditMinStockValue] = useState("");

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const params: any = {};
            if (category !== "all") params.category = category;
            if (search.trim()) params.search = search.trim();
            const r = await apiGet("/reports/stock", params);
            setItems(r?.data?.items ?? []);
        } catch { }
        setLoading(false);
    }, [category, search]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const openHistory = async (p: Product) => {
        setModalProduct(p);
        setHistLoading(true);
        setHistory([]);
        try {
            const r = await apiGet(`/products/${p.id}/history`);
            setHistory(r?.data?.history ?? []);
        } catch { }
        setHistLoading(false);
    };

    // Sort + filter
    const filtered = items.filter(p =>
        !search || p.name.toLowerCase().includes(search.toLowerCase())
    );

    const statusOrder = (p: Product) => {
        if (p.stock_qty === 0) return 0;
        if (p.stock_qty <= p.stock_min) return 1;
        if (p.stock_qty <= p.stock_min * 2) return 2;
        return 3;
    };

    const sorted = [...filtered].sort((a, b) => {
        if (sortCol === "status") return sortAsc ? statusOrder(a) - statusOrder(b) : statusOrder(b) - statusOrder(a);
        if (sortCol === "name") return sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
        if (sortCol === "stock_qty") return sortAsc ? a.stock_qty - b.stock_qty : b.stock_qty - a.stock_qty;
        if (sortCol === "nilai") {
            const av = a.stock_qty * parseFloat(a.hpp || "0");
            const bv = b.stock_qty * parseFloat(b.hpp || "0");
            return sortAsc ? av - bv : bv - av;
        }
        return 0;
    });

    const lowCount = items.filter(p => p.stock_qty <= p.stock_min).length;
    const totalNilai = items.reduce((s, p) => s + p.stock_qty * parseFloat(p.hpp || "0"), 0);

    const handleSort = (col: typeof sortCol) => {
        if (sortCol === col) setSortAsc(a => !a);
        else { setSortCol(col); setSortAsc(true); }
    };

    const handleDeleteProduct = async (p: Product) => {
        if (!confirm(`Hapus "${p.name}" dari daftar stok?`)) return;
        try {
            await apiDelete(`/products/${p.id}`);
            fetchData();
        } catch (err: any) {
            alert(err?.response?.data?.detail || "Gagal menghapus item");
        }
    };

    const handleSaveMinStock = async (p: Product) => {
        try {
            const val = parseFloat(editMinStockValue) || 0;
            await apiPut(`/products/${p.id}`, { stock_min: val });
            setEditingMinStockId(null);
            fetchData();
        } catch (err: any) {
            alert("Gagal update stok minimum.");
        }
    };

    const exportCsv = () => {
        const rows = [["Nama", "Kategori", "Satuan", "HPP", "Stok Saat Ini", "Stok Min", "Nilai Stok"]];
        sorted.forEach(p => rows.push([
            p.name, p.category ?? "", p.unit,
            p.hpp, String(p.stock_qty), String(p.stock_min),
            String(Math.round(p.stock_qty * parseFloat(p.hpp || "0"))),
        ]));
        const csv = rows.map(r => r.join(",")).join("\n");
        const a = document.createElement("a");
        a.href = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
        a.download = "stok_bahan.csv";
        a.click();
    };

    return (
        <div className="space-y-5">
            <PageHeader
                title="Stok Bahan"
                subtitle={`${items.length} item total`}
                actions={
                    <button onClick={exportCsv}
                        className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700">
                        📥 Export CSV
                    </button>
                }
            />

            {/* Summary Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard title="Total Item" value={`${items.length} item`} icon="📦" />
                <StatCard title="Stok Menipis" value={`${lowCount} item`} icon="⚠️" />
                <StatCard title="Nilai Total" value={formatRp(totalNilai)} icon="💰" />
                <StatCard title="Item Aktif" value={`${items.filter(p => p.stock_qty > 0).length} item`} icon="✅" />
            </div>

            {/* Filter */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3 items-end">
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Kategori</label>
                    <select value={category} onChange={e => setCategory(e.target.value)}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                        <option value="all">Semua</option>
                        <option value="bahan_baku">Bahan Baku</option>
                        <option value="produk_jadi">Produk Jadi</option>
                    </select>
                </div>
                <div className="flex-1 min-w-[160px]">
                    <label className="block text-xs text-gray-500 mb-1">Cari</label>
                    <input value={search} onChange={e => setSearch(e.target.value)}
                        placeholder="Nama bahan..." className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-full" />
                </div>
                <button onClick={fetchData} className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
                    🔍 Cari
                </button>
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-700">
                💡 Update stok via Telegram Bot <code className="bg-blue-100 px-1 rounded">/belanja</code>
                , atau dikurangi otomatis saat konfirmasi <code className="bg-blue-100 px-1 rounded">/serah</code>
            </div>

            {/* Tabel */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="flex justify-center py-12">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    {[
                                        { key: "name", label: "Nama" },
                                        { key: null, label: "Kategori" },
                                        { key: null, label: "Satuan" },
                                        { key: null, label: "HPP" },
                                        { key: "stock_qty", label: "Stok Saat Ini" },
                                        { key: null, label: "Stok Min" },
                                        { key: "status", label: "Status" },
                                        { key: "nilai", label: "Nilai Stok" },
                                        { key: null, label: "Aksi" },
                                    ].map(col => (
                                        <th key={col.label}
                                            className={`text-left px-4 py-2.5 text-gray-500 font-medium text-xs whitespace-nowrap ${col.key ? "cursor-pointer hover:text-gray-800" : ""}`}
                                            onClick={() => col.key && handleSort(col.key as any)}>
                                            {col.label}
                                            {col.key === sortCol ? (sortAsc ? " ↑" : " ↓") : ""}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.map((p, i) => {
                                    const nilai = p.stock_qty * parseFloat(p.hpp || "0");
                                    const st = getStockStatus(p.stock_qty, p.stock_min);
                                    return (
                                        <tr key={p.id} className={`border-b border-gray-50 hover:bg-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                            <td className="px-4 py-2.5">
                                                <button onClick={() => openHistory(p)}
                                                    className="font-medium text-blue-700 hover:underline text-left">{p.name}</button>
                                            </td>
                                            <td className="px-4 py-2.5 text-gray-500 text-xs">{p.category || "—"}</td>
                                            <td className="px-4 py-2.5 text-gray-500">{p.unit}</td>
                                            <td className="px-4 py-2.5 text-right">{formatRp(p.hpp)}</td>
                                            <td className="px-4 py-2.5 text-right font-semibold">{p.stock_qty.toLocaleString("id-ID")}</td>
                                            <td className="px-4 py-2.5 text-right text-gray-500 whitespace-nowrap">
                                                {editingMinStockId === p.id ? (
                                                    <div className="flex items-center justify-end gap-2">
                                                        <input type="number" min="0" step="0.1" autoFocus
                                                            value={editMinStockValue} onChange={e => setEditMinStockValue(e.target.value)}
                                                            className="w-20 px-2 py-1 border rounded text-xs bg-white text-right"
                                                            onKeyDown={e => {
                                                                if (e.key === "Enter") handleSaveMinStock(p);
                                                                if (e.key === "Escape") setEditingMinStockId(null);
                                                            }}
                                                        />
                                                        <button onClick={() => handleSaveMinStock(p)} className="text-green-600 hover:text-green-800 text-lg">✅</button>
                                                        <button onClick={() => setEditingMinStockId(null)} className="text-gray-400 hover:text-red-500 text-lg">✕</button>
                                                    </div>
                                                ) : (
                                                    <div className="flex items-center justify-end gap-2 group cursor-pointer" onClick={() => { setEditingMinStockId(p.id); setEditMinStockValue(String(p.stock_min)); }}>
                                                        <span>{p.stock_min.toLocaleString("id-ID")}</span>
                                                        <span className="text-gray-300 group-hover:text-blue-500 transition-colors">✏️</span>
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-4 py-2.5">
                                                <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${st.className}`}>{st.label}</span>
                                            </td>
                                            <td className="px-4 py-2.5 text-right font-medium">{formatRp(nilai)}</td>
                                            <td className="px-4 py-2.5 text-center">
                                                <button onClick={() => handleDeleteProduct(p)} className="text-red-500 hover:text-red-700 text-xs font-medium px-2 py-1 bg-red-50 rounded hover:bg-red-100 transition-colors">🗑️ Hapus</button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                            <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                                <tr>
                                    <td className="px-4 py-2.5 font-bold" colSpan={8}>TOTAL NILAI STOK</td>
                                    <td className="px-4 py-2.5 font-bold text-right">{formatRp(totalNilai)}</td>
                                </tr>
                            </tfoot>
                        </table>
                    </div>
                )}
            </div>

            {/* Modal History */}
            {modalProduct && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
                    onClick={() => setModalProduct(null)}>
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
                        onClick={e => e.stopPropagation()}>
                        <div className="p-5 border-b border-gray-100 flex justify-between items-start">
                            <div>
                                <h2 className="font-bold text-gray-900">{modalProduct.name}</h2>
                                <p className="text-sm text-gray-500">Riwayat Perubahan Stok</p>
                            </div>
                            <button onClick={() => setModalProduct(null)} className="text-gray-400 hover:text-gray-700 text-xl">✕</button>
                        </div>
                        <div className="flex-1 overflow-auto p-5">
                            {histLoading ? (
                                <div className="flex justify-center py-8">
                                    <div className="w-6 h-6 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                                </div>
                            ) : history.length === 0 ? (
                                <p className="text-center text-gray-400 py-8">Belum ada riwayat</p>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            {["Tanggal", "Perubahan", "Saldo", "Alasan", "Notes"].map(h => (
                                                <th key={h} className="text-left px-3 py-2 text-gray-500 font-medium text-xs">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {history.map((h, i) => {
                                            const delta = parseFloat(h.change_qty);
                                            return (
                                                <tr key={h.id} className={`border-b border-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                                    <td className="px-3 py-1.5 whitespace-nowrap text-gray-500 text-xs">
                                                        {new Date(h.created_at).toLocaleDateString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                                                    </td>
                                                    <td className={`px-3 py-1.5 font-semibold ${delta >= 0 ? "text-green-700" : "text-red-500"}`}>
                                                        {delta >= 0 ? "+" : ""}{delta.toLocaleString("id-ID")} {modalProduct.unit}
                                                    </td>
                                                    <td className="px-3 py-1.5 font-medium">
                                                        {parseFloat(h.running_balance).toLocaleString("id-ID")} {modalProduct.unit}
                                                    </td>
                                                    <td className="px-3 py-1.5 text-gray-600 text-xs">{h.reason || "—"}</td>
                                                    <td className="px-3 py-1.5 text-gray-400 text-xs">{h.notes || "—"}</td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
