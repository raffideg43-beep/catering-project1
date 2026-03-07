"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPut } from "@/lib/api";
import { Rupiah } from "@/components/ui/rupiah";

export function TabAlokasi() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const [formData, setFormData] = useState({
        price_per_portion: 0,
        budget_food: 0,
        budget_labor: 0,
        budget_ops: 0,
    });

    const fetchSettings = async () => {
        setLoading(true);
        try {
            const res = await apiGet("/mbg/allocation-settings");
            if (res?.data) {
                setFormData({
                    price_per_portion: res.data.price_per_portion || 0,
                    budget_food: res.data.budget_food || 0,
                    budget_labor: res.data.budget_labor || 0,
                    budget_ops: res.data.budget_ops || 0,
                });
            }
        } catch (e) {
            console.error(e);
            setError("Gagal memuat pengaturan alokasi saat ini.");
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchSettings();
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: parseInt(e.target.value) || 0 });
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setSuccess("");
        try {
            await apiPut("/mbg/allocation-settings", formData);
            setSuccess("Pengaturan alokasi berhasil disimpan.");
        } catch (err: any) {
            setError(err?.response?.data?.detail || err?.response?.data?.error || "Gagal menyimpan.");
        }
        setSaving(false);
    };

    const subtotal = formData.budget_food + formData.budget_labor + formData.budget_ops;
    const isMatch = subtotal === formData.price_per_portion;

    return (
        <div>
            <h2 className="text-2xl font-bold mb-6">Alokasi Anggaran MBG</h2>
            <p className="text-gray-600 mb-6 max-w-2xl">
                Atur proporsi dana program Makan Bergizi Gratis per porsi.
                Total dari alokasi bahan (Food Cost), upah (Labor Cost), dan operasional (Overhead Cost) harus sama dengan target Harga Pokok.
            </p>

            {loading ? (
                <div className="text-gray-500">Memuat data...</div>
            ) : (
                <div className="max-w-xl">
                    {error && <div className="mb-4 bg-red-50 text-red-600 p-3 rounded-lg text-sm">{error}</div>}
                    {success && <div className="mb-4 bg-green-50 text-green-600 p-3 rounded-lg text-sm">{success}</div>}

                    <form onSubmit={handleSave} className="space-y-4">
                        <div className="bg-blue-50 p-4 rounded-lg border border-blue-100 mb-6">
                            <label className="block text-sm font-semibold text-blue-900 mb-1">
                                Anggaran per Porsi dari Pemerintah (Rp)
                            </label>
                            <input
                                type="number"
                                name="price_per_portion"
                                value={formData.price_per_portion}
                                onChange={handleChange}
                                min="0"
                                className="w-full px-4 py-3 border border-blue-200 rounded-lg text-lg font-bold text-blue-900 focus:ring focus:ring-blue-200"
                            />
                        </div>

                        <div className="grid grid-cols-1 gap-4">
                            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Pagu Bahan Makanan (Food Cost)
                                </label>
                                <div className="flex">
                                    <span className="inline-flex items-center px-3 bg-gray-200 text-gray-600 rounded-l-lg border border-r-0 border-gray-300">Rp</span>
                                    <input
                                        type="number"
                                        name="budget_food"
                                        value={formData.budget_food}
                                        onChange={handleChange}
                                        min="0"
                                        className="w-full px-4 py-2 border rounded-r-lg"
                                    />
                                </div>
                            </div>

                            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Pagu Upah Pegawai (Labor Cost)
                                </label>
                                <div className="flex">
                                    <span className="inline-flex items-center px-3 bg-gray-200 text-gray-600 rounded-l-lg border border-r-0 border-gray-300">Rp</span>
                                    <input
                                        type="number"
                                        name="budget_labor"
                                        value={formData.budget_labor}
                                        onChange={handleChange}
                                        min="0"
                                        className="w-full px-4 py-2 border rounded-r-lg"
                                    />
                                </div>
                            </div>

                            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Pagu Operasional & Kemasan (Overhead Cost)
                                </label>
                                <div className="flex">
                                    <span className="inline-flex items-center px-3 bg-gray-200 text-gray-600 rounded-l-lg border border-r-0 border-gray-300">Rp</span>
                                    <input
                                        type="number"
                                        name="budget_ops"
                                        value={formData.budget_ops}
                                        onChange={handleChange}
                                        min="0"
                                        className="w-full px-4 py-2 border rounded-r-lg"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className={`mt-6 p-4 rounded-lg flex items-center justify-between ${isMatch ? "bg-green-50 border border-green-200 text-green-800" : "bg-red-50 border border-red-200 text-red-800"}`}>
                            <div>
                                <p className="text-sm font-medium">Total Alokasi Evaluasi</p>
                                <p className="text-xl font-bold"><Rupiah amount={subtotal} /></p>
                            </div>
                            <div className="text-right">
                                <p className="text-sm font-medium">{isMatch ? "✅ Tepat Sesuai Porsi" : "❌ Selisih Nominal"}</p>
                                <p className="text-xs mt-1">
                                    {isMatch ? "Siap disimpan." : `Selisih: Rp ${Math.abs(formData.price_per_portion - subtotal).toLocaleString()}`}
                                </p>
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={saving || !isMatch}
                            className="w-full mt-4 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? "Menyimpan..." : "Simpan Konfigurasi"}
                        </button>
                    </form>
                </div>
            )}
        </div>
    );
}
