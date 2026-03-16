"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatCard } from "@/components/ui/stat-card";
import Link from "next/link";
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";

function formatRp(val: number | string): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

interface ChartPoint {
    date: string;
    avg_price: number;
    by_supplier: Array<{ supplier_name: string; price: number; qty: number }>;
}

interface SupplierComparison {
    supplier_name: string;
    avg_price: number;
    min_price: number;
    max_price: number;
    purchase_count: number;
}

interface PriceDetailData {
    product_id: string;
    product_name: string;
    unit: string;
    period: string;
    chart_data: ChartPoint[];
    suppliers_comparison: SupplierComparison[];
    stats: {
        min_price: string;
        max_price: string;
        avg_price: string;
        price_volatility: number;
    };
}

export default function HargaDetailPage() {
    const params = useParams();
    const productId = params?.id as string;
    const [period, setPeriod] = useState("1m");
    const [data, setData] = useState<PriceDetailData | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        if (!productId) return;
        setLoading(true);
        try {
            const r = await apiGet(`/price-tracking/${productId}?period=${period}`);
            setData(r?.data ?? null);
        } catch { }
        setLoading(false);
    }, [productId, period]);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Build chart series: all unique supplier names
    const suppliers = Array.from(new Set(
        (data?.chart_data ?? []).flatMap(d => d.by_supplier.map(s => s.supplier_name))
    ));

    // Flatten chart data: each point has a key per supplier
    const chartSeries = (data?.chart_data ?? []).map(point => {
        const obj: Record<string, any> = { date: point.date };
        point.by_supplier.forEach(s => { obj[s.supplier_name] = s.price; });
        obj["Rata-rata"] = point.avg_price;
        return obj;
    });

    const CustomTooltip = ({ active, payload, label }: any) => {
        if (!active || !payload?.length) return null;
        return (
            <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
                <p className="font-semibold text-gray-800 mb-1">{label}</p>
                {payload.map((p: any) => (
                    <p key={p.name} style={{ color: p.color }} className="text-xs">
                        {p.name}: {formatRp(p.value)}
                    </p>
                ))}
            </div>
        );
    };

    return (
        <div className="space-y-5">
            <PageHeader
                title={data?.product_name ? `📈 ${data.product_name}` : "📈 Detail Harga"}
                subtitle={data ? `Satuan: ${data.unit}` : ""}
                actions={
                    <Link href="/harga"
                        className="px-4 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50">
                        ← Kembali
                    </Link>
                }
            />

            {/* Period Toggle */}
            <div className="flex gap-2">
                {[["1m", "1 Bulan"], ["3m", "3 Bulan"], ["12m", "12 Bulan"]].map(([val, label]) => (
                    <button key={val} onClick={() => setPeriod(val)}
                        className={`px-4 py-1.5 text-sm rounded-lg font-medium transition-colors ${period === val ? "bg-purple-600 text-white" : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
                        {label}
                    </button>
                ))}
            </div>

            {loading ? (
                <div className="flex justify-center py-16">
                    <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : !data || data.chart_data.length === 0 ? (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-12 text-center text-gray-400">
                    <p className="text-4xl mb-2">📊</p>
                    <p className="font-medium text-gray-600">Belum ada data harga dalam periode ini</p>
                    <p className="text-sm mt-1">Data muncul setelah ada nota belanja yang dikonfirmasi.</p>
                </div>
            ) : (
                <>
                    {/* Stats Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard title="Harga Terendah" value={formatRp(data.stats.min_price)} icon="📉" />
                        <StatCard title="Harga Tertinggi" value={formatRp(data.stats.max_price)} icon="📈" />
                        <StatCard title="Rata-rata" value={formatRp(data.stats.avg_price)} icon="📊" />
                        <StatCard title="Volatilitas" value={`${data.stats.price_volatility}%`} icon="📐" />
                    </div>

                    {/* Chart */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                        <h3 className="font-bold text-gray-900 mb-4">Grafik Harga per Supplier</h3>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={chartSeries} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 11 }}
                                    tickFormatter={d => d.slice(5)}
                                />
                                <YAxis
                                    tick={{ fontSize: 11 }}
                                    tickFormatter={v => `${(v / 1000).toFixed(0)}k`}
                                />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Line
                                    key="Rata-rata"
                                    type="monotone"
                                    dataKey="Rata-rata"
                                    stroke="#94a3b8"
                                    strokeWidth={1.5}
                                    strokeDasharray="5 5"
                                    dot={false}
                                />
                                {suppliers.map((sup, idx) => (
                                    <Line
                                        key={sup}
                                        type="monotone"
                                        dataKey={sup}
                                        stroke={COLORS[idx % COLORS.length]}
                                        strokeWidth={2}
                                        dot={{ r: 3 }}
                                        activeDot={{ r: 5 }}
                                        connectNulls
                                    />
                                ))}
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    {/* Supplier Comparison */}
                    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                        <div className="px-5 py-4 border-b border-gray-100">
                            <h3 className="font-bold text-gray-900">Perbandingan Supplier</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50">
                                    <tr>
                                        {["Supplier", "Rata-rata", "Termurah", "Termahal", "Frekuensi Beli"].map(h => (
                                            <th key={h} className="text-left px-4 py-2.5 text-gray-500 font-medium text-xs">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.suppliers_comparison.map((sup, i) => (
                                        <tr key={sup.supplier_name}
                                            className={`border-b border-gray-50 ${i === 0 ? "bg-green-50" : i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                            <td className="px-4 py-2.5 font-medium text-gray-800">
                                                {i === 0 && <span className="text-xs text-green-600 mr-1.5">✅</span>}
                                                {sup.supplier_name}
                                            </td>
                                            <td className="px-4 py-2.5 font-semibold">{formatRp(sup.avg_price)}</td>
                                            <td className="px-4 py-2.5 text-green-700">{formatRp(sup.min_price)}</td>
                                            <td className="px-4 py-2.5 text-red-600">{formatRp(sup.max_price)}</td>
                                            <td className="px-4 py-2.5 text-gray-500">{sup.purchase_count}x</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
