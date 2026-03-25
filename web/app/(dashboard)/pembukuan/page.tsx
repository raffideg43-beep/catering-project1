"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPut } from "@/lib/api";
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

    items_count?: number;
    juknis_category?: string;
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
    const [juknisCat, setJuknisCat] = useState("all");
    const [page, setPage] = useState(0);

    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [monthly, setMonthly] = useState<MonthlyData | null>(null);
    const [totalCount, setTotalCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [excelLoading, setExcelLoading] = useState(false);
    const [legalDocs, setLegalDocs] = useState<any[]>([]);
    const [sptLoading, setSptLoading] = useState(false);
    const [bapLoading, setBapLoading] = useState(false);
    
    const [error, setError] = useState<string | null>(null);
    const [stalCount, setStalCount] = useState(0); // nota processing > 24 jam

    const [showOpsModal, setShowOpsModal] = useState(false);
    const [opsForm, setOpsForm] = useState({ name: "", amount: "", cost_date: "", is_recurring: false, notes: "" });
    const [opsSaving, setOpsSaving] = useState(false);

    const LIMIT = 50;

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params: any = { limit: LIMIT, offset: page * LIMIT };
            if (status !== "all") params.status = status;
            if (supplier.trim()) params.supplier = supplier.trim();
            // Date range: bulan/tahun
            const first = `${tahun}-${String(bulan).padStart(2, "0")}-01`;
            const lastDay = new Date(tahun, bulan, 0).getDate();
            const last = `${tahun}-${String(bulan).padStart(2, "0")}-${lastDay}`;
            params.date_from = first;
            params.date_to = last;

            const [trxResp, mResp, legalResp] = await Promise.all([
                apiGet("/transactions", params),
                apiGet("/reports/monthly", { year: tahun, month: bulan }),
                apiGet("/legal/documents", { year: tahun, month: bulan })
            ]);

            const items = trxResp?.data?.items ?? trxResp?.data ?? [];
            setTransactions(items);
            setTotalCount(trxResp?.data?.total ?? items.length);
            setMonthly(mResp?.data ?? null);
            setLegalDocs(legalResp?.data ?? []);

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
    }, [bulan, tahun, status, supplier, page]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const handleGenerateExcel = async () => {
        setExcelLoading(true);
        try {
            await apiPost("/legal/excel-dinas/generate", { year: tahun, month: bulan });
            fetchData();
        } catch {
            alert("Gagal generate Excel. Coba lagi.");
        } finally {
            setExcelLoading(false);
        }
    };

    const handleGenerateSPT = async () => {
        setSptLoading(true);
        try {
            await apiPost("/legal/spt/generate", { year: tahun, month: bulan });
            fetchData();
        } catch (e: any) {
            alert(e.response?.data?.detail || "Gagal generate SPT.");
        } finally {
            setSptLoading(false);
        }
    };

    const handleGenerateBAP = async () => {
        setBapLoading(true);
        try {
            const res = await apiPost("/legal/bap/generate", { year: tahun, month: bulan });
            if (!res.success) {
                alert(res.error || "BAP tidak dapat dibuat.");
            }
            fetchData();
        } catch (e: any) {
             alert(e.response?.data?.detail || "Gagal generate BAP.");
        } finally {
            setBapLoading(false);
        }
    };

    const handleUpdateStatus = async (id: string, status: string) => {
        try {
            await apiPut(`/legal/documents/${id}/status`, { status });
            fetchData();
        } catch {
            alert("Gagal update status.");
        }
    };

    const getDoc = (type: string) => legalDocs.find(d => d.doc_type === type);
    const excelDoc = getDoc("excel_dinas");
    const sptDoc = getDoc("spt");
    const bapDoc = getDoc("bap");

    const handleSaveOps = async (e: React.FormEvent) => {
        e.preventDefault();
        setOpsSaving(true);
        try {
            await apiPost("/operational", {
                ...opsForm,
                amount: Number(opsForm.amount)
            });
            setShowOpsModal(false);
            setOpsForm({ name: "", amount: "", cost_date: "", is_recurring: false, notes: "" });
            fetchData();
        } catch (e: any) {
            alert(e.message || "Gagal menyimpan biaya operasional");
        } finally {
            setOpsSaving(false);
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
                    <div className="flex gap-2">
                        <button
                            onClick={() => setShowOpsModal(true)}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
                        >
                            + Biaya Operasional
                        </button>
                    </div>
                }
            />

            {/* ─── DOKUMEN LEGAL & EXCEL SECTION ─────────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                
                {/* EXCEL DINAS */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col">
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex gap-3">
                            <span className="text-3xl">📊</span>
                            <div>
                                <h3 className="font-bold text-gray-900">Excel Dinas {MONTHS[bulan]} {tahun}</h3>
                                <p className="text-sm text-gray-500">10 Sheet Laporan Lengkap</p>
                            </div>
                        </div>
                    </div>
                    
                    <div className="mb-4">
                        <div className="text-sm flex items-center justify-between py-1">
                            <span className="text-gray-500">Status:</span>
                            <span className={`font-medium ${excelDoc ? "text-green-600" : "text-gray-500"}`}>
                                {excelDoc ? "✅ Siap didownload" : "⚪ Belum digenerate"}
                            </span>
                        </div>
                        {excelDoc && (
                           <div className="text-xs text-gray-400 mt-1">Generated: {new Date(excelDoc.generated_at).toLocaleString("id-ID")}</div>
                        )}
                    </div>
                    
                    <div className="mt-auto flex flex-col gap-2">
                        {excelDoc && (
                            <a href={excelDoc.file_url} target="_blank" rel="noopener noreferrer" className="w-full py-2 bg-green-50 text-green-700 hover:bg-green-100 rounded-lg text-sm font-medium text-center transition-colors">
                                📥 Download Excel
                            </a>
                        )}
                        <button onClick={handleGenerateExcel} disabled={excelLoading} className="w-full py-2 border border-blue-200 text-blue-600 hover:bg-blue-50 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50">
                            {excelLoading ? "⏳ Generating..." : excelDoc ? "🔄 Generate Ulang" : "➕ Generate Excel"}
                        </button>
                    </div>
                </div>

                {/* SPT */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col">
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex gap-3">
                            <span className="text-3xl">📋</span>
                            <div>
                                <h3 className="font-bold text-gray-900">SPT</h3>
                                <p className="text-sm text-gray-500">Surat Pernyataan Tanggung Jawab</p>
                            </div>
                        </div>
                    </div>
                    
                    <div className="mb-4">
                        <div className="text-sm flex items-center justify-between py-1">
                            <span className="text-gray-500">Status:</span>
                            <span className={`font-medium ${!sptDoc ? "text-gray-500" : sptDoc.status === "draft" ? "text-orange-500" : sptDoc.status === "final" ? "text-green-600" : "text-blue-600"}`}>
                                {!sptDoc ? "⚪ Belum digenerate" : sptDoc.status === "draft" ? "📝 Draft (Belum TTD)" : sptDoc.status === "final" ? "✅ Final (Sudah TTD)" : "📤 Submitted"}
                            </span>
                        </div>
                        {sptDoc && (
                           <div className="text-xs text-gray-400 mt-1">Generated: {new Date(sptDoc.generated_at).toLocaleString("id-ID")}</div>
                        )}
                    </div>
                    
                    <div className="mt-auto flex flex-col gap-2">
                        {sptDoc && (
                            <div className="grid grid-cols-2 gap-2">
                                <a href={sptDoc.file_url} target="_blank" rel="noopener noreferrer" className="py-2 bg-gray-50 text-gray-700 hover:bg-gray-100 rounded-lg text-sm font-medium text-center transition-colors">
                                    📥 Download PDF
                                </a>
                                {sptDoc.status === "draft" ? (
                                    <button onClick={() => handleUpdateStatus(sptDoc.id, "final")} className="py-2 bg-green-500 text-white hover:bg-green-600 rounded-lg text-sm font-medium transition-colors cursor-pointer">
                                        ✅ Tandai Final
                                    </button>
                                ) : sptDoc.status === "final" ? (
                                    <button onClick={() => handleUpdateStatus(sptDoc.id, "submitted")} className="py-2 bg-blue-500 text-white hover:bg-blue-600 rounded-lg text-sm font-medium transition-colors cursor-pointer">
                                        📤 Tandai Submitted
                                    </button>
                                ) : (
                                    <div className="py-2 bg-blue-50 text-blue-600 rounded-lg text-sm font-medium text-center">✔ Submitted</div>
                                )}
                            </div>
                        )}
                        <button onClick={handleGenerateSPT} disabled={sptLoading} className="w-full py-2 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50">
                            {sptLoading ? "⏳ Generating..." : sptDoc ? "🔄 Generate Ulang" : "➕ Generate SPT"}
                        </button>
                    </div>
                </div>

                {/* BAP */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col">
                    <div className="flex justify-between items-start mb-4">
                        <div className="flex gap-3">
                            <span className="text-3xl">📝</span>
                            <div>
                                <h3 className="font-bold text-gray-900">BAP Kas</h3>
                                <p className="text-sm text-gray-500">Berita Acara Pemeriksaan Sisa Kas</p>
                            </div>
                        </div>
                    </div>
                    
                    <div className="mb-4">
                        <div className="text-sm flex items-center justify-between py-1">
                            <span className="text-gray-500">Status:</span>
                            <span className={`font-medium ${!bapDoc ? "text-gray-400" : bapDoc.status === "draft" ? "text-orange-500" : bapDoc.status === "final" ? "text-green-600" : "text-blue-600"}`}>
                                {!bapDoc ? "⚪ Tidak Ada / N/A" : bapDoc.status === "draft" ? "📝 Draft (Belum TTD)" : bapDoc.status === "final" ? "✅ Final (Sudah TTD)" : "📤 Submitted"}
                            </span>
                        </div>
                        {!bapDoc && <div className="text-xs text-gray-400 mt-1 italic">Hanya dibuat jika ada pengembalian sisa dana kas ke negara</div>}
                        {bapDoc && (
                           <div className="text-xs text-gray-400 mt-1">Generated: {new Date(bapDoc.generated_at).toLocaleString("id-ID")}</div>
                        )}
                    </div>
                    
                    <div className="mt-auto flex flex-col gap-2">
                        {bapDoc && (
                            <div className="grid grid-cols-2 gap-2">
                                <a href={bapDoc.file_url} target="_blank" rel="noopener noreferrer" className="py-2 bg-gray-50 text-gray-700 hover:bg-gray-100 rounded-lg text-sm font-medium text-center transition-colors">
                                    📥 Download PDF
                                </a>
                                {bapDoc.status === "draft" ? (
                                    <button onClick={() => handleUpdateStatus(bapDoc.id, "final")} className="py-2 bg-green-500 text-white hover:bg-green-600 rounded-lg text-sm font-medium transition-colors cursor-pointer">
                                        ✅ Tandai Final
                                    </button>
                                ) : bapDoc.status === "final" ? (
                                    <button onClick={() => handleUpdateStatus(bapDoc.id, "submitted")} className="py-2 bg-blue-500 text-white hover:bg-blue-600 rounded-lg text-sm font-medium transition-colors cursor-pointer">
                                        📤 Tandai Submitted
                                    </button>
                                ) : (
                                    <div className="py-2 bg-blue-50 text-blue-600 rounded-lg text-sm font-medium text-center">✔ Submitted</div>
                                )}
                            </div>
                        )}
                        <button onClick={handleGenerateBAP} disabled={bapLoading} title="Hanya akan berhasil jika ada Sisa Kas setelah perhitungan operasional" className="w-full py-2 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg text-sm font-medium transition-colors cursor-pointer disabled:opacity-50">
                            {bapLoading ? "⏳ Generating..." : bapDoc ? "🔄 Generate Ulang" : "➕ Generate BAP (Cek Sisa)"}
                        </button>
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">Log Transaksi & Pengeluaran</h2>
                <a href="/pembukuan/dokumen" className="text-sm text-blue-600 font-medium hover:underline">Lihat Semua Dokumen →</a>
            </div>

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
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Kategori Juknis</label>
                        <select
                            value={juknisCat}
                            onChange={(e) => { setJuknisCat(e.target.value); setPage(0); }}
                            className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                            <option value="all">Semua</option>
                            <option value="bahan_pangan">🥦 Bahan Pangan</option>
                            <option value="operasional">⚙️ Operasional</option>
                            <option value="insentif">👷 Insentif</option>
                            <option value="dana_masuk">💰 Dana Masuk</option>
                            <option value="lainnya">📦 Lainnya</option>
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
                    <button
                        onClick={() => { setPage(0); fetchData(); }}
                        className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
                    >
                        🔍 Cari
                    </button>
                    <button
                        onClick={() => { setBulan(now.getMonth() + 1); setTahun(now.getFullYear()); setStatus("all"); setSupplier(""); setPage(0); }}
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
                                        {["Tanggal", "Supplier", "Items", "Total", "Kategori", "Status", "Aksi"].map((h) => (
                                            <th key={h} className="text-left px-4 py-3 text-gray-500 font-medium text-xs whitespace-nowrap">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {transactions.map((trx, i) => {

                                        return (
                                            <tr key={trx.id} className={`border-b border-gray-50 hover:bg-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                                <td className="px-4 py-3 whitespace-nowrap text-gray-600">
                                                    {new Date(trx.date).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "2-digit" })}
                                                </td>
                                                <td className="px-4 py-3 font-medium text-gray-800 max-w-[140px] truncate">{trx.nama_toko || "—"}</td>
                                                <td className="px-4 py-3 text-center text-gray-500">{trx.items_count ?? "—"}</td>
                                                <td className="px-4 py-3 font-semibold whitespace-nowrap">{formatRp(trx.total)}</td>
                                                <td className="px-4 py-3">
                                                    {(() => {
                                                        const cat = trx.juknis_category || "lainnya";
                                                        const colors: Record<string, string> = {
                                                            bahan_pangan: "bg-green-100 text-green-700",
                                                            operasional: "bg-blue-100 text-blue-700",
                                                            insentif: "bg-purple-100 text-purple-700",
                                                            dana_masuk: "bg-yellow-100 text-yellow-700",
                                                            lainnya: "bg-gray-100 text-gray-600",
                                                        };
                                                        const labels: Record<string, string> = {
                                                            bahan_pangan: "Bahan",
                                                            operasional: "Ops",
                                                            insentif: "Insentif",
                                                            dana_masuk: "Dana Masuk",
                                                            lainnya: "Lain",
                                                        };
                                                        return (
                                                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${colors[cat] || colors.lainnya}`}>
                                                                {labels[cat] || cat}
                                                            </span>
                                                        );
                                                    })()}
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

            {/* Modal Biaya Operasional */}
            {showOpsModal && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 relative">
                        <h3 className="text-xl font-bold mb-4">Catat Biaya Operasional</h3>
                        <form onSubmit={handleSaveOps} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-1">Nama Biaya</label>
                                <input required placeholder="Contoh: Beli Gas 3kg" value={opsForm.name} onChange={e => setOpsForm({...opsForm, name: e.target.value})} className="w-full p-2 border rounded-lg" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Nominal (Rp)</label>
                                <input required type="number" min="0" value={opsForm.amount} onChange={e => setOpsForm({...opsForm, amount: e.target.value})} className="w-full p-2 border rounded-lg" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Tanggal</label>
                                <input required type="date" value={opsForm.cost_date} onChange={e => setOpsForm({...opsForm, cost_date: e.target.value})} className="w-full p-2 border rounded-lg" />
                            </div>
                            <div className="flex items-center gap-2">
                                <input type="checkbox" id="is_recurring" checked={opsForm.is_recurring} onChange={e => setOpsForm({...opsForm, is_recurring: e.target.checked})} className="w-4 h-4 rounded text-blue-600" />
                                <label htmlFor="is_recurring" className="text-sm font-medium">Biaya Rutin Bulanan</label>
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1">Catatan (Opsional)</label>
                                <textarea value={opsForm.notes} onChange={e => setOpsForm({...opsForm, notes: e.target.value})} className="w-full p-2 border rounded-lg" rows={2} />
                            </div>
                            <div className="flex justify-end gap-2 pt-2">
                                <button type="button" onClick={() => setShowOpsModal(false)} className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm font-medium cursor-pointer">Batal</button>
                                <button type="submit" disabled={opsSaving} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50 cursor-pointer">
                                    {opsSaving ? "Menyimpan..." : "Simpan"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
