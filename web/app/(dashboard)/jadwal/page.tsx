"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";
import Link from "next/link";

/* ═══ Types ════════════════════════════════════════════════════════════════ */

interface TimelineEvent {
    time: string;
    activity: string;
    school_id: string | null;
    school_name: string | null;
    type: "prep" | "cook" | "cook_done" | "depart" | "arrive" | string;
}

interface DaySchedule {
    date: string;
    day_name: string;
    is_holiday: boolean;
    holiday_name: string | null;
    menu_name?: string | null;
    menu_id?: string | null;
    has_menu?: boolean;
    timeline: TimelineEvent[];
    total_portions: number;
    cook_duration_minutes?: number;
    ai_notes?: string | null;
}

interface MasterSchool {
    school_id: string;
    school_name: string;
    default_portions: number;
    target_arrival: string;
    travel_minutes: number;
    delivery_window_minutes: number;
    depart_time: string;
    done_at_school: string;
}

interface MasterData {
    id: string;
    name: string;
    prep_start_time: string;
    cook_start_time: string;
    cook_end_time: string;
    cook_minutes_per_100: number;
    cook_duration_minutes: number;
    total_portions: number;
    schools: MasterSchool[];
}

interface WeekData {
    week_start: string;
    days: DaySchedule[];
    has_schedule?: boolean;
    source?: string;
    from_ai?: boolean;
    ai_notes?: string;
}

/* ═══ Helpers ══════════════════════════════════════════════════════════════ */

const eventIcon = (type: string) => {
    switch (type) {
        case "prep": return "🥬";
        case "cook": return "🍳";
        case "cook_done": return "✅";
        case "depart": return "🚗";
        case "arrive": return "📍";
        default: return "📋";
    }
};

const eventColor = (type: string) => {
    switch (type) {
        case "prep": return "border-l-4 border-l-green-400 bg-green-50/60";
        case "cook": return "border-l-4 border-l-orange-400 bg-orange-50/60";
        case "cook_done": return "border-l-4 border-l-emerald-400 bg-emerald-50/60";
        case "depart": return "border-l-4 border-l-blue-400 bg-blue-50/60";
        case "arrive": return "border-l-4 border-l-purple-400 bg-purple-50/60";
        default: return "border-l-4 border-l-gray-300 bg-gray-50/60";
    }
};

function formatDuration(m: number): string {
    if (!m || m <= 0) return "-";
    const h = Math.floor(m / 60);
    const mins = m % 60;
    if (h === 0) return `${mins}m`;
    return mins > 0 ? `${h}j ${mins}m` : `${h}j`;
}

/* ═══ Main Page ═══════════════════════════════════════════════════════════ */

export default function JadwalPage() {
    const [master, setMaster] = useState<MasterData | null>(null);
    const [weekData, setWeekData] = useState<WeekData | null>(null);
    const [draftData, setDraftData] = useState<WeekData | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [approving, setApproving] = useState(false);
    const [weekOffset, setWeekOffset] = useState(0);
    const [toast, setToast] = useState("");

    const getMonday = (offset: number) => {
        const d = new Date();
        d.setDate(d.getDate() - d.getDay() + 1 + offset * 7);
        return d.toISOString().split("T")[0];
    };

    const fetchMaster = useCallback(async () => {
        try {
            const res = await apiGet("/schedules/master");
            setMaster(res?.data || null);
        } catch { setMaster(null); }
    }, []);

    const fetchWeek = useCallback(async (ws: string) => {
        try {
            const res = await apiGet(`/schedules/week?week_start=${ws}`);
            setWeekData(res?.data || null);
        } catch { setWeekData(null); }
    }, []);

    useEffect(() => {
        setLoading(true);
        const ws = getMonday(weekOffset);
        Promise.all([fetchMaster(), fetchWeek(ws)]).finally(() => setLoading(false));
    }, [weekOffset, fetchMaster, fetchWeek]);

    const handleLoadMaster = async () => {
        setGenerating(true);
        try {
            const ws = getMonday(weekOffset);
            const res = await apiPost("/schedules/load-master", { week_start: ws });
            setDraftData(res?.data || null);
            setToast("✅ Timeline dari master berhasil dimuat");
        } catch (e: any) {
            setToast("❌ " + (e?.message || "Gagal load master"));
        }
        setGenerating(false);
    };

    const handleAiDraft = async () => {
        setGenerating(true);
        try {
            const ws = getMonday(weekOffset);
            const res = await apiGet(`/schedules/ai-draft?week_start=${ws}`);
            setDraftData(res?.data || null);
            setToast(res?.data?.from_ai ? "🤖 AI draft berhasil!" : "📋 Menggunakan master (AI tidak tersedia)");
        } catch (e: any) {
            setToast("❌ " + (e?.message || "Gagal generate"));
        }
        setGenerating(false);
    };

    const handleApprove = async () => {
        if (!draftData) return;
        setApproving(true);
        try {
            await apiPost("/schedules/approve-draft", {
                week_start: draftData.week_start,
                days: draftData.days,
            });
            setToast("✅ Jadwal berhasil di-approve!");
            setDraftData(null);
            fetchWeek(getMonday(weekOffset));
        } catch (e: any) {
            setToast("❌ " + (e?.message || "Gagal approve"));
        }
        setApproving(false);
    };

    const displayData = draftData || weekData;
    const isDraft = !!draftData;
    const hasSchedule = weekData?.has_schedule;

    if (loading) {
        return (
            <div className="p-6 flex justify-center items-center min-h-[50vh]">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
            </div>
        );
    }

    return (
        <div className="p-4 md:p-6 max-w-4xl mx-auto space-y-6">
            {/* Toast */}
            {toast && (
                <div className="fixed top-4 right-4 z-50 bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 max-w-sm animate-[fadeIn_0.3s]">
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-sm">{toast}</span>
                        <button onClick={() => setToast("")} className="text-gray-400 hover:text-gray-600">✕</button>
                    </div>
                </div>
            )}

            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-gray-800">📅 AI Jadwal Operasional</h1>
                <p className="text-gray-500 text-sm mt-1">Timeline harian: persiapan → masak → pengiriman</p>
            </div>

            {/* ─── Section 1: Master Schedule Status ─────────────── */}
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
                {!master ? (
                    <div className="text-center py-4">
                        <p className="text-amber-600 font-semibold text-lg mb-2">⚠️ Master Schedule Belum Di-setup</p>
                        <p className="text-gray-500 text-sm mb-4">Setup jadwal waktu operasional sekali, dipakai otomatis tiap minggu</p>
                        <Link href="/jadwal/master"
                            className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition">
                            ⚙️ Setup Master Schedule
                        </Link>
                    </div>
                ) : (
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="font-semibold text-gray-700 flex items-center gap-2">
                                ✅ Jadwal Master Aktif
                            </h2>
                            <Link href="/jadwal/master"
                                className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                                ✏️ Edit Master
                            </Link>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                            <div className="bg-green-50 rounded-xl p-3">
                                <span className="text-gray-500 text-xs">🥬 Persiapan</span>
                                <p className="font-bold text-lg">{master.prep_start_time}</p>
                            </div>
                            <div className="bg-orange-50 rounded-xl p-3">
                                <span className="text-gray-500 text-xs">🍳 Mulai Masak</span>
                                <p className="font-bold text-lg">{master.cook_start_time}</p>
                            </div>
                            <div className="bg-emerald-50 rounded-xl p-3">
                                <span className="text-gray-500 text-xs">✅ Selesai Masak</span>
                                <p className="font-bold text-lg">{master.cook_end_time}</p>
                            </div>
                            <div className="bg-blue-50 rounded-xl p-3">
                                <span className="text-gray-500 text-xs">📊 Total</span>
                                <p className="font-bold text-lg">{master.total_portions?.toLocaleString("id-ID")} porsi</p>
                            </div>
                        </div>
                        {master.schools.length > 0 && (
                            <div className="mt-3 space-y-1.5">
                                {master.schools.map(s => (
                                    <div key={s.school_id} className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg px-3 py-2">
                                        <span>🚗</span>
                                        <span className="font-medium flex-shrink-0">{s.school_name}</span>
                                        <span className="text-gray-400">|</span>
                                        <span className="text-gray-600 text-xs">
                                            berangkat {s.depart_time} → tiba {s.target_arrival} → selesai {s.done_at_school}
                                        </span>
                                        <span className="text-xs text-gray-400 ml-auto">({s.default_portions} porsi)</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* ─── Section 2: Week Picker ─────────────────────────── */}
            <div className="flex items-center gap-3">
                {[0, 1].map(offset => (
                    <button key={offset}
                        onClick={() => { setWeekOffset(offset); setDraftData(null); }}
                        className={`px-4 py-2 rounded-xl font-medium text-sm transition ${weekOffset === offset ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                    >
                        {offset === 0 ? "Minggu Ini" : "Minggu Depan"}
                    </button>
                ))}
                <span className="text-sm text-gray-400 ml-auto">
                    {getMonday(weekOffset)} — {(() => {
                        const d = new Date(getMonday(weekOffset));
                        d.setDate(d.getDate() + 4);
                        return d.toISOString().split("T")[0];
                    })()}
                </span>
            </div>

            {/* ─── Draft banner ────────────────────────────────────── */}
            {isDraft && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center justify-between">
                    <span className="text-amber-800 text-sm font-medium">
                        📝 Draft belum disimpan — {draftData?.source === "ai" ? "dari AI" : "dari Master"}
                    </span>
                    <button onClick={handleApprove} disabled={approving}
                        className="bg-green-600 text-white px-4 py-1.5 rounded-lg text-sm font-semibold hover:bg-green-700 disabled:opacity-50">
                        {approving ? "Menyimpan..." : "✅ Approve"}
                    </button>
                </div>
            )}

            {/* ─── No schedule: action buttons ────────────────────── */}
            {!hasSchedule && !isDraft && (
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 text-center">
                    <p className="text-gray-500 mb-4">Belum ada jadwal untuk {weekOffset === 0 ? "minggu ini" : "minggu depan"}</p>
                    <div className="flex justify-center gap-3 flex-wrap">
                        <button onClick={handleLoadMaster} disabled={generating || !master}
                            className="bg-blue-600 text-white px-5 py-2.5 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition">
                            {generating ? "⏳..." : "📋 Load dari Master"}
                        </button>
                        <button onClick={handleAiDraft} disabled={generating}
                            className="bg-purple-600 text-white px-5 py-2.5 rounded-xl font-semibold hover:bg-purple-700 disabled:opacity-50 transition">
                            {generating ? "⏳..." : "🤖 Generate AI Draft"}
                        </button>
                    </div>
                </div>
            )}

            {/* ─── Section 3: Timeline ────────────────────────────── */}
            {displayData && displayData.days && displayData.days.length > 0 && (
                <div className="space-y-4">
                    {displayData.days.map(day => (
                        <div key={day.date} className={`bg-white rounded-2xl border shadow-sm overflow-hidden ${day.is_holiday ? "border-red-200" : "border-gray-100"}`}>
                            {/* Day header */}
                            <div className={`px-5 py-3 ${day.is_holiday ? "bg-red-50" : "bg-gradient-to-r from-blue-50 to-indigo-50/30"}`}>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <span className="font-bold text-gray-800">{day.day_name}</span>
                                        <span className="text-gray-500 text-sm ml-2">{day.date}</span>
                                        {day.is_holiday && <span className="ml-2 text-red-600 text-sm font-medium">🎌 {day.holiday_name}</span>}
                                    </div>
                                    {!day.is_holiday && day.total_portions > 0 && (
                                        <span className="bg-blue-100 text-blue-800 font-bold px-3 py-1 rounded-full text-sm">
                                            {day.total_portions.toLocaleString("id-ID")} porsi
                                        </span>
                                    )}
                                </div>
                                {/* Menu info */}
                                {!day.is_holiday && (
                                    <div className="mt-1">
                                        {day.has_menu && day.menu_name ? (
                                            <span className="text-sm text-indigo-700 font-medium">🍽️ Menu: {day.menu_name}</span>
                                        ) : (
                                            <span className="text-sm text-amber-600">⚠️ Menu belum diatur — set via Telegram /menu</span>
                                        )}
                                        {day.cook_duration_minutes && day.cook_duration_minutes > 0 && (
                                            <span className="text-xs text-gray-400 ml-3">⏱️ Estimasi masak: {formatDuration(day.cook_duration_minutes)}</span>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Timeline events */}
                            {day.is_holiday ? (
                                <div className="px-5 py-4 text-center text-gray-400 text-sm">Libur — tidak ada jadwal</div>
                            ) : day.timeline.length === 0 ? (
                                <div className="px-5 py-4 text-center text-gray-400 text-sm">Tidak ada kegiatan</div>
                            ) : (
                                <div className="px-4 py-3 space-y-1.5">
                                    {day.timeline.map((evt, idx) => (
                                        <div key={idx} className={`flex items-center gap-3 rounded-lg px-3 py-2 ${eventColor(evt.type)}`}>
                                            <span className="text-lg">{eventIcon(evt.type)}</span>
                                            <span className="font-mono font-bold text-gray-700 w-14 text-sm">{evt.time}</span>
                                            <span className="text-sm text-gray-800 flex-1">{evt.activity}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* AI notes */}
                            {day.ai_notes && (
                                <div className="px-5 py-2 bg-yellow-50 border-t border-yellow-100 text-xs text-yellow-700">
                                    🤖 {day.ai_notes}
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Bottom buttons */}
                    {isDraft && (
                        <div className="text-center pt-2">
                            <button onClick={handleApprove} disabled={approving}
                                className="bg-green-600 text-white px-8 py-3 rounded-xl font-bold text-lg hover:bg-green-700 disabled:opacity-50 shadow-lg transition">
                                {approving ? "⏳ Menyimpan..." : "✅ Approve Jadwal Minggu Ini"}
                            </button>
                        </div>
                    )}

                    {hasSchedule && !isDraft && (
                        <div className="flex justify-center gap-3 pt-2">
                            <button onClick={handleLoadMaster} disabled={generating || !master}
                                className="text-blue-600 border border-blue-200 px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-50 disabled:opacity-50">
                                🔄 Regenerate dari Master
                            </button>
                            <button onClick={handleAiDraft} disabled={generating}
                                className="text-purple-600 border border-purple-200 px-4 py-2 rounded-xl text-sm font-medium hover:bg-purple-50 disabled:opacity-50">
                                🤖 Regenerate AI Draft
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* AI notes banner */}
            {displayData?.ai_notes && (
                <div className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-3 text-sm text-purple-800">
                    🤖 <strong>Catatan AI:</strong> {displayData.ai_notes}
                </div>
            )}
        </div>
    );
}
