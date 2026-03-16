"use client";

import { useState, useEffect } from "react";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";

interface AIAlert {
    level: "high" | "medium" | "low";
    bahan: string;
    pesan: string;
    rekomendasi: string;
}

interface AIOpportunity {
    bahan: string;
    pesan: string;
    estimasi_hemat: string;
}

interface AIInsightData {
    summary: string;
    alerts: AIAlert[];
    opportunities: AIOpportunity[];
    generated_at: string;
    from_cache?: boolean;
}

const alertStyle: Record<string, { card: string; dot: string; icon: string }> = {
    high: { card: "bg-red-50 border-red-200", dot: "bg-red-500", icon: "🔴" },
    medium: { card: "bg-yellow-50 border-yellow-200", dot: "bg-yellow-500", icon: "🟡" },
    low: { card: "bg-green-50 border-green-200", dot: "bg-green-500", icon: "🟢" },
};

export default function AIInsightPage() {
    const [data, setData] = useState<AIInsightData | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchInsight = async (forceRefresh = false) => {
        if (forceRefresh) setRefreshing(true);
        else setLoading(true);
        try {
            const r = await apiGet(`/price-tracking/ai-insights${forceRefresh ? "?force_refresh=true" : ""}`);
            setData(r?.data ?? null);
        } catch { }
        setLoading(false);
        setRefreshing(false);
    };

    useEffect(() => { fetchInsight(); }, []);

    const formatTs = (ts?: string) => {
        if (!ts) return "—";
        try { return new Date(ts).toLocaleString("id-ID"); } catch { return ts; }
    };

    return (
        <div className="space-y-5">
            <PageHeader
                title="🤖 AI Insight Harga"
                subtitle={`Diperbarui: ${formatTs(data?.generated_at)}`}
                actions={
                    <div className="flex items-center gap-2">
                        <Link href="/harga"
                            className="px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
                            ← Kembali
                        </Link>
                        <button
                            onClick={() => fetchInsight(true)}
                            disabled={refreshing}
                            className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-60">
                            {refreshing ? "⏳ Menganalisis..." : "🔄 Refresh Analisis"}
                        </button>
                    </div>
                }
            />

            {loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3">
                    <div className="w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-gray-500 text-sm">⏳ AI sedang menganalisis data harga...</p>
                </div>
            ) : !data || !data.summary ? (
                <div className="text-center py-16 text-gray-400">
                    <p className="text-4xl mb-2">🤖</p>
                    <p className="font-medium text-gray-600">Analisis AI belum tersedia</p>
                    <p className="text-sm mt-1">Pastikan ada data transaksi yang terkonfirmasi.</p>
                </div>
            ) : (
                <>
                    {data.from_cache && (
                        <div className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-1.5 inline-block">
                            📦 Menggunakan data cache (diperbarui otomatis tiap 24 jam)
                        </div>
                    )}

                    {/* Summary */}
                    <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
                        <p className="text-sm font-semibold text-blue-900 mb-1">📋 Ringkasan Kondisi Harga</p>
                        <p className="text-sm text-blue-800 leading-relaxed">{data.summary}</p>
                    </div>

                    {/* Alerts */}
                    {data.alerts && data.alerts.length > 0 && (
                        <div className="space-y-3">
                            <h3 className="font-bold text-gray-800">⚠️ Alert Harga</h3>
                            {data.alerts.map((alert, i) => {
                                const style = alertStyle[alert.level] || alertStyle.low;
                                return (
                                    <div key={i} className={`rounded-xl border p-4 ${style.card}`}>
                                        <div className="flex items-start gap-3">
                                            <span className="text-lg flex-shrink-0 mt-0.5">{style.icon}</span>
                                            <div className="space-y-1 flex-1">
                                                <p className="font-semibold text-gray-900 text-sm">{alert.bahan}</p>
                                                <p className="text-sm text-gray-700">{alert.pesan}</p>
                                                <div className="flex items-start gap-1.5 mt-1">
                                                    <span className="text-xs text-gray-500">💡 Rekomendasi:</span>
                                                    <span className="text-xs font-medium text-gray-800 italic">{alert.rekomendasi}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Opportunities */}
                    {data.opportunities && data.opportunities.length > 0 && (
                        <div className="space-y-3">
                            <h3 className="font-bold text-gray-800">💰 Peluang Penghematan</h3>
                            {data.opportunities.map((opp, i) => (
                                <div key={i} className="bg-green-50 border border-green-200 rounded-xl p-4">
                                    <div className="flex items-start gap-3">
                                        <span className="text-lg flex-shrink-0 mt-0.5">💡</span>
                                        <div className="space-y-1">
                                            <p className="font-semibold text-green-900 text-sm">{opp.bahan}</p>
                                            <p className="text-sm text-green-800">{opp.pesan}</p>
                                            <p className="text-xs font-bold text-green-700">
                                                Estimasi hemat: {opp.estimasi_hemat}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {data.alerts?.length === 0 && data.opportunities?.length === 0 && (
                        <div className="text-center py-8 text-gray-400">
                            <p className="text-2xl mb-2">✅</p>
                            <p className="text-sm">Tidak ada alert atau peluang penghematan yang terdeteksi saat ini.</p>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
