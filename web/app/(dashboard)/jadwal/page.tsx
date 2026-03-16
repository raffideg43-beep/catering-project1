"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { PageHeader } from "@/components/layout/page-header";

type State = "empty" | "loading" | "draft" | "saving" | "saved";

interface DeliveryItem {
    school_id: string;
    school_name: string;
    portions: number;
    suggested_depart: string;
    suggested_arrive: string;
    notes: string | null;
}

interface DraftDay {
    date: string;
    day_name: string;
    is_holiday: boolean;
    holiday_name: string | null;
    deliveries: DeliveryItem[];
    total_portions: number;
    is_active?: boolean;
}

interface Draft {
    week_start: string;
    days: DraftDay[];
    ai_notes: string;
    from_ai: boolean;
}

function formatWeekLabel(weekStart: string) {
    const d = new Date(weekStart + "T00:00:00");
    const end = new Date(d);
    end.setDate(d.getDate() + 4);
    return `${d.toLocaleDateString("id-ID", { day: "numeric", month: "short" })} – ${end.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}`;
}

function getNextMonday(offset = 0) {
    const today = new Date();
    const day = today.getDay(); // 0=Sun
    const diff = day === 0 ? 1 : (8 - day); // days to next monday
    const next = new Date(today);
    next.setDate(today.getDate() + diff + (offset * 7));
    return next.toISOString().split("T")[0];
}

export default function JadwalPage() {
    const [weekOffset, setWeekOffset] = useState(0); // 0 = minggu depan, 1 = 2 minggu lagi
    const [state, setState] = useState<State>("empty");
    const [draft, setDraft] = useState<Draft | null>(null);
    const [savedWeek, setSavedWeek] = useState<Draft | null>(null);
    const [resultMsg, setResultMsg] = useState("");

    const weekStart = getNextMonday(weekOffset);

    // Check if week already has schedule
    useEffect(() => {
        apiGet(`/schedules/week?week_start=${weekStart}`).then(r => {
            const days: any[] = r?.data?.days ?? [];
            const hasSaved = days.some(d => d.deliveries && d.deliveries.length > 0);
            if (hasSaved) {
                setSavedWeek({ week_start: weekStart, days, ai_notes: "", from_ai: false });
                setState("saved");
            } else {
                setSavedWeek(null);
                setState("empty");
                setDraft(null);
            }
        }).catch(() => setState("empty"));
    }, [weekStart]);

    const generateDraft = async () => {
        setState("loading");
        try {
            const r = await apiGet(`/schedules/ai-draft?week_start=${weekStart}`);
            const d = r?.data as Draft;
            // Init is_active for all days
            d.days = d.days.map(day => ({ ...day, is_active: !day.is_holiday }));
            setDraft(d);
            setState("draft");
        } catch {
            setState("empty");
        }
    };

    const updateDelivery = (dayIdx: number, delIdx: number, field: keyof DeliveryItem, value: any) => {
        if (!draft) return;
        const newDays = draft.days.map((day, di) => {
            if (di !== dayIdx) return day;
            const newDeliveries = day.deliveries.map((del, deli) => {
                if (deli !== delIdx) return del;
                return { ...del, [field]: value };
            });
            return { ...day, deliveries: newDeliveries };
        });
        setDraft({ ...draft, days: newDays });
    };

    const toggleDay = (dayIdx: number) => {
        if (!draft) return;
        const newDays = draft.days.map((day, di) =>
            di === dayIdx ? { ...day, is_active: !day.is_active } : day
        );
        setDraft({ ...draft, days: newDays });
    };

    const approveDraft = async () => {
        if (!draft) return;
        setState("saving");
        try {
            // Only send active days
            const payload = {
                ...draft,
                days: draft.days.filter(d => d.is_active !== false),
            };
            const r = await apiPost("/schedules/approve-draft", payload);
            const count = r?.data?.saved_count ?? 0;
            setResultMsg(`✅ ${count} jadwal pengiriman tersimpan untuk minggu ${formatWeekLabel(weekStart)}!`);
            // Reload saved
            const weekResp = await apiGet(`/schedules/week?week_start=${weekStart}`);
            const days = weekResp?.data?.days ?? [];
            setSavedWeek({ week_start: weekStart, days, ai_notes: draft.ai_notes, from_ai: draft.from_ai });
            setDraft(null);
            setState("saved");
        } catch {
            setState("draft");
        }
    };

    return (
        <div className="space-y-5">
            <PageHeader
                title="📅 AI Jadwal Pengiriman"
                subtitle="Generate draft jadwal MBG mingguan dengan bantuan AI"
            />

            {/* Week selector */}
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 flex flex-wrap gap-3 items-center">
                <span className="text-sm text-gray-600 font-medium">Pilih Minggu:</span>
                <div className="flex gap-2">
                    {[0, 1, 2].map(offset => (
                        <button key={offset} onClick={() => setWeekOffset(offset)}
                            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${weekOffset === offset ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                            {offset === 0 ? "Minggu Depan" : offset === 1 ? "2 Minggu Lagi" : "3 Minggu Lagi"}
                        </button>
                    ))}
                </div>
                <span className="text-sm text-gray-500">{formatWeekLabel(weekStart)}</span>
            </div>

            {/* State: empty */}
            {state === "empty" && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-8 text-center space-y-4">
                    <p className="text-4xl">📅</p>
                    <div>
                        <p className="font-bold text-gray-900 text-lg">Belum ada jadwal untuk minggu ini</p>
                        <p className="text-sm text-gray-500 mt-1 max-w-md mx-auto">
                            AI akan membuat draft berdasarkan pola pengiriman historis, kuota porsi per sekolah, dan hari libur nasional.
                        </p>
                    </div>
                    <button onClick={generateDraft}
                        className="px-8 py-3 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg hover:shadow-xl">
                        🤖 Generate Draft Jadwal
                    </button>
                </div>
            )}

            {/* State: loading AI */}
            {state === "loading" && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-12 flex flex-col items-center gap-4">
                    <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-gray-600 font-medium">⏳ AI sedang membuat jadwal pengiriman...</p>
                </div>
            )}

            {/* State: draft */}
            {state === "draft" && draft && (
                <>
                    {draft.ai_notes && (
                        <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-700">
                            <span className="font-medium text-gray-900">💬 AI: </span>{draft.ai_notes}
                            {!draft.from_ai && <span className="ml-2 text-xs text-gray-400">(Dibuat dari data historis)</span>}
                        </div>
                    )}

                    <div className="space-y-4">
                        {draft.days.map((day, dayIdx) => {
                            const isActive = day.is_active !== false;
                            const total = day.deliveries.reduce((s, d) => s + (Number(d.portions) || 0), 0);
                            return (
                                <div key={day.date} className={`bg-white rounded-xl border shadow-sm overflow-hidden ${!isActive ? "opacity-60" : ""}`}>
                                    <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between bg-gray-50">
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-gray-900">{day.day_name}, {new Date(day.date + "T00:00:00").toLocaleDateString("id-ID", { day: "numeric", month: "long" })}</span>
                                            {day.is_holiday && (
                                                <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">🏖️ {day.holiday_name}</span>
                                            )}
                                            {!day.is_holiday && (
                                                <span className="text-xs text-gray-500">{total} porsi total</span>
                                            )}
                                        </div>
                                        {!day.is_holiday && (
                                            <button onClick={() => toggleDay(dayIdx)}
                                                className={`text-xs px-3 py-1 rounded-lg font-medium ${isActive ? "text-gray-600 hover:bg-red-50 hover:text-red-600" : "text-green-600 bg-green-50 hover:bg-green-100"}`}>
                                                {isActive ? "⏭️ Skip" : "✅ Aktifkan"}
                                            </button>
                                        )}
                                    </div>

                                    {!day.is_holiday && isActive && day.deliveries.length > 0 && (
                                        <div className="divide-y divide-gray-50">
                                            {day.deliveries.map((del, delIdx) => (
                                                <div key={del.school_id} className="p-4 grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
                                                    <div>
                                                        <p className="text-xs text-gray-500 mb-0.5">Sekolah</p>
                                                        <p className="font-medium text-sm text-gray-900">🏫 {del.school_name}</p>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-gray-500 block mb-0.5">Porsi</label>
                                                        <input type="number" min="0"
                                                            value={del.portions}
                                                            onChange={e => updateDelivery(dayIdx, delIdx, "portions", parseInt(e.target.value) || 0)}
                                                            className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm" />
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <div className="flex-1">
                                                            <label className="text-xs text-gray-500 block mb-0.5">Berangkat</label>
                                                            <input type="time"
                                                                value={del.suggested_depart || ""}
                                                                onChange={e => updateDelivery(dayIdx, delIdx, "suggested_depart", e.target.value)}
                                                                className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm" />
                                                        </div>
                                                        <div className="flex-1">
                                                            <label className="text-xs text-gray-500 block mb-0.5">Tiba</label>
                                                            <input type="time"
                                                                value={del.suggested_arrive || ""}
                                                                onChange={e => updateDelivery(dayIdx, delIdx, "suggested_arrive", e.target.value)}
                                                                className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm" />
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-gray-500 block mb-0.5">Catatan</label>
                                                        <input type="text"
                                                            value={del.notes || ""}
                                                            onChange={e => updateDelivery(dayIdx, delIdx, "notes", e.target.value)}
                                                            placeholder="opsional..."
                                                            className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm" />
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    {day.is_holiday && (
                                        <div className="p-4 text-center text-gray-400 text-sm">Tidak ada pengiriman pada hari libur</div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {/* Action buttons */}
                    <div className="flex gap-3 justify-end">
                        <button onClick={generateDraft}
                            className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200">
                            🔄 Generate Ulang
                        </button>
                        <button onClick={approveDraft}
                            className="px-6 py-2.5 bg-green-600 text-white rounded-xl text-sm font-bold hover:bg-green-700 shadow-md">
                            ✅ Approve & Simpan Jadwal
                        </button>
                    </div>
                </>
            )}

            {/* State: saving */}
            {state === "saving" && (
                <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-12 flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-gray-600 font-medium">⏳ Menyimpan jadwal...</p>
                </div>
            )}

            {/* State: saved */}
            {state === "saved" && savedWeek && (
                <div className="space-y-4">
                    {resultMsg && (
                        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800 font-medium">
                            {resultMsg}
                        </div>
                    )}

                    <div className="flex justify-end">
                        <button onClick={() => { setState("empty"); setResultMsg(""); }}
                            className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                            🔄 Buat Jadwal Baru
                        </button>
                    </div>

                    {savedWeek.days.map(day => {
                        const total = day.deliveries?.reduce((s: number, d: any) => s + (Number(d.qty) || Number(d.portions) || 0), 0) ?? 0;
                        return (
                            <div key={day.date} className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
                                <div className="px-5 py-3 border-b border-gray-100 bg-gray-50 flex items-center gap-3">
                                    <span className="font-bold text-gray-900">{day.day_name}</span>
                                    <span className="text-sm text-gray-500">{new Date(day.date + "T00:00:00").toLocaleDateString("id-ID", { day: "numeric", month: "long" })}</span>
                                    {day.is_holiday && <span className="text-xs px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded-full">🏖️ {day.holiday_name}</span>}
                                    {!day.is_holiday && <span className="text-xs text-gray-500">{total} porsi</span>}
                                </div>
                                {(day.deliveries?.length ?? 0) > 0 ? (
                                    <div className="divide-y divide-gray-50">
                                        {day.deliveries.map((del: any, i: number) => (
                                            <div key={i} className="px-5 py-3 flex flex-wrap gap-4 items-center text-sm">
                                                <span className="font-medium text-gray-800">🏫 {del.customer_name || del.school_name}</span>
                                                <span className="text-gray-500">{del.qty || del.portions} porsi</span>
                                                {del.scheduled_time && <span className="text-gray-400 text-xs">⏰ {del.scheduled_time}</span>}
                                                {del.notes && <span className="text-gray-400 text-xs">{del.notes}</span>}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-center text-gray-400 text-sm py-3">Tidak ada pengiriman</p>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
