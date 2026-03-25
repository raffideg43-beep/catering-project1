"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/ui/stat-card";

const MONTHS_FULL = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"];


function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

interface DeliverySummary {
    date: string;
    menu_name: string | null;
    total_portions: number;
    schools_count: number;
    has_delivery: boolean;
    pdf_draft_url?: string | null;
    deliveries?: Array<{ school_name: string; portions_sent: number; receiver_name?: string; status?: string }>;
}

export default function MbgPage() {
    const now = new Date();
    const [bulan, setBulan] = useState(now.getMonth() + 1);
    const [tahun, setTahun] = useState(now.getFullYear());
    const [summaries, setSummaries] = useState<DeliverySummary[]>([]);
    const [monthly, setMonthly] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});
    const [pricePerPortion, setPricePerPortion] = useState(15000);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [mResp, settingsResp] = await Promise.all([
                apiGet("/reports/monthly", { year: tahun, month: bulan }),
                apiGet("/mbg/settings").catch(() => null),
            ]);
            setMonthly(mResp?.data ?? null);
            if (settingsResp?.data?.price_per_portion) {
                setPricePerPortion(Number(settingsResp.data.price_per_portion));
            }

            // Fetch summaries per hari dalam bulan (hanya hari yang ada delivery)
            const lastDay = new Date(tahun, bulan, 0).getDate();
            const dates: string[] = [];
            for (let d = 1; d <= lastDay; d++) {
                dates.push(`${tahun}-${String(bulan).padStart(2, "0")}-${String(d).padStart(2, "0")}`);
            }

            // Batch fetch — ambil hanya summary delivery
            const results = await Promise.allSettled(
                dates.map(d => apiGet("/mbg/deliveries/summary", { date: d }).catch(() => null))
            );

            const filled: DeliverySummary[] = [];
            results.forEach((r, i) => {
                if (r.status === "fulfilled" && r.value?.data?.has_delivery) {
                    filled.push({ date: dates[i], ...r.value.data });
                }
            });
            setSummaries(filled.sort((a, b) => a.date.localeCompare(b.date)));
        } catch { }
        setLoading(false);
    }, [bulan, tahun]);

    useEffect(() => { fetchData(); }, [fetchData]);

    const totalPortions = summaries.reduce((s, d) => s + (d.total_portions || 0), 0);
    const totalGross = totalPortions * pricePerPortion;

    return (
        <div className="space-y-5">
            <PageHeader title="MBG — Penyerahan" subtitle={`${MONTHS_FULL[bulan]} ${tahun}`} />

            {/* Filter */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3 items-end">
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Bulan</label>
                    <select value={bulan} onChange={e => { setBulan(Number(e.target.value)); }}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                        {MONTHS_FULL.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
                    </select>
                </div>
                <div>
                    <label className="block text-xs text-gray-500 mb-1">Tahun</label>
                    <input type="number" value={tahun} onChange={e => setTahun(Number(e.target.value))}
                        className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-24" />
                </div>
                <button onClick={fetchData} className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
                    🔍 Terapkan
                </button>
            </div>

            {/* Summary Cards */}
            {monthly && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard title="Total Porsi" value={`${monthly.mbg?.total_portions?.toLocaleString("id-ID")} porsi`} icon="🍱" />
                    <StatCard title="Hari Kirim" value={`${monthly.mbg?.total_delivery_days} hari`} icon="📅" />
                    <StatCard title="Gross Revenue" value={formatRp(monthly.mbg?.revenue_gross)} icon="💰" />
                    <StatCard title="Rata-rata/Hari" value={`${monthly.mbg?.avg_portions_per_day} porsi`} icon="📊" />
                </div>
            )}

            {/* Info Box */}
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 text-sm text-blue-700">
                💡 Input penyerahan MBG via Telegram Bot <code className="bg-blue-100 px-1 rounded">/serah</code>
                &nbsp;— web hanya untuk monitoring dan download laporan
            </div>

            {/* Tabel Penyerahan */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                    <h2 className="font-semibold text-gray-800">📋 Daftar Penyerahan ({summaries.length} hari)</h2>
                </div>
                {loading ? (
                    <div className="flex justify-center py-12">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : summaries.length === 0 ? (
                    <div className="text-center py-12 text-gray-400">
                        <p className="text-3xl mb-2">📭</p>
                        <p>Belum ada penyerahan di bulan ini</p>
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50">
                                    <tr>
                                        {["Tanggal", "Menu", "Sekolah", "Total Porsi", "Gross", "PDF"].map(h => (
                                            <th key={h} className="text-left px-4 py-2.5 text-gray-500 font-medium text-xs">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {summaries.map((s, i) => {
                                        const gross = s.total_portions * pricePerPortion;
                                        const isExp = expanded[s.date];
                                        const d = new Date(s.date);
                                        return (
                                            <>
                                                <tr key={s.date} className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}
                                                    onClick={() => setExpanded(e => ({ ...e, [s.date]: !e[s.date] }))}>
                                                    <td className="px-4 py-2.5 font-medium">
                                                        {isExp ? "▼" : "▶"}&nbsp;
                                                        {d.toLocaleDateString("id-ID", { weekday: "short", day: "numeric", month: "short" })}
                                                    </td>
                                                    <td className="px-4 py-2.5 text-gray-600">{s.menu_name || "—"}</td>
                                                    <td className="px-4 py-2.5 text-center">{s.schools_count || (s.deliveries?.length ?? "—")}</td>
                                                    <td className="px-4 py-2.5 font-semibold">{s.total_portions.toLocaleString("id-ID")}</td>
                                                    <td className="px-4 py-2.5 text-right">{formatRp(gross)}</td>
                                                    <td className="px-4 py-2.5">
                                                        {s.pdf_draft_url
                                                            ? <a href={s.pdf_draft_url} target="_blank" rel="noopener noreferrer"
                                                                className="text-blue-600 hover:underline text-xs" onClick={e => e.stopPropagation()}>📄 Download</a>
                                                            : <span className="text-gray-300">—</span>}
                                                    </td>
                                                </tr>
                                                {isExp && s.deliveries && s.deliveries.map((school, si) => (
                                                    <tr key={`${s.date}-${si}`} className="bg-blue-50/40 border-b border-blue-50">
                                                        <td className="px-4 py-1.5 pl-10 text-xs text-gray-500 italic" colSpan={3}>
                                                            🏫 {school.school_name}
                                                        </td>
                                                        <td className="px-4 py-1.5 text-xs text-center">{school.portions_sent}</td>
                                                        <td colSpan={1} />
                                                        <td className="px-4 py-1.5 text-xs text-gray-400">{school.status}</td>
                                                    </tr>
                                                ))}
                                            </>
                                        );
                                    })}
                                </tbody>
                                {/* Total row */}
                                <tfoot className="bg-gray-50 border-t-2 border-gray-200">
                                    <tr>
                                        <td className="px-4 py-2.5 font-bold" colSpan={3}>TOTAL</td>
                                        <td className="px-4 py-2.5 font-bold">{totalPortions.toLocaleString("id-ID")}</td>
                                        <td className="px-4 py-2.5 font-bold text-right">{formatRp(totalGross)}</td>
                                        <td />
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
