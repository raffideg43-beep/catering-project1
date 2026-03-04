"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";

function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

const MONTHS_FULL = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

interface Receivable {
    id: string;
    debtor_name: string;
    amount: string;
    pph22_note: string;
    due_date?: string;
    created_at: string;
    status: string;
    days_overdue: number;
}

interface SummaryData {
    total_outstanding: string;
    total_all: string;
    total_paid: string;
    total_overdue: string;
    count: number;
    receivables: Receivable[];
}

export default function PiutangPage() {
    const now = new Date();
    const [status, setStatus] = useState("unpaid");
    const [bulan, setBulan] = useState(now.getMonth() + 1);
    const [tahun, setTahun] = useState(now.getFullYear());
    const [data, setData] = useState<SummaryData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const params: any = { status };
            if (bulan && tahun) { params.month = bulan; params.year = tahun; }
            const r = await apiGet("/reports/receivables", params);
            setData(r?.data ?? null);
        } catch { }
        setLoading(false);
    }, [status, bulan, tahun]);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Sort: overdue dulu, lalu due_date ASC
    const sorted = [...(data?.receivables ?? [])].sort((a, b) => {
        if (b.days_overdue !== a.days_overdue) return b.days_overdue - a.days_overdue;
        return (a.due_date ?? "").localeCompare(b.due_date ?? "");
    });

    return (
        <div className="space-y-5">
            <PageHeader title="Piutang MBG" subtitle="Tagihan ke Pemerintah" />

            {/* Summary Cards */}
            {data && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard title="Total Piutang" value={formatRp(data.total_all)} icon="💰" />
                    <StatCard title="Sudah Lunas" value={formatRp(data.total_paid)} icon="✅" />
                    <StatCard title="Belum Lunas" value={formatRp(data.total_outstanding)} icon="📋" />
                    <StatCard title="Terlambat" value={formatRp(data.total_overdue)} icon="⚠️" />
                </div>
            )}

            {/* Filter */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3 items-end">
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Status</label>
                    <select value={status} onChange={e => setStatus(e.target.value)}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                        <option value="all">Semua</option>
                        <option value="unpaid">Belum Lunas</option>
                        <option value="paid">Lunas</option>
                    </select>
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Bulan</label>
                    <select value={bulan} onChange={e => setBulan(Number(e.target.value))}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                        {MONTHS_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
                    </select>
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Tahun</label>
                    <input type="number" value={tahun} onChange={e => setTahun(Number(e.target.value))}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-24" />
                </div>
                <button onClick={fetchData} className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg">🔍 Cari</button>
            </div>

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-700">
                💡 Piutang dibuat otomatis saat konfirmasi penyerahan MBG via Telegram Bot
                <code className="bg-blue-100 px-1 rounded ml-1">/serah</code>
            </div>

            {/* Tabel */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="flex justify-center py-12">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : sorted.length === 0 ? (
                    <div className="text-center py-12 text-gray-400 space-y-2">
                        <p className="text-3xl">✅</p>
                        <p>Tidak ada piutang untuk filter ini</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    {["Tanggal", "Debitur", "Gross", "PPh22", "Bersih", "Jatuh Tempo", "Status", "Terlambat"].map(h => (
                                        <th key={h} className="text-left px-4 py-2.5 text-gray-500 font-medium text-xs whitespace-nowrap">{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.map((r, i) => {
                                    const amount = parseFloat(r.amount || "0");
                                    // PPh22 dihitung saat Excel, tampilkan — jika belum
                                    const pph22Display = "—";
                                    const bersihDisplay = formatRp(amount); // sama dg gross karena PPh22 belum
                                    const due = r.due_date
                                        ? new Date(r.due_date).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "2-digit" })
                                        : "—";
                                    return (
                                        <tr key={r.id} className={`border-b border-gray-50 hover:bg-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                            <td className="px-4 py-2.5 text-gray-500 text-xs whitespace-nowrap">{r.created_at}</td>
                                            <td className="px-4 py-2.5 font-medium text-gray-800">{r.debtor_name}</td>
                                            <td className="px-4 py-2.5 text-right font-semibold">{formatRp(amount)}</td>
                                            <td className="px-4 py-2.5 text-right text-gray-300 text-xs" title="Dihitung saat generate Excel">{pph22Display}</td>
                                            <td className="px-4 py-2.5 text-right">{bersihDisplay}</td>
                                            <td className="px-4 py-2.5 text-xs whitespace-nowrap">{due}</td>
                                            <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                                            <td className="px-4 py-2.5">
                                                {r.days_overdue > 0
                                                    ? <span className="text-red-500 font-semibold text-xs">{r.days_overdue} hari</span>
                                                    : <span className="text-gray-300 text-xs">—</span>}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
