"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

interface School {
    id: string;
    name: string;
    address: string;
    contact_name: string;
    default_portions: number;
    notes: string;
}

export function TabSekolah() {
    const [schools, setSchools] = useState<School[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        name: "",
        address: "",
        contact_name: "",
        default_portions: 0,
        notes: "",
    });

    const fetchSchools = async () => {
        setLoading(true);
        try {
            const res = await apiGet("/schools");
            setSchools(res?.data?.items || res?.data || []);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchSchools();
    }, []);

    const openForm = (school?: School) => {
        if (school) {
            setEditingId(school.id);
            setFormData({
                name: school.name,
                address: school.address || "",
                contact_name: school.contact_name || "",
                default_portions: school.default_portions,
                notes: school.notes || "",
            });
        } else {
            setEditingId(null);
            setFormData({ name: "", address: "", contact_name: "", default_portions: 0, notes: "" });
        }
        setShowModal(true);
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (editingId) {
                await apiPut(`/schools/${editingId}`, formData);
            } else {
                await apiPost("/schools", formData);
            }
            setShowModal(false);
            fetchSchools();
        } catch (err: any) {
            alert(err?.response?.data?.detail || err?.response?.data?.error || "Gagal menyimpan data sekolah");
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm("Hapus sekolah ini?")) return;
        try {
            await apiDelete(`/schools/${id}`);
            fetchSchools();
        } catch {
            alert("Gagal menghapus sekolah");
        }
    };

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold">Daftar Sekolah</h2>
                <button onClick={() => openForm()} className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium">
                    + Tambah Sekolah
                </button>
            </div>

            {loading ? (
                <div className="text-gray-500">Memuat data...</div>
            ) : schools.length === 0 ? (
                <div className="text-gray-500 text-center py-8">Belum ada data sekolah.</div>
            ) : (
                <div className="overflow-x-auto">
                    <table className="min-w-full text-sm text-left align-middle border-collapse">
                        <thead>
                            <tr className="border-b bg-gray-50">
                                <th className="px-4 py-3 font-semibold text-gray-700">Nama Sekolah</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Penanggung Jawab</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Default Porsi</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Alamat</th>
                                <th className="px-4 py-3 font-semibold text-gray-700">Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schools.map((s) => (
                                <tr key={s.id} className="border-b hover:bg-gray-50">
                                    <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                                    <td className="px-4 py-3 text-gray-600">{s.contact_name || "-"}</td>
                                    <td className="px-4 py-3 text-gray-600 font-medium">{s.default_portions} pjg</td>
                                    <td className="px-4 py-3 text-gray-600 max-w-[200px] truncate">{s.address || "-"}</td>
                                    <td className="px-4 py-3 flex gap-2">
                                        <button onClick={() => openForm(s)} className="text-blue-600 hover:text-blue-800 font-medium px-2 py-1 bg-blue-50 rounded">Edit</button>
                                        <button onClick={() => handleDelete(s.id)} className="text-red-600 hover:text-red-800 font-medium px-2 py-1 bg-red-50 rounded">Hapus</button>
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
                        <h3 className="text-xl font-bold mb-4">{editingId ? "Edit" : "Tambah"} Sekolah</h3>
                        <form onSubmit={handleSave} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Sekolah</label>
                                <input required type="text" value={formData.name} onChange={e => setFormData({ ...formData, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Penanggung Jawab (Opsional)</label>
                                <input type="text" value={formData.contact_name} onChange={e => setFormData({ ...formData, contact_name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Standar Porsi Hari-H</label>
                                <input type="number" required min="0" value={formData.default_portions} onChange={e => setFormData({ ...formData, default_portions: parseInt(e.target.value) || 0 })} className="w-full px-4 py-2 border rounded-lg" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Alamat Lengkap</label>
                                <textarea value={formData.address} onChange={e => setFormData({ ...formData, address: e.target.value })} className="w-full px-4 py-2 border rounded-lg" rows={2} />
                            </div>
                            <div className="flex gap-3 mt-6">
                                <button type="button" onClick={() => setShowModal(false)} className="flex-1 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                                <button type="submit" className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">Simpan</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
