"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Rupiah } from "@/components/ui/rupiah";

interface Product {
    id: string;
    name: string;
    category: string;
    unit: string;
    stock_qty: number;
    stock_min: number;
    hpp: number;
    sell_price: number;
}

export function TabBahan() {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        name: "",
        category: "bahan_baku",
        unit: "kg",
        hpp: 0,
        sell_price: 0,
        stock_min: 0,
        notes: ""
    });

    const fetchProducts = async () => {
        setLoading(true);
        try {
            const res = await apiGet("/products");
            let data = res?.data?.items || res?.data || [];
            // Filter out 'menu' maybe if we only want bahan, but let's show all or just bahan_baku
            data = data.filter((p: any) => p.category === "bahan_baku" || p.category === "kemasan");
            setProducts(data);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchProducts();
    }, []);

    const openForm = (prod?: Product) => {
        if (prod) {
            setEditingId(prod.id);
            setFormData({
                name: prod.name,
                category: prod.category,
                unit: prod.unit,
                hpp: prod.hpp,
                sell_price: prod.sell_price,
                stock_min: prod.stock_min,
                notes: "",
            });
        } else {
            setEditingId(null);
            setFormData({ name: "", category: "bahan_baku", unit: "kg", hpp: 0, sell_price: 0, stock_min: 0, notes: "" });
        }
        setShowModal(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (editingId) {
                await apiPut(`/products/${editingId}`, formData);
            } else {
                await apiPost("/products", { ...formData, stock_qty: 0 }); // new product starts with 0
            }
            setShowModal(false);
            fetchProducts();
        } catch (err: any) {
            alert(err?.response?.data?.detail || "Gagal menyimpan bahan");
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm("Hapus bahan ini?")) return;
        try {
            await apiDelete(`/products/${id}`);
            fetchProducts();
        } catch {
            alert("Gagal menghapus bahan");
        }
    };

    return (
        <div>
            <h2 className="text-2xl font-bold mb-6">Bahan Baku & Kemasan</h2>

            <div className="flex justify-between items-center mb-4">
                <p className="text-gray-600">Kelola master data bahan baku pembentuk resep Makanan Bergizi Gratis.</p>
                <button onClick={() => openForm()} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium">
                    + Tambah Bahan
                </button>
            </div>

            {loading ? (
                <div className="text-gray-500">Memuat data...</div>
            ) : products.length === 0 ? (
                <div className="text-gray-500 text-center py-8">Belum ada data bahan baku.</div>
            ) : (
                <div className="overflow-x-auto mb-10">
                    <table className="min-w-full text-sm text-left align-middle border-collapse">
                        <thead>
                            <tr className="border-b bg-gray-50">
                                <th className="px-4 py-3 font-semibold text-gray-700">Nama Bahan</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Kategori</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Satuan</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Harga Beli Dasar (HPP)</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Min. Stok</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {products.map((p) => (
                                <tr key={p.id} className="border-b hover:bg-gray-50">
                                    <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                                    <td className="px-4 py-3 text-gray-600 capitalize">{p.category.replace("_", " ")}</td>
                                    <td className="px-4 py-3 text-gray-600">{p.unit}</td>
                                    <td className="px-4 py-3 text-gray-600"><Rupiah amount={p.hpp} /></td>
                                    <td className="px-4 py-3 text-gray-600">{p.stock_min}</td>
                                    <td className="px-4 py-3 flex gap-2">
                                        <button onClick={() => openForm(p)} className="text-blue-600 hover:text-blue-800 font-medium px-2 py-1 bg-blue-50 rounded">Edit</button>
                                        <button onClick={() => handleDelete(p.id)} className="text-red-600 hover:text-red-800 font-medium px-2 py-1 bg-red-50 rounded">Hapus</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {showModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
                        <h3 className="text-xl font-bold mb-4">{editingId ? "Edit" : "Tambah"} Bahan Baku</h3>
                        <form onSubmit={handleSave} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Produk/Bahan</label>
                                <input required type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
                                    <select value={formData.category} onChange={e => setFormData({ ...formData, category: e.target.value })} className="w-full px-4 py-2 border rounded-lg bg-white">
                                        <option value="bahan_baku">Bahan Baku</option>
                                        <option value="kemasan">Kemasan</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Satuan Dasar</label>
                                    <input required placeholder="kg, liter, pcs" type="text" value={formData.unit} onChange={e => setFormData({ ...formData, unit: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Harga Beli (HPP)</label>
                                    <input type="number" required min="0" value={formData.hpp} onChange={e => setFormData({ ...formData, hpp: parseInt(e.target.value) || 0 })} className="w-full px-4 py-2 border rounded-lg" />
                                    <p className="text-xs text-gray-400 mt-1">Estimasi referensi per satuan</p>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Peringatan Min. Stok</label>
                                    <input type="number" required min="0" step="0.1" value={formData.stock_min} onChange={e => setFormData({ ...formData, stock_min: parseFloat(e.target.value) || 0 })} className="w-full px-4 py-2 border rounded-lg" />
                                </div>
                            </div>

                            <div className="flex gap-3 mt-6">
                                <button type="button" onClick={() => setShowModal(false)} className="flex-1 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                                <button type="submit" className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">Simpan</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Placeholder Minimalist Resep */}
            <h2 className="text-2xl font-bold mb-6 pt-6 border-t border-gray-200">Resep / BOM (Menu Harian)</h2>
            <div className="bg-yellow-50 text-yellow-800 p-4 border border-yellow-200 rounded-lg">
                <p className="font-medium">⚠️ Fitur Builder Resep (Bill of Materials) Sedang Dalam Tahap Penyelesaian.</p>
                <p className="text-sm mt-1">Anda sudah dapat mendefinisikan Bahan Baku dan Kemasan Anda di tabel atas, yang mana adalah syarat pertama sebelum dapat membikin Menu MBG yang memiliki daftar resep otomatis.</p>
            </div>
        </div>
    );
}
