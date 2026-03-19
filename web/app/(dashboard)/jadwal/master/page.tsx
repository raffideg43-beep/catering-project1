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

function addMinutes(t: string, m: number): string {
    const [h, min] = t.split(":").map(Number);
    const total = h * 60 + min + m;
    return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/* ═══ Main Page ═══════════════════════════════════════════════════════════ */

export default function MasterSchedulePage() {
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState("");

    // Kitchen
    const [prepTime, setPrepTime] = useState("06:30");
    const [cookTime, setCookTime] = useState("07:00");
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

            // Extract schools from response — handle multiple possible formats
            let schools: School[] = [];
            if (Array.isArray(schoolsRes?.data)) {
                schools = schoolsRes.data;
            } else if (Array.isArray(schoolsRes)) {
                schools = schoolsRes;
            }
            console.log("[MasterSchedule] schools loaded:", schools.length, schools);
            setAllSchools(schools);

            const master = masterRes?.data;
            if (master) {
                setPrepTime(master.prep_start_time || "06:30");
                setCookTime(master.cook_start_time || "07:00");
                setCookPer100(master.cook_minutes_per_100 || 30);

                const existingMap = new Map<string, SchoolTiming>();
                (master.schools || []).forEach((s: SchoolTiming) => {
                    existingMap.set(s.school_id, s);
                });

                const merged = schools.map(sch => {
                    const existing = existingMap.get(sch.id);
                    return existing || {
                        school_id: sch.id,
                        school_name: sch.name,
                        default_portions: sch.default_portions || 0,
                        target_arrival: "10:30",
                        travel_minutes: 30,
                    };
                });
                setTimings(merged);
            } else {
                setTimings(schools.map(s => ({
                    school_id: s.id,
                    school_name: s.name,
                    default_portions: s.default_portions || 0,
                    target_arrival: "10:30",
                    travel_minutes: 30,
                })));
            }
        } catch (e) {
            console.error("[MasterSchedule] fetchData error:", e);
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

    // Computed preview
    const totalPortions = timings.reduce((s, t) => s + (t.default_portions || 0), 0);
    const cookDuration = totalPortions > 0 ? Math.max(30, Math.round((totalPortions / 100) * cookPer100)) : 0;
    const cookEnd = cookDuration > 0 ? addMinutes(cookTime, cookDuration) : "--:--";

    // Timeline preview
    const buildPreviewTimeline = () => {
        if (timings.length === 0) return [];
        const events: { time: string; icon: string; label: string }[] = [
            { time: prepTime, icon: "🥬", label: "Persiapan bahan" },
            { time: cookTime, icon: "🍳", label: `Mulai masak (${totalPortions.toLocaleString("id-ID")} porsi)` },
        ];
        if (cookDuration > 0) {
            events.push({ time: cookEnd, icon: "✅", label: `Selesai masak (~${cookDuration} menit)` });
        }
        const sorted = [...timings].sort((a, b) => {
            const da = subtractMinutes(a.target_arrival, a.travel_minutes);
            const db = subtractMinutes(b.target_arrival, b.travel_minutes);
            return da.localeCompare(db);
        });
        for (const s of sorted) {
            const depart = subtractMinutes(s.target_arrival, s.travel_minutes);
            events.push({ time: depart, icon: "🚗", label: `Berangkat → ${s.school_name}` });
            events.push({ time: s.target_arrival, icon: "📍", label: `Tiba di ${s.school_name} (${s.default_portions} porsi)` });
        }
        events.sort((a, b) => a.time.localeCompare(b.time));
        return events;
    };

    const previewTimeline = buildPreviewTimeline();

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
                        <label className="text-sm text-gray-600 font-medium block mb-1">Estimasi total waktu masak</label>
                        <div className="flex items-center gap-2">
                            <input type="number" min={5} max={120} value={cookPer100}
                                onChange={e => setCookPer100(parseInt(e.target.value) || 30)}
                                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-lg font-mono focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
                            <span className="text-gray-500 text-sm whitespace-nowrap">mnt/100 porsi</span>
                        </div>
                    </div>
                </div>

                {/* Estimasi visual */}
                {totalPortions > 0 && (
                    <div className="bg-blue-50 rounded-xl p-4 text-sm space-y-2">
                        <p className="text-blue-800 font-semibold">📊 Estimasi Waktu Masak</p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div className="bg-white rounded-lg p-2.5 text-center border border-blue-100">
                                <p className="text-xs text-gray-500">Total Porsi</p>
                                <p className="text-lg font-bold text-blue-700">{totalPortions.toLocaleString("id-ID")}</p>
                            </div>
                            <div className="bg-white rounded-lg p-2.5 text-center border border-blue-100">
                                <p className="text-xs text-gray-500">Durasi Masak</p>
                                <p className="text-lg font-bold text-orange-600">~{cookDuration} mnt</p>
                            </div>
                            <div className="bg-white rounded-lg p-2.5 text-center border border-blue-100">
                                <p className="text-xs text-gray-500">Mulai</p>
                                <p className="text-lg font-bold text-gray-700">{cookTime}</p>
                            </div>
                            <div className="bg-white rounded-lg p-2.5 text-center border border-blue-100">
                                <p className="text-xs text-gray-500">Selesai</p>
                                <p className="text-lg font-bold text-green-600">{cookEnd}</p>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* ─── Section: Per Sekolah ───────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-4">
                <h2 className="font-semibold text-gray-700 text-lg flex items-center gap-2">
                    🏫 Waktu Pengiriman Per Sekolah
                </h2>

                {timings.length === 0 ? (
                    <div className="text-center py-6">
                        <p className="text-amber-600 font-semibold mb-2">⚠️ Belum ada sekolah terdaftar</p>
                        <p className="text-gray-500 text-sm mb-3">Tambahkan sekolah di pengaturan terlebih dahulu</p>
                        <Link href="/settings" className="inline-block bg-blue-600 text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-blue-700">
                            Buka Pengaturan →
                        </Link>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {timings.map((t, idx) => {
                            const depart = subtractMinutes(t.target_arrival, t.travel_minutes);
                            return (
                                <div key={t.school_id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                    <div className="flex items-center justify-between mb-3">
                                        <div>
                                            <span className="font-semibold text-gray-800">🏫 {t.school_name}</span>
                                            <span className="ml-2 bg-blue-100 text-blue-700 text-xs font-bold px-2 py-0.5 rounded-full">
                                                {t.default_portions} porsi
                                            </span>
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

            {/* ─── Preview Timeline ───────────────────────────────── */}
            {previewTimeline.length > 0 && (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 space-y-3">
                    <h2 className="font-semibold text-gray-700 text-lg flex items-center gap-2">
                        📋 Preview Timeline Harian
                    </h2>
                    <div className="space-y-1.5">
                        {previewTimeline.map((evt, i) => (
                            <div key={i} className="flex items-center gap-3 bg-gray-50 rounded-lg px-3 py-2 border border-gray-100">
                                <span className="text-lg">{evt.icon}</span>
                                <span className="font-mono font-bold text-gray-700 w-14 text-sm">{evt.time}</span>
                                <span className="text-sm text-gray-800">{evt.label}</span>
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
