"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

/* ═══ Types ════════════════════════════════════════════════════════════════ */

interface School {
    id: string;
    name: string;
    default_portions: number;
}

interface SchoolTiming {
    school_id: string;
    school_name: string;
    default_portions: number;
    target_arrival: string;
    travel_minutes: number;
    depart_time?: string;
}

/* ═══ Helpers ══════════════════════════════════════════════════════════════ */

function subtractMinutes(t: string, m: number): string {
    const [h, min] = t.split(":").map(Number);
    let total = h * 60 + min - m;
    if (total < 0) total = 0;
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/* ═══ Main Page ═══════════════════════════════════════════════════════════ */

export default function MasterSchedulePage() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState("");

    // Kitchen settings
    const [prepTime, setPrepTime] = useState("06:30");
    const [cookTime, setCookTime] = useState("07:00");
    const [cookPer100, setCookPer100] = useState(30);

    // All schools
    const [allSchools, setAllSchools] = useState<School[]>([]);
    // School timings
    const [timings, setTimings] = useState<SchoolTiming[]>([]);

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [masterRes, schoolsRes] = await Promise.all([
                apiGet("/schedules/master"),
                apiGet("/schools"),
            ]);

            const schools: School[] = schoolsRes?.data || [];
            setAllSchools(schools);

            const master = masterRes?.data;
            if (master) {
                setPrepTime(master.prep_start_time || "06:30");
                setCookTime(master.cook_start_time || "07:00");
                setCookPer100(master.cook_minutes_per_100 || 30);

                // Merge existing timings with all schools
                const existingMap = new Map<string, SchoolTiming>();
                (master.schools || []).forEach((s: SchoolTiming) => {
                    existingMap.set(s.school_id, s);
                });

                const merged = schools.map(sch => {
                    const existing = existingMap.get(sch.id);
                    return existing || {
                        school_id: sch.id,
                        school_name: sch.name,
                        default_portions: sch.default_portions,
                        target_arrival: "10:30",
                        travel_minutes: 30,
                    };
                });
                setTimings(merged);
            } else {
                // No master yet — initialize from schools
                setTimings(schools.map(s => ({
                    school_id: s.id,
                    school_name: s.name,
                    default_portions: s.default_portions,
                    target_arrival: "10:30",
                    travel_minutes: 30,
                })));
            }
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    const updateTiming = (idx: number, field: string, value: any) => {
        setTimings(prev => prev.map((t, i) => i === idx ? { ...t, [field]: value } : t));
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            await apiPost("/schedules/master", {
                prep_start_time: prepTime,
                cook_start_time: cookTime,
                cook_minutes_per_100: cookPer100,
                schools: timings.map(t => ({
                    school_id: t.school_id,
                    target_arrival: t.target_arrival,
                    travel_minutes: t.travel_minutes,
                })),
            });
            setToast("✅ Master schedule berhasil disimpan!");
            setTimeout(() => setToast(""), 3000);
        } catch (e: any) {
            setToast("❌ Gagal: " + (e?.message || "Error"));
        }
        setSaving(false);
    };

    // Compute total portions
    const totalPortions = timings.reduce((s, t) => s + (t.default_portions || 0), 0);
    const cookDuration = Math.max(30, Math.round((totalPortions / 100) * cookPer100));
    const cookEnd = (() => {
        const [h, m] = cookTime.split(":").map(Number);
        const total = h * 60 + m + cookDuration;
        return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
    })();

    if (loading) {
        return (
            <div className="p-6 flex justify-center items-center min-h-[50vh]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 max-w-3xl mx-auto space-y-6">
            {/* Toast */}
            {toast && (
                <div className="fixed top-4 right-4 z-50 bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 max-w-sm">
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-sm">{toast}</span>
                        <button onClick={() => setToast("")} className="text-gray-400 hover:text-gray-600">✕</button>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">⚙️ Setup Jadwal Master</h1>
                    <p className="text-gray-500 text-sm mt-1">Isi sekali, dipakai otomatis tiap minggu</p>
                </div>
                <Link href="/jadwal" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
                    ← Kembali
                </Link>
            </div>

            {/* ─── Section: Jadwal Dapur ──────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
                <h2 className="font-semibold text-gray-700 text-lg flex items-center gap-2">
                    🍳 Jadwal Dapur
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Jam mulai persiapan bahan</label>
                        <input type="time" value={prepTime} onChange={e => setPrepTime(e.target.value)}
                            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                    </div>
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Jam mulai masak</label>
                        <input type="time" value={cookTime} onChange={e => setCookTime(e.target.value)}
                            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                    </div>
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Estimasi masak per 100 porsi</label>
                        <div className="flex items-center gap-2">
                            <input type="number" min={5} max={120} value={cookPer100}
                                onChange={e => setCookPer100(parseInt(e.target.value) || 30)}
                                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                            <span className="text-gray-500 text-sm whitespace-nowrap">menit</span>
                        </div>
                    </div>
                </div>

                {/* Computed preview */}
                <div className="bg-blue-50 rounded-xl p-3 text-sm space-y-1">
                    <p className="text-blue-700">
                        <strong>Preview:</strong> {totalPortions.toLocaleString("id-ID")} porsi total
                        → estimasi masak <strong>{cookDuration} menit</strong>
                        → selesai masak <strong>{cookEnd}</strong>
                    </p>
                </div>
            </div>

            {/* ─── Section: Per Sekolah ───────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
                <h2 className="font-semibold text-gray-700 text-lg flex items-center gap-2">
                    🏫 Waktu Per Sekolah
                </h2>

                {timings.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-4">
                        Belum ada sekolah terdaftar. Tambahkan sekolah di halaman Settings terlebih dahulu.
                    </p>
                ) : (
                    <div className="space-y-4">
                        {timings.map((t, idx) => {
                            const depart = subtractMinutes(t.target_arrival, t.travel_minutes);
                            return (
                                <div key={t.school_id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                    <div className="flex items-center justify-between mb-3">
                                        <div>
                                            <span className="font-semibold text-gray-800">🏫 {t.school_name}</span>
                                            <span className="ml-2 text-xs text-gray-400">({t.default_portions} porsi)</span>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Target tiba di sekolah</label>
                                            <input type="time" value={t.target_arrival}
                                                onChange={e => updateTiming(idx, "target_arrival", e.target.value)}
                                                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-base font-mono focus:ring-2 focus:ring-blue-500" />
                                        </div>
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Estimasi perjalanan</label>
                                            <div className="flex items-center gap-2">
                                                <input type="number" min={5} max={180} value={t.travel_minutes}
                                                    onChange={e => updateTiming(idx, "travel_minutes", parseInt(e.target.value) || 30)}
                                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-base font-mono focus:ring-2 focus:ring-blue-500" />
                                                <span className="text-xs text-gray-400 whitespace-nowrap">mnt</span>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Jam berangkat (auto)</label>
                                            <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 text-base font-mono font-bold text-blue-700">
                                                🚗 {depart}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* ─── Save Button ────────────────────────────────────── */}
            <div className="text-center">
                <button onClick={handleSave} disabled={saving || timings.length === 0}
                    className="bg-blue-600 text-white px-8 py-3 rounded-xl font-bold text-lg hover:bg-blue-700 disabled:opacity-50 shadow-lg transition">
                    {saving ? "⏳ Menyimpan..." : "💾 Simpan Master Schedule"}
                </button>
            </div>
        </div>
    );
}
