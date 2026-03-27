"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Rupiah } from "@/components/ui/rupiah";
import { PageHeader } from "@/components/layout/page-header";

// Types
interface DailyData {
    date: string;
    mbg: {
        total_portions: number;
        total_schools: number;
        menu_name: string | null;
        revenue_gross: string;
        has_delivery: boolean;
    };
    expenses: { total: string; count: number; by_supplier: any[] };
    stock_alerts: Array<{ product_name: string; stock_qty: number; stock_min: number; unit: string; deficit: number }>;
    cashflow: { income: string; outcome: string; net: string };
}

interface MonthlyData {
    year: number;
    month: number;
    period_label: string;
    mbg: { total_portions: number; revenue_gross: string; avg_portions_per_day: number };
    expenses: { total: string; count: number; hutang_outstanding: string };
    profit_estimate: { gross_profit: string };
    stock_summary: { low_stock_count: number };
    excel_status: string;
}

interface Transaction {
    id: string;
    date: string;
    nama_toko: string;
    total: string;
    status: string;
    type: string;
}

function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n)
        .replace("IDR", "Rp");
}

function getGreeting(): string {
    const h = new Date().getHours();
    if (h < 11) return "Selamat pagi";
    if (h < 15) return "Selamat siang";
    return "Selamat sore";
}

function todayLabel(): string {
    return new Date().toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export default function DashboardPage() {
    const router = useRouter();
    const [daily, setDaily] = useState<DailyData | null>(null);
    const [monthly, setMonthly] = useState<MonthlyData | null>(null);
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [tenantName, setTenantName] = useState("SPPG");

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [d, m, t] = await Promise.all([
                apiGet("/reports/daily"),
                apiGet("/reports/monthly"),
                apiGet("/transactions", { limit: 10, sort: "created_at_desc" }),
            ]);
            setDaily(d?.data ?? null);
            setMonthly(m?.data ?? null);
            setTransactions(t?.data?.items ?? t?.data ?? []);
            try {
                const me = await apiGet("/auth/me");
                setTenantName(me?.data?.tenant_name ?? "SPPG");
            } catch { }
        } catch (e: any) {
            setError("Gagal memuat data. Pastikan backend berjalan.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center space-y-3">
                    <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
                    <p className="text-gray-500">Memuat data...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center space-y-3 max-w-md">
                    <p className="text-4xl">⚠️</p>
                    <p className="text-red-600 font-medium">{error}</p>
                    <button onClick={fetchAll} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                        Coba Lagi
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* ─── Greeting ───────────────────────────────────── */}
            <div>
                <h1 className="text-2xl font-bold text-gray-900">
                    {getGreeting()}, {tenantName} 👋
                </h1>
                <p className="text-gray-500 text-sm mt-1">{todayLabel()}</p>
            </div>

            {/* ─── Stat Cards (2x2 di mobile, 4 kolom di desktop) ─ */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                    title="Porsi Hari Ini"
                    value={daily?.mbg.has_delivery ? `${daily.mbg.total_portions.toLocaleString("id-ID")} porsi` : "—"}
                    subtitle={daily?.mbg.has_delivery ? `${daily.mbg.total_schools} sekolah` : "Belum ada serah"}
                    icon="🍱"
                />
                <StatCard
                    title="Pendapatan Bulan Ini"
                    value={monthly ? formatRp(monthly.mbg.revenue_gross) : "—"}
                    subtitle={`${monthly?.mbg.total_portions.toLocaleString("id-ID") ?? 0} total porsi`}
                    icon="💰"
                />
                <StatCard
                    title="Belanja Hari Ini"
                    value={daily ? formatRp(daily.expenses.total) : "—"}
                    subtitle={`${daily?.expenses.count ?? 0} nota`}
                    icon="🛒"
                />
                <StatCard
                    title="Laba Estimasi"
                    value={monthly ? formatRp(monthly.profit_estimate.gross_profit) : "—"}
                    subtitle="Bulan ini"
                    icon="📊"
                />
            </div>

            {/* ─── Baris konten utama: Penyerahan + Stok ────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Penyerahan Hari Ini */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                    <h2 className="font-semibold text-gray-800 mb-3">🍱 Penyerahan Hari Ini</h2>
                    {daily?.mbg.has_delivery ? (
                        <div className="space-y-2">
                            {daily.mbg.menu_name && (
                                <p className="text-sm text-gray-600">Menu: <span className="font-medium">{daily.mbg.menu_name}</span></p>
                            )}
                            <div className="flex justify-between text-sm border-t pt-2 mt-2">
                                <span className="text-gray-500">Total Porsi</span>
                                <span className="font-semibold">{daily.mbg.total_portions.toLocaleString("id-ID")} porsi</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-500">Gross Revenue</span>
                                <span className="font-semibold text-green-700">{formatRp(daily.mbg.revenue_gross)}</span>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-6 text-gray-400">
                            <p className="text-3xl mb-2">⚪</p>
                            <p className="font-medium">Belum ada penyerahan</p>
                            <p className="text-xs mt-1">Konfirmasi via Telegram Bot <code className="bg-gray-100 px-1 rounded">/serah</code></p>
                        </div>
                    )}
                </div>

                {/* Stok Menipis */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                    <h2 className="font-semibold text-gray-800 mb-3">📦 Stok Menipis</h2>
                    {daily?.stock_alerts && daily.stock_alerts.length > 0 ? (
                        <div className="space-y-2">
                            {daily.stock_alerts.slice(0, 5).map((a, i) => (
                                <div key={i} className="flex justify-between items-center text-sm py-1 border-b border-gray-50">
                                    <span className="text-gray-700 font-medium">{a.product_name}</span>
                                    <span className="text-red-500 text-xs font-semibold">
                                        {a.stock_qty}{a.unit} / min {a.stock_min}{a.unit}
                                    </span>
                                </div>
                            ))}
                            <a href="/stok" className="text-xs text-blue-600 hover:underline mt-2 inline-block">
                                Lihat semua stok →
                            </a>
                        </div>
                    ) : (
                        <div className="text-center py-6 text-green-600">
                            <p className="text-3xl mb-2">✅</p>
                            <p className="font-medium">Semua stok aman</p>
                        </div>
                    )}
                </div>
            </div>

            {/* ─── Transaksi Terbaru ────────────────────────────── */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="font-semibold text-gray-800">🧾 Transaksi Terbaru</h2>
                    <a href="/pembukuan" className="text-xs text-blue-600 hover:underline">Lihat semua →</a>
                </div>
                {transactions.length === 0 ? (
                    <p className="text-center text-gray-400 text-sm py-6">Belum ada transaksi bulan ini</p>
                ) : (
                    <div className="overflow-x-auto -mx-5 px-5">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-100">
                                    <th className="text-left py-2 text-gray-500 font-medium">Tanggal</th>
                                    <th className="text-left py-2 text-gray-500 font-medium">Supplier</th>
                                    <th className="text-right py-2 text-gray-500 font-medium">Total</th>
                                    <th className="text-left py-2 text-gray-500 font-medium">Status</th>
                                    <th className="text-left py-2"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {transactions.slice(0, 10).map((trx) => (
                                    <tr key={trx.id} className="border-b border-gray-50 hover:bg-gray-50">
                                        <td className="py-2 text-gray-600">
                                            {new Date(trx.date).toLocaleDateString("id-ID", { day: "numeric", month: "short" })}
                                        </td>
                                        <td className="py-2 text-gray-800 font-medium">{trx.nama_toko || "—"}</td>
                                        <td className="py-2 text-right font-semibold">{formatRp(trx.total)}</td>
                                        <td className="py-2">
                                            <StatusBadge status={trx.status} />
                                        </td>
                                        <td className="py-2 text-right">
                                            <a
                                                href={`/pembukuan/${trx.id}`}
                                                className="text-blue-600 hover:underline text-xs whitespace-nowrap"
                                            >
                                                Lihat Detail
                                            </a>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* ─── Quick Links ──────────────────────────────────── */}
            <div>
                <button
                    onClick={async () => {
                        try {
                            const r = await apiGet("/reports/excel/download");
                            if (r?.data?.file_url) window.open(r.data.file_url, "_blank");
                        } catch { alert("Gagal generate Excel"); }
                    }}
                    className="w-full sm:w-auto bg-blue-50 border border-blue-200 text-blue-700 shadow-sm px-6 py-3 rounded-xl font-medium hover:bg-blue-100 transition-all flex items-center justify-center gap-2"
                >
                    📥 Download Excel Laporan
                </button>
            </div>
        </div>
    );
}
