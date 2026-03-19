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
    delivery_window_minutes: number;
}

/* ═══ Helpers ══════════════════════════════════════════════════════════════ */

function subtractMinutes(t: string, m: number): string {
    const [h, min] = t.split(":").map(Number);
    let total = h * 60 + min - m;
    if (total < 0) total = 0;
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function addMinutes(t: string, m: number): string {
    const [h, min] = t.split(":").map(Number);
    const total = h * 60 + min + m;
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function diffMinutes(t1: string, t2: string): number {
    const [h1, m1] = t1.split(":").map(Number);
    const [h2, m2] = t2.split(":").map(Number);
    return (h2 * 60 + m2) - (h1 * 60 + m1);
}

function formatDuration(m: number): string {
    if (m <= 0) return "0m";
    const h = Math.floor(m / 60);
    const mins = m % 60;
    if (h === 0) return `${mins}m`;
    return mins > 0 ? `${h}j ${mins}m` : `${h}j`;
}

/* ═══ Main Page ═══════════════════════════════════════════════════════════ */

export default function MasterSchedulePage() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState("");

    // Kitchen settings
    const [prepTime, setPrepTime] = useState("06:30");
    const [cookTime, setCookTime] = useState("07:00");
    const [cookEndTime, setCookEndTime] = useState("09:30");
    const [cookPer100, setCookPer100] = useState(30);

    // Schools
    const [allSchools, setAllSchools] = useState<School[]>([]);
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
                setCookEndTime(master.cook_end_time || "09:30");
                setCookPer100(master.cook_minutes_per_100 || 30);

                const existingMap = new Map<string, any>();
                (master.schools || []).forEach((s: any) => existingMap.set(s.school_id, s));

                setTimings(schools.map(sch => {
                    const existing = existingMap.get(sch.id);
                    return existing ? {
                        school_id: existing.school_id,
                        school_name: existing.school_name,
                        default_portions: existing.default_portions,
                        target_arrival: existing.target_arrival,
                        travel_minutes: existing.travel_minutes,
                        delivery_window_minutes: existing.delivery_window_minutes ?? 15,
                    } : {
                        school_id: sch.id,
                        school_name: sch.name,
                        default_portions: sch.default_portions,
                        target_arrival: "10:30",
                        travel_minutes: 30,
                        delivery_window_minutes: 15,
                    };
                }));
            } else {
                setTimings(schools.map(s => ({
                    school_id: s.id,
                    school_name: s.name,
                    default_portions: s.default_portions,
                    target_arrival: "10:30",
                    travel_minutes: 30,
                    delivery_window_minutes: 15,
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
                cook_end_time: cookEndTime,
                cook_minutes_per_100: cookPer100,
                schools: timings.map(t => ({
                    school_id: t.school_id,
                    target_arrival: t.target_arrival,
                    travel_minutes: t.travel_minutes,
                    delivery_window_minutes: t.delivery_window_minutes,
                })),
            });
            setToast("✅ Master schedule berhasil disimpan!");
            setTimeout(() => setToast(""), 3000);
        } catch (e: any) {
            setToast("❌ Gagal: " + (e?.message || "Error"));
        }
        setSaving(false);
    };

    // Computed
    const totalPortions = timings.reduce((s, t) => s + (t.default_portions || 0), 0);
    const cookDuration = diffMinutes(cookTime, cookEndTime);
    const avgPer100 = totalPortions > 0 ? Math.round((cookDuration / totalPortions) * 100) : 0;

    // Sorted delivery order
    const deliveryOrder = [...timings]
        .map(t => ({
            ...t,
            depart: subtractMinutes(t.target_arrival, t.travel_minutes),
            doneAt: addMinutes(t.target_arrival, t.delivery_window_minutes),
        }))
        .sort((a, b) => a.depart.localeCompare(b.depart));

    if (loading) {
        return (
            <div className="p-6 flex justify-center items-center min-h-[50vh]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
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
                <Link href="/jadwal" className="text-blue-600 hover:text-blue-800 text-sm font-medium">← Kembali</Link>
            </div>

            {/* ─── Section: Jadwal Dapur ──────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
                <h2 className="font-semibold text-gray-700 text-lg">🍳 Jadwal Dapur</h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Jam mulai persiapan</label>
                        <input type="time" value={prepTime} onChange={e => setPrepTime(e.target.value)}
                            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                    </div>
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Jam mulai masak</label>
                        <input type="time" value={cookTime} onChange={e => setCookTime(e.target.value)}
                            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                    </div>
                    <div>
                        <label className="text-sm text-gray-600 font-medium block mb-1">Target selesai masak</label>
                        <input type="time" value={cookEndTime} onChange={e => setCookEndTime(e.target.value)}
                            className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                    </div>
                </div>

                {/* Auto-computed info */}
                <div className="bg-blue-50 rounded-xl p-3 text-sm space-y-1">
                    <p className="text-blue-700">
                        <strong>➜</strong> Total porsi: <strong>{totalPortions.toLocaleString("id-ID")}</strong>
                        {" | "}Estimasi masak: <strong>{formatDuration(cookDuration)}</strong>
                        {totalPortions > 0 && (
                            <> | Rata-rata per 100 porsi: <strong>{avgPer100} menit</strong></>
                        )}
                    </p>
                </div>

                {/* Optional fallback */}
                <details className="text-sm">
                    <summary className="text-gray-400 cursor-pointer hover:text-gray-600">
                        Opsional: estimasi per 100 porsi (untuk kalkulasi otomatis jika porsi berubah)
                    </summary>
                    <div className="mt-2 flex items-center gap-2 max-w-xs">
                        <input type="number" min={5} max={120} value={cookPer100}
                            onChange={e => setCookPer100(parseInt(e.target.value) || 30)}
                            className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono text-sm" />
                        <span className="text-gray-400 text-xs whitespace-nowrap">menit / 100 porsi</span>
                    </div>
                </details>
            </div>

            {/* ─── Section: Per Sekolah ───────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
                <h2 className="font-semibold text-gray-700 text-lg">🏫 Waktu Per Sekolah</h2>

                {timings.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-4">
                        Belum ada sekolah terdaftar. Tambahkan sekolah di halaman Settings.
                    </p>
                ) : (
                    <div className="space-y-4">
                        {timings.map((t, idx) => {
                            const depart = subtractMinutes(t.target_arrival, t.travel_minutes);
                            const doneAt = addMinutes(t.target_arrival, t.delivery_window_minutes);
                            return (
                                <div key={t.school_id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                    <div className="flex items-center justify-between mb-3">
                                        <span className="font-semibold text-gray-800">🏫 {t.school_name}
                                            <span className="ml-2 text-xs text-gray-400 font-normal">({t.default_portions} porsi)</span>
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Target tiba di sekolah</label>
                                            <input type="time" value={t.target_arrival}
                                                onChange={e => updateTiming(idx, "target_arrival", e.target.value)}
                                                className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono focus:ring-2 focus:ring-blue-500" />
                                        </div>
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Estimasi perjalanan</label>
                                            <div className="flex items-center gap-1">
                                                <input type="number" min={5} max={180} value={t.travel_minutes}
                                                    onChange={e => updateTiming(idx, "travel_minutes", parseInt(e.target.value) || 30)}
                                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono focus:ring-2 focus:ring-blue-500" />
                                                <span className="text-xs text-gray-400">mnt</span>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="text-xs text-gray-500 block mb-1">Estimasi serah terima</label>
                                            <div className="flex items-center gap-1">
                                                <input type="number" min={5} max={60} value={t.delivery_window_minutes}
                                                    onChange={e => updateTiming(idx, "delivery_window_minutes", parseInt(e.target.value) || 15)}
                                                    className="w-full border border-gray-200 rounded-lg px-3 py-2 font-mono focus:ring-2 focus:ring-blue-500" />
                                                <span className="text-xs text-gray-400">mnt</span>
                                            </div>
                                        </div>
                                    </div>
                                    {/* Auto-computed */}
                                    <div className="mt-3 flex gap-4 text-sm">
                                        <div className="bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5 font-mono">
                                            🚗 Berangkat: <strong>{depart}</strong>
                                        </div>
                                        <div className="bg-green-50 border border-green-100 rounded-lg px-3 py-1.5 font-mono">
                                            ✅ Selesai di sekolah: <strong>{doneAt}</strong>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* ─── Section: Urutan Pengiriman ─────────────────────── */}
            {deliveryOrder.length > 0 && (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                    <h2 className="font-semibold text-gray-700 text-lg mb-3">🚗 Urutan Pengiriman</h2>
                    <div className="space-y-2">
                        {deliveryOrder.map((s, idx) => (
                            <div key={s.school_id} className="flex items-center gap-3 bg-blue-50/50 rounded-lg px-4 py-2 border border-blue-100/50">
                                <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">{idx + 1}</span>
                                <span className="font-mono font-bold text-blue-700 w-14 text-sm">{s.depart}</span>
                                <span className="text-gray-400">→</span>
                                <span className="font-medium text-gray-800 flex-1">{s.school_name}</span>
                                <span className="text-xs text-gray-500">
                                    tiba {s.target_arrival} · selesai {s.doneAt}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

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
