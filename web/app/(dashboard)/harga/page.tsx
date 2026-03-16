"use client";

import { useState, useEffect } from "react";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import Link from "next/link";

function formatRp(val: number | string): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

interface PriceItem {
    product_id: string;
    product_name: string;
    unit: string;
    avg_price_30d: string;
    avg_price_90d: string;
    change_pct: number;
    trend: "naik" | "turun" | "stabil";
    cheapest_supplier: string;
    cheapest_price: string;
    last_purchase: string;
}

interface AISummary {
    summary?: string;
    alerts?: Array<{ level: string; bahan: string; pesan: string; rekomendasi: string }>;
    opportunities?: Array<{ bahan: string; pesan: string; estimasi_hemat: string }>;
}

function TrendBadge({ pct, trend }: { pct: number; trend: string }) {
    if (trend === "naik" && pct > 5) return (
        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">🔴 +{pct.toFixed(1)}%</span>
    );
    if (trend === "naik") return (
        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-yellow-100 text-yellow-700">🟡 +{pct.toFixed(1)}%</span>
    );
    if (trend === "turun") return (
        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700">🟢 {pct.toFixed(1)}%</span>
    );
    return (
        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-500">⚪ {pct.toFixed(1)}%</span>
    );
}

export default function HargaPage() {
    const [items, setItems] = useState<PriceItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [aiSummary, setAiSummary] = useState<AISummary | null>(null);
    const [aiLoading, setAiLoading] = useState(true);

    useEffect(() => {
        apiGet("/price-tracking/overview").then(r => {
            setItems(r?.data?.items ?? []);
        }).catch(() => { }).finally(() => setLoading(false));

        apiGet("/price-tracking/ai-insights").then(r => {
            setAiSummary(r?.data ?? null);
        }).catch(() => { }).finally(() => setAiLoading(false));
    }, []);

    const highAlert = aiSummary?.alerts?.find(a => a.level === "high");

    return (
        <div className="space-y-5">
            <PageHeader
                title="📈 Track Kenaikan Harga"
                subtitle="Pantau pergerakan harga bahan baku dari transaksi terkonfirmasi"
                actions={
                    <Link href="/harga/insight"
                        className="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700">
                        🤖 AI Insight
                    </Link>
                }
            />

            {/* AI Banner */}
            {!aiLoading && (
                <div className={`rounded-xl p-4 border ${highAlert ? "bg-red-50 border-red-200" : "bg-blue-50 border-blue-100"}`}>
                    {highAlert ? (
                        <div className="space-y-1">
                            <p className="text-sm font-semibold text-red-800">🔴 Alert: {highAlert.pesan}</p>
                            {aiSummary?.summary && <p className="text-xs text-red-700">{aiSummary.summary}</p>}
                        </div>
                    ) : aiSummary?.summary ? (
                        <p className="text-sm text-blue-800">{aiSummary.summary}</p>
                    ) : (
                        <p className="text-sm text-blue-600">Analisis AI belum tersedia. Data muncul setelah ada transaksi terkonfirmasi.</p>
                    )}
                    <Link href="/harga/insight" className="text-xs font-medium text-blue-600 hover:underline mt-1 inline-block">
                        Lihat Detail AI →
                    </Link>
                </div>
            )}

            {/* Table */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                {loading ? (
                    <div className="flex justify-center py-16">
                        <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-center py-16 text-gray-400 space-y-2">
                        <p className="text-4xl">📊</p>
                        <p className="font-medium text-gray-600">Belum ada data harga</p>
                        <p className="text-sm">Data muncul setelah ada nota belanja yang dikonfirmasi.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50">
                                <tr>
                                    {["Bahan", "Satuan", "Rata-rata 30 Hari", "Rata-rata 90 Hari", "Perubahan", "Trend", "Supplier Termurah", "Terakhir Beli"].map(h => (
                                        <th key={h} className="text-left px-4 py-2.5 text-gray-500 font-medium text-xs whitespace-nowrap">{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item, i) => (
                                    <tr key={item.product_id} className={`border-b border-gray-50 hover:bg-gray-50 cursor-pointer ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                        <td className="px-4 py-2.5">
                                            <Link href={`/harga/${item.product_id}`}
                                                className="font-medium text-purple-700 hover:underline">
                                                {item.product_name}
                                            </Link>
                                        </td>
                                        <td className="px-4 py-2.5 text-gray-500">{item.unit}</td>
                                        <td className="px-4 py-2.5 font-semibold">{formatRp(item.avg_price_30d)}</td>
                                        <td className="px-4 py-2.5 text-gray-500">{formatRp(item.avg_price_90d)}</td>
                                        <td className="px-4 py-2.5">
                                            <TrendBadge pct={item.change_pct} trend={item.trend} />
                                        </td>
                                        <td className="px-4 py-2.5">
                                            <span className={`text-xs font-medium ${item.trend === "naik" ? "text-red-600" : item.trend === "turun" ? "text-green-600" : "text-gray-500"}`}>
                                                {item.trend === "naik" ? "↗ Naik" : item.trend === "turun" ? "↘ Turun" : "→ Stabil"}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2.5 text-gray-700">
                                            <span className="text-xs">{item.cheapest_supplier}</span>
                                            {parseFloat(item.cheapest_price) > 0 && (
                                                <span className="ml-1 text-green-700 text-xs">({formatRp(item.cheapest_price)})</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-2.5 text-gray-400 text-xs">{item.last_purchase || "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
