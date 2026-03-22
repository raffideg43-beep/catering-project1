"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";

interface Transaction {
    id: string;
    date: string;
    nama_toko: string;
    total: string;
    status: string;
    payment_method: string;
    pph22_amount?: string;
    ppn_amount?: string;
    items_count?: number;
    juknis_category?: string;
    payment_date?: string;
    fund_source?: string;
    created_at: string;
}

interface MonthlyData {
    expenses: { total: string; count: number; hutang_outstanding: string };
    excel_status: string;
    period_label: string;
    year: number;
    month: number;
}

function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"];
const MONTHS_FULL = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

export default function PembukuanPage() {
    const now = new Date();
    const [bulan, setBulan] = useState(now.getMonth() + 1);
    const [tahun, setTahun] = useState(now.getFullYear());
    const [status, setStatus] = useState("all");
    const [supplier, setSupplier] = useState("");
    const [juknisFilter, setJuknisFilter] = useState("all");
    const [page, setPage] = useState(0);

    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [monthly, setMonthly] = useState<MonthlyData | null>(null);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [excelLoading, setExcelLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [stalCount, setStalCount] = useState(0); // nota processing > 24 jam

    const LIMIT = 50;

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params: any = { limit: LIMIT, offset: page * LIMIT };
            if (status !== "all") params.status = status;
            if (supplier.trim()) params.supplier = supplier.trim();
            if (juknisFilter !== "all") params.juknis_category = juknisFilter;
            // Date range: bulan/tahun
            const first = `${tahun}-${String(bulan).padStart(2, "0")}-01`;
            const lastDay = new Date(tahun, bulan, 0).getDate();
            const last = `${tahun}-${String(bulan).padStart(2, "0")}-${lastDay}`;
            params.date_from = first;
            params.date_to = last;

            const [trxResp, mResp] = await Promise.all([
                apiGet("/transactions", params),
                apiGet("/reports/monthly", { year: tahun, month: bulan }),
            ]);

            const items = trxResp?.data?.items ?? trxResp?.data ?? [];
            setTransactions(items);
            setTotalCount(trxResp?.data?.total ?? items.length);
            setMonthly(mResp?.data ?? null);

            // Stale nota: processing > 24 jam
            const yesterday = new Date(Date.now() - 86_400_000).toISOString();
            const stale = items.filter(
                (t: Transaction) => t.status === "processing" && t.created_at < yesterday
            );
            setStalCount(stale.length);
        } catch (e: any) {
            setError("Gagal memuat data transaksi.");
        } finally {
            setLoading(false);
        }
    }, [bulan, tahun, status, supplier, juknisFilter, page]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const handleExcel = async () => {
        setExcelLoading(true);
        try {
            const r = await apiGet(`/reports/excel/download?year=${tahun}&month=${bulan}`);
            if (r?.data?.file_url) {
                window.open(r.data.file_url, "_blank");
            } else {
                alert("Excel belum tersedia, coba lagi.");
            }
        } catch {
            alert("Gagal generate Excel. Coba lagi.");
        } finally {
            setExcelLoading(false);
        }
    };

    const handleKonfirmasi = async (id: string) => {
        try {
            await apiPost(`/transactions/${id}/confirm`);
            fetchData();
        } catch {
            alert("Gagal konfirmasi transaksi.");
        }
    };

    return (
        <div className="space-y-5">
            <PageHeader
                title="Pembukuan"
                subtitle={`${MONTHS_FULL[bulan]} ${tahun}`}
                actions={
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleExcel}
                            disabled={excelLoading}
                            className="flex items-center gap-1 px-3 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-60 transition-colors"
                        >
                            {excelLoading ? "⏳..." : `📥 Normal`}
                        </button>
                        <button
                            onClick={async () => {
                                try {
                                    const url = `/reports/excel/download?year=${tahun}&month=${bulan}&format=audit`;
                                    const resp = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${url}`, {
                                        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
                                    });
                                    if (!resp.ok) throw new Error();
                                    const blob = await resp.blob();
                                    const a = document.createElement('a');
                                    a.href = URL.createObjectURL(blob);
                                    a.download = `pembukuan_audit_${tahun}_${String(bulan).padStart(2,'0')}.xlsx`;
                                    a.click();
                                } catch {
                                    alert('Gagal download audit Excel.');
                                }
                            }}
                            className="flex items-center gap-1 px-3 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors"
                        >
                            📋 Untuk Audit
                        </button>
                    </div>
                }
            />

            {/* ─── Filter Bar ─────────────────────────────────── */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
                <div className="flex flex-wrap gap-3 items-end">
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Bulan</label>
                        <select
                            value={bulan}
                            onChange={(e) => { setBulan(Number(e.target.value)); setPage(0); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            {MONTHS_FULL.slice(1).map((m, i) => (
                                <option key={i + 1} value={i + 1}>{m}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Tahun</label>
                        <input
                            type="number"
                            value={tahun}
                            onChange={(e) => { setTahun(Number(e.target.value)); setPage(0); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-blue-300"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Status</label>
                        <select
                            value={status}
                            onChange={(e) => { setStatus(e.target.value); setPage(0); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            <option value="all">Semua</option>
                            <option value="confirmed">Confirmed</option>
                            <option value="processing">Processing</option>
                            <option value="failed">Failed</option>
                        </select>
                    </div>
                    <div className="flex-1 min-w-[160px]">
                        <label className="block text-xs text-gray-500 mb-1">Supplier</label>
                        <input
                            type="text"
                            placeholder="Cari supplier..."
                            value={supplier}
                            onChange={(e) => setSupplier(e.target.value)}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-300"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Kategori Juknis</label>
                        <select
                            value={juknisFilter}
                            onChange={(e) => { setJuknisFilter(e.target.value); setPage(0); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            <option value="all">Semua</option>
                            <option value="bahan_pangan">Bahan Pangan</option>
                            <option value="operasional">Operasional</option>
                            <option value="insentif">Insentif</option>
                            <option value="dana_masuk">Dana Masuk</option>
                        </select>
                    </div>
                    <button
                        onClick={() => { setPage(0); fetchData(); }}
                        className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
                    >
                        🔍 Cari
                    </button>
                    <button
                        onClick={() => { setBulan(now.getMonth() + 1); setTahun(now.getFullYear()); setStatus("all"); setSupplier(""); setJuknisFilter("all"); setPage(0); }}
                        className="px-4 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200"
                    >
                        🔄 Reset
                    </button>
                </div>
            </div>

            {/* ─── Summary Cards ──────────────────────────────── */}
            {monthly && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard title="Total Transaksi" value={`${monthly.expenses.count} nota`} icon="🧾" />
                    <StatCard title="Total Pengeluaran" value={formatRp(monthly.expenses.total)} icon="💸" />
                    <StatCard title="Hutang Outstanding" value={formatRp(monthly.expenses.hutang_outstanding)} icon="📋" />
                    <StatCard title="Status Excel" value={monthly.excel_status === "ready" ? "✅ Siap" : "—"} icon="📊" />
                </div>
            )}

            {/* ─── Warning: Nota Stale ─────────────────────────── */}
            {stalCount > 0 && (
                <div className="flex items-center gap-2 bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-lg text-sm">
                    ⚠️ <strong>{stalCount} nota</strong>&nbsp;belum dikonfirmasi lebih dari 24 jam
                </div>
            )}

            {/* ─── Tabel Transaksi ──────────────────────────────── */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : error ? (
                    <div className="text-center py-12 text-red-500">{error}</div>
                ) : transactions.length === 0 ? (
                    <div className="text-center py-12 text-gray-400 space-y-2">
                        <p className="text-3xl">📭</p>
                        <p className="font-medium">Tidak ada transaksi</p>
                        <p className="text-xs">Coba ubah filter atau catat belanja via Telegram Bot</p>
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50 border-b border-gray-100">
                                    <tr>
                                        {["Tanggal", "Supplier", "Items", "Total", "Kategori", "Tgl Bayar", "Status", "Aksi"].map((h) => (
                                            <th key={h} className="text-left px-4 py-3 text-gray-500 font-medium text-xs whitespace-nowrap">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {transactions.map((trx, i) => {
                                        const pph22 = parseFloat(trx.pph22_amount || "0");
                                        const ppn = parseFloat(trx.ppn_amount || "0");
                                        const juknisColors: Record<string, string> = {
                                            bahan_pangan: "bg-green-100 text-green-700",
                                            operasional: "bg-blue-100 text-blue-700",
                                            insentif: "bg-purple-100 text-purple-700",
                                            dana_masuk: "bg-yellow-100 text-yellow-700",
                                        };
                                        const juknisLabels: Record<string, string> = {
                                            bahan_pangan: "Bahan Pangan",
                                            operasional: "Operasional",
                                            insentif: "Insentif",
                                            dana_masuk: "Dana Masuk",
                                        };
                                        const jCat = trx.juknis_category || "";
                                        const showPayDate = trx.payment_date && trx.payment_date !== trx.date;
                                        return (
                                            <tr key={trx.id} className={`border-b border-gray-50 hover:bg-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                                <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                                                    {new Date(trx.date).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "2-digit" })}
                                                </td>
                                                <td className="px-4 py-3 font-medium text-gray-800 max-w-[140px] truncate">{trx.nama_toko || "—"}</td>
                                                <td className="px-4 py-3 text-center text-gray-500">{trx.items_count ?? "—"}</td>
                                                <td className="px-4 py-3 font-semibold whitespace-nowrap">{formatRp(trx.total)}</td>
                                                <td className="px-4 py-3">
                                                    {jCat ? (
                                                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${juknisColors[jCat] || "bg-gray-100 text-gray-600"}`}>
                                                            {juknisLabels[jCat] || jCat}
                                                        </span>
                                                    ) : <span className="text-gray-300">—</span>}
                                                </td>
                                                <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                                                    {showPayDate ? (
                                                        <span title="Cash basis">
                                                            {new Date(trx.payment_date!).toLocaleDateString("id-ID", { day: "numeric", month: "short" })}
                                                        </span>
                                                    ) : <span className="text-gray-300">—</span>}
                                                </td>
                                                <td className="px-4 py-3"><StatusBadge status={trx.status} /></td>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center gap-2">
                                                        <a href={`/pembukuan/${trx.id}`} className="text-blue-600 hover:underline text-xs">👁 Detail</a>
                                                        {trx.status === "processing" && (
                                                            <button
                                                                onClick={() => handleKonfirmasi(trx.id)}
                                                                className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded hover:bg-green-200"
                                                            >
                                                                ✅
                                                            </button>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination */}
                        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
                            <span>{page * LIMIT + 1}–{Math.min((page + 1) * LIMIT, totalCount)} dari {totalCount}</span>
                            <div className="flex gap-2">
                                <button
                                    disabled={page === 0}
                                    onClick={() => setPage(p => p - 1)}
                                    className="px-3 py-1 border border-gray-200 rounded hover:bg-gray-100 disabled:opacity-40"
                                >← Prev</button>
                                <button
                                    disabled={(page + 1) * LIMIT >= totalCount}
                                    onClick={() => setPage(p => p + 1)}
                                    className="px-3 py-1 border border-gray-200 rounded hover:bg-gray-100 disabled:opacity-40"
                                >Next →</button>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
