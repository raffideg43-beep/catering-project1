"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/ui/status-badge";

interface TransactionItem {
    id: string;
    product_name: string;
    qty: string;
    unit: string;
    price: string;
    subtotal: string;
    product_id?: string;
    alias_matched?: string;
}

interface StockHistoryEntry {
    id: string;
    created_at: string;
    product_name?: string;
    change_qty: string;
    unit?: string;
    reason?: string;
}

interface TransactionDetail {
    id: string;
    date: string;
    nama_toko: string;
    supplier_id?: string;
    payment_method: string;
    due_date?: string;
    created_at: string;
    confirmed_at?: string;
    created_by?: string;
    status: string;
    source?: string;
    photo_url?: string;
    total: string;
    pph22_amount?: string;
    ppn_amount?: string;
    is_pkp?: boolean;
    items: TransactionItem[];
    stock_history?: StockHistoryEntry[];
}

function formatRp(val: string | number): string {
    const n = typeof val === "string" ? parseFloat(val) || 0 : val || 0;
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", minimumFractionDigits: 0 })
        .format(n).replace("IDR", "Rp");
}

function formatDate(iso?: string): string {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleDateString("id-ID", {
            weekday: "long", day: "numeric", month: "long", year: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    } catch { return iso; }
}

export default function TransactionDetailPage() {
    const { id } = useParams<{ id: string }>();
    const router = useRouter();
    const [trx, setTrx] = useState<TransactionDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [confirmLoading, setConfirmLoading] = useState(false);
    const [photoOpen, setPhotoOpen] = useState(false);

    useEffect(() => {
        const fetch = async () => {
            try {
                const r = await apiGet(`/transactions/${id}`);
                setTrx(r?.data ?? r);
            } catch {
                setError("Transaksi tidak ditemukan atau terjadi error.");
            } finally {
                setLoading(false);
            }
        };
        if (id) fetch();
    }, [id]);

    const handleConfirm = async () => {
        if (!confirm("Konfirmasi transaksi ini?")) return;
        setConfirmLoading(true);
        try {
            await apiPost(`/transactions/${id}/confirm`);
            router.push("/pembukuan");
        } catch {
            alert("Gagal konfirmasi.");
            setConfirmLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm("Batalkan transaksi ini? Tindakan tidak dapat dibatalkan.")) return;
        try {
            await apiDelete(`/transactions/${id}`);
            router.push("/pembukuan");
        } catch {
            alert("Gagal membatalkan transaksi.");
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center py-20">
                <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    if (error || !trx) {
        return (
            <div className="text-center py-20 space-y-3">
                <p className="text-4xl">⚠️</p>
                <p className="text-red-600 font-medium">{error ?? "Transaksi tidak ditemukan."}</p>
                <a href="/pembukuan" className="text-blue-600 hover:underline text-sm">← Kembali ke Pembukuan</a>
            </div>
        );
    }

    const pph22 = parseFloat(trx.pph22_amount || "0");
    const ppn = parseFloat(trx.ppn_amount || "0");
    const subtotal = trx.items.reduce((s, i) => s + parseFloat(i.subtotal || "0"), 0);

    return (
        <div className="space-y-5 max-w-4xl">
            <PageHeader
                title="Detail Transaksi"
                backHref="/pembukuan"
                backLabel="Kembali ke Pembukuan"
                actions={
                    <div className="flex gap-2">
                        <StatusBadge status={trx.status} />
                        {trx.source && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{trx.source}</span>}
                    </div>
                }
            />

            {/* ─── Info Transaksi ───────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-3">
                <h2 className="font-semibold text-gray-800">📋 Informasi Transaksi</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-6 text-sm">
                    <Row label="Supplier" value={trx.nama_toko || "—"} />
                    <Row label="Tanggal" value={new Date(trx.date).toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" })} />
                    <Row label="Metode Bayar" value={trx.payment_method || "—"} />
                    {trx.due_date && <Row label="Jatuh Tempo" value={new Date(trx.due_date).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })} />}
                    <Row label="Dibuat" value={formatDate(trx.created_at)} />
                    <Row label="Dikonfirmasi" value={trx.confirmed_at ? formatDate(trx.confirmed_at) : "Belum dikonfirmasi"} />
                    {trx.created_by && <Row label="Oleh" value={trx.created_by} />}
                </div>
            </div>

            {/* ─── Foto Nota ────────────────────────────────────── */}
            {trx.photo_url && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h2 className="font-semibold text-gray-800 mb-3">📷 Foto Nota</h2>
                    <div className="relative inline-block">
                        <img
                            src={trx.photo_url}
                            alt="Foto nota"
                            className="max-h-64 rounded-lg object-contain cursor-pointer border border-gray-200 hover:opacity-90 transition-opacity"
                            onClick={() => setPhotoOpen(true)}
                        />
                    </div>
                    <div className="mt-2">
                        <a href={trx.photo_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline">🔍 Buka Ukuran Penuh</a>
                    </div>
                    {/* Lightbox */}
                    {photoOpen && (
                        <div
                            className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
                            onClick={() => setPhotoOpen(false)}
                        >
                            <img src={trx.photo_url} alt="Nota" className="max-w-full max-h-full rounded-lg" />
                        </div>
                    )}
                </div>
            )}

            {/* ─── Tabel Items ──────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-gray-100">
                    <h2 className="font-semibold text-gray-800">🛒 Daftar Item ({trx.items.length})</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                            <tr>
                                {["No", "Nama Item", "Qty", "Satuan", "Harga Satuan", "Subtotal", "Produk DB"].map(h => (
                                    <th key={h} className="text-left px-4 py-2.5 text-gray-500 font-medium text-xs">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {trx.items.map((item, i) => (
                                <tr key={item.id} className={`border-b border-gray-50 ${i % 2 === 1 ? "bg-gray-50/40" : ""}`}>
                                    <td className="px-4 py-2.5 text-gray-400">{i + 1}</td>
                                    <td className="px-4 py-2.5 font-medium text-gray-800">{item.product_name}</td>
                                    <td className="px-4 py-2.5 text-right">{parseFloat(item.qty).toLocaleString("id-ID")}</td>
                                    <td className="px-4 py-2.5 text-gray-500">{item.unit || "—"}</td>
                                    <td className="px-4 py-2.5 text-right">{formatRp(item.price)}</td>
                                    <td className="px-4 py-2.5 text-right font-semibold">{formatRp(item.subtotal)}</td>
                                    <td className="px-4 py-2.5 text-xs text-gray-400">{item.alias_matched || "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Summary */}
                <div className="px-5 py-4 border-t border-gray-100 space-y-1.5 text-sm">
                    <div className="flex justify-between">
                        <span className="text-gray-500">Subtotal</span>
                        <span className="font-medium">{formatRp(subtotal)}</span>
                    </div>
                    <div className="flex justify-between border-t border-gray-100 pt-2 font-bold text-base">
                        <span>Total</span>
                        <span>{formatRp(trx.total)}</span>
                    </div>
                </div>
            </div>

            {/* ─── Actions ──────────────────────────────────────── */}
            {trx.status === "processing" && (
                <div className="flex gap-3">
                    <button
                        onClick={handleConfirm}
                        disabled={confirmLoading}
                        className="flex-1 sm:flex-none px-6 py-2.5 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-60 transition-colors"
                    >
                        {confirmLoading ? "⏳ Memproses..." : "✅ Konfirmasi Transaksi"}
                    </button>
                    <button
                        onClick={handleDelete}
                        className="flex-1 sm:flex-none px-6 py-2.5 bg-red-100 text-red-600 font-medium rounded-lg hover:bg-red-200 transition-colors"
                    >
                        ❌ Batalkan
                    </button>
                </div>
            )}

            {/* ─── Riwayat Stok ─────────────────────────────────── */}
            {trx.stock_history && trx.stock_history.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h2 className="font-semibold text-gray-800 mb-3">📦 Riwayat Stok Terkait</h2>
                    <div className="space-y-1.5">
                        {trx.stock_history.map((h) => (
                            <div key={h.id} className="flex items-center justify-between text-sm py-1.5 border-b border-gray-50">
                                <div>
                                    <span className="text-gray-700 font-medium">{h.product_name || "—"}</span>
                                    <span className="text-gray-400 ml-2 text-xs">{h.reason}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                    <span className={`font-semibold ${parseFloat(h.change_qty) >= 0 ? "text-green-600" : "text-red-500"}`}>
                                        {parseFloat(h.change_qty) >= 0 ? "+" : ""}{h.change_qty} {h.unit}
                                    </span>
                                    <span className="text-gray-400 text-xs">
                                        {new Date(h.created_at).toLocaleDateString("id-ID")}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function Row({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex gap-2">
            <span className="text-gray-500 min-w-[110px]">{label}</span>
            <span className="font-medium text-gray-800">{value}</span>
        </div>
    );
}
