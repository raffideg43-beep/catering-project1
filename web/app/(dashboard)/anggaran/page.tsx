"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";

/* ═══ Types ═══════════════════════════════════════════════════════════════ */

interface JuknisBreakdown {
  realisasi: string;
  target: string;
  target_pct: number;
  pct: number;
  over_budget: boolean;
}

interface KasBalance {
  id: string;
  name: string;
  type: string;
  balance: string;
}

interface Disbursement {
  id: string;
  date: string;
  amount: string;
  reference_number: string | null;
  notes: string | null;
}

interface BudgetSummary {
  year: number;
  month: number;
  pagu_amount: string;
  total_disbursed: string;
  total_spent: string;
  sisa_anggaran: string;
  pct_terpakai: number;
  total_porsi: number;
  avg_harga_porsi: string;
  kas_balances: KasBalance[];
  juknis_breakdown: {
    bahan_pangan: JuknisBreakdown;
    insentif: JuknisBreakdown;
    operasional: JuknisBreakdown;
  };
  disbursements: Disbursement[];
  fund_return: any;
}

/* ═══ Helpers ═════════════════════════════════════════════════════════════ */

const fmtRp = (v: string | number) => {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (isNaN(n)) return "Rp 0";
  return "Rp " + n.toLocaleString("id-ID", { maximumFractionDigits: 0 });
};

const MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember"];

/* ═══ Main Page ═══════════════════════════════════════════════════════════ */

export default function AnggaranPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Ledger state
  const [ledger, setLedger] = useState<any[]>([]);
  const [activeKas, setActiveKas] = useState<string | null>(null);
  const [ledgerLoading, setLedgerLoading] = useState(false);

  // Modals
  const [showPagu, setShowPagu] = useState(false);
  const [showCair, setShowCair] = useState(false);
  const [showTransfer, setShowTransfer] = useState(false);
  const [showReturn, setShowReturn] = useState(false);
  const [showKasModal, setShowKasModal] = useState(false);

  // Pagu form
  const [paguAmount, setPaguAmount] = useState("");
  const [paguNotes, setPaguNotes] = useState("");

  // Disbursement form
  const [cairDate, setCairDate] = useState(now.toISOString().split("T")[0]);
  const [cairAmount, setCairAmount] = useState("");
  const [cairRef, setCairRef] = useState("");
  const [cairNotes, setCairNotes] = useState("");

  // Transfer form
  const [tfFrom, setTfFrom] = useState("");
  const [tfTo, setTfTo] = useState("");
  const [tfAmount, setTfAmount] = useState("");
  const [tfDate, setTfDate] = useState(now.toISOString().split("T")[0]);
  const [tfNotes, setTfNotes] = useState("");

  // Return form
  const [retAmount, setRetAmount] = useState("");
  const [retDate, setRetDate] = useState(now.toISOString().split("T")[0]);
  const [retRef, setRetRef] = useState("");

  // Kas form
  const [kasName, setKasName] = useState("");
  const [kasType, setKasType] = useState("kas_kecil");
  const [kasBal, setKasBal] = useState("0");

  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiGet(`/budget/summary?year=${year}&month=${month}`);
      setData(res?.data || null);
      if (res?.data?.kas_balances?.length > 0 && !activeKas) {
        setActiveKas(res.data.kas_balances[0].id);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [year, month, activeKas]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const fetchLedger = useCallback(async () => {
    if (!activeKas) return;
    setLedgerLoading(true);
    try {
      // Get dates for selected month/year
      const startDate = new Date(year, month - 1, 1).toLocaleDateString('en-CA');
      const endDate = new Date(year, month, 0).toLocaleDateString('en-CA');
      const res = await apiGet(`/budget/ledger?kas_account_id=${activeKas}&start_date=${startDate}&end_date=${endDate}&limit=20`);
      setLedger(res?.data?.entries || []);
    } catch (e) { console.error(e); }
    setLedgerLoading(false);
  }, [year, month, activeKas]);

  useEffect(() => { fetchLedger(); }, [fetchLedger]);

  // ─── Actions ─────────────────────────────────────────────────────────

  const savePagu = async () => {
    if (!paguAmount) return;
    setSaving(true);
    try {
      await apiPost("/budget/pagu", { year, month, pagu_amount: parseFloat(paguAmount), notes: paguNotes || null });
      setShowPagu(false); fetchData();
    } catch (e: any) { alert(e?.response?.data?.detail || "Gagal"); }
    setSaving(false);
  };

  const saveCair = async () => {
    if (!cairAmount) return;
    setSaving(true);
    try {
      await apiPost("/budget/disbursement", {
        year, month, disbursement_date: cairDate,
        amount: parseFloat(cairAmount),
        reference_number: cairRef || null, notes: cairNotes || null,
      });
      setShowCair(false); setCairAmount(""); setCairRef(""); setCairNotes(""); fetchData();
    } catch (e: any) { alert(e?.response?.data?.detail || "Gagal"); }
    setSaving(false);
  };

  const saveTransfer = async () => {
    if (!tfFrom || !tfTo || !tfAmount) return;
    setSaving(true);
    try {
      await apiPost("/budget/fund-transfer", {
        from_account_id: tfFrom, to_account_id: tfTo,
        amount: parseFloat(tfAmount), transfer_date: tfDate, notes: tfNotes || null,
      });
      setShowTransfer(false); setTfAmount(""); setTfNotes(""); fetchData();
    } catch (e: any) { alert(e?.response?.data?.detail || "Gagal"); }
    setSaving(false);
  };

  const saveReturn = async () => {
    if (!retAmount) return;
    setSaving(true);
    try {
      await apiPost("/budget/fund-return", {
        year, month, amount: parseFloat(retAmount),
        return_date: retDate, reference_number: retRef || null,
      });
      setShowReturn(false); fetchData();
    } catch (e: any) { alert(e?.response?.data?.detail || "Gagal"); }
    setSaving(false);
  };

  const saveKas = async () => {
    if (!kasName) return;
    setSaving(true);
    try {
      await apiPost("/budget/kas-accounts", { name: kasName, type: kasType, initial_balance: parseFloat(kasBal) || 0 });
      setShowKasModal(false); setKasName(""); setKasBal("0"); fetchData();
    } catch (e: any) { alert(e?.response?.data?.detail || "Gagal"); }
    setSaving(false);
  };

  // ─── Computed ────────────────────────────────────────────────────────

  const sisa = data ? parseFloat(data.sisa_anggaran) : 0;
  const hasSisa = sisa > 0 && !data?.fund_return;

  /* ═══ Render ════════════════════════════════════════════════════════════ */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📊 Realisasi Anggaran</h1>
          <p className="text-sm text-gray-500 mt-1">Monitoring pagu, pencairan, dan realisasi MBG</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={month} onChange={e => setMonth(Number(e.target.value))}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            {MONTHS.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
          </select>
          <select value={year} onChange={e => setYear(Number(e.target.value))}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" /></div>
      ) : data ? (
        <>
          {/* ─── 5 Stat Cards ─── */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
            {[
              { label: "Pagu Anggaran", value: fmtRp(data.pagu_amount), icon: "🏛️", color: "blue" },
              { label: "Dana Cair", value: fmtRp(data.total_disbursed), icon: "💰", color: "green" },
              { label: "Total Terpakai", value: fmtRp(data.total_spent), icon: "💸", color: "orange" },
              { label: "Sisa Anggaran", value: fmtRp(data.sisa_anggaran), icon: sisa > 0 ? "⚠️" : "✅", color: sisa > 0 ? "red" : "gray" },
              { label: "Total Porsi", value: data.total_porsi.toLocaleString("id-ID"), icon: "🍱", color: "purple" },
            ].map(card => (
              <div key={card.label} className={`bg-white rounded-xl border shadow-sm p-4 ${
                card.color === "red" ? "border-red-200 bg-red-50" : "border-gray-100"
              }`}>
                <p className="text-xs text-gray-500 mb-1">{card.icon} {card.label}</p>
                <p className={`text-lg font-bold ${
                  card.color === "red" ? "text-red-700" : "text-gray-900"
                }`}>{card.value}</p>
              </div>
            ))}
          </div>

          {/* ─── Pagu & Pencairan ─── */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
            <div className="p-4 border-b border-gray-100 flex justify-between items-center">
              <h2 className="font-bold text-gray-900">💰 Pagu & Pencairan Dana</h2>
              <div className="flex gap-2">
                <button onClick={() => { setPaguAmount(data.pagu_amount !== "0" ? data.pagu_amount : ""); setShowPagu(true); }}
                  className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 font-medium">
                  {parseFloat(data.pagu_amount) > 0 ? "✏️ Edit Pagu" : "⚠️ Set Pagu"}
                </button>
                <button onClick={() => setShowCair(true)}
                  className="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium">
                  + Catat Pencairan
                </button>
              </div>
            </div>
            <div className="p-4">
              <div className="flex justify-between text-sm mb-3">
                <span className="text-gray-500">Pagu bulan ini:</span>
                <span className="font-bold">{fmtRp(data.pagu_amount)}</span>
              </div>
              {data.disbursements.length > 0 ? (
                <div className="space-y-2">
                  {data.disbursements.map(d => (
                    <div key={d.id} className="flex justify-between items-center bg-green-50 rounded-lg px-3 py-2 text-sm">
                      <span className="text-green-800">{d.date} {d.reference_number ? `(Ref: ${d.reference_number})` : ""}</span>
                      <span className="font-bold text-green-900">{fmtRp(d.amount)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-sm font-bold pt-2 border-t border-gray-100">
                    <span>Total Cair</span>
                    <span className="text-green-700">{fmtRp(data.total_disbursed)}</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-400 text-sm italic">Belum ada pencairan bulan ini</p>
              )}
            </div>
          </div>

          {/* ─── Saldo Kas ─── */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
            <div className="p-4 border-b border-gray-100 flex justify-between items-center">
              <h2 className="font-bold text-gray-900">🏦 Saldo Kas</h2>
              <div className="flex gap-2">
                <button onClick={() => setShowTransfer(true)}
                  className="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 font-medium">
                  ↔️ Transfer Antar Kas
                </button>
                <button onClick={() => setShowKasModal(true)}
                  className="text-xs px-3 py-1.5 bg-gray-50 text-gray-700 rounded-lg hover:bg-gray-100 font-medium">
                  + Tambah Kas
                </button>
              </div>
            </div>
            <div className="p-4">
              {data.kas_balances.length > 0 ? (
                <div className="space-y-2">
                  {data.kas_balances.map(k => (
                    <div key={k.id} className="flex justify-between items-center bg-blue-50 rounded-lg px-4 py-3">
                      <span className="text-blue-800 font-medium">{k.name}</span>
                      <span className="font-bold text-blue-900">{fmtRp(k.balance)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-sm italic">Belum ada kas. Tambahkan kas (VA Bank, Kas Kecil) untuk mulai tracking.</p>
              )}
            </div>
          </div>

          {/* ─── Buku Kas Preview ─── */}
          {data.kas_balances.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
              <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                <h2 className="font-bold text-gray-900">📒 Buku Kas</h2>
              </div>
              <div className="p-4 border-b border-gray-100 flex flex-wrap gap-2">
                {data.kas_balances.map(k => (
                  <button 
                    key={k.id} 
                    onClick={() => setActiveKas(k.id)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${activeKas === k.id ? 'bg-blue-600 outline-none text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50 border-gray-200'}`}
                  >
                    {k.type === "va_bank" ? "🏦" : "💵"} {k.name}
                  </button>
                ))}
              </div>
              <div className="p-0 overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-100/50 text-xs text-gray-500 uppercase tracking-wider">
                      <th className="p-4 font-medium">Tanggal</th>
                      <th className="p-4 font-medium">Keterangan</th>
                      <th className="p-4 font-medium text-right">Masuk</th>
                      <th className="p-4 font-medium text-right">Keluar</th>
                      <th className="p-4 font-medium text-right bg-blue-50/30">Saldo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100/50 text-sm">
                    {ledgerLoading ? (
                      <tr><td colSpan={5} className="p-8 text-center text-gray-400 italic">Memuat buku kas...</td></tr>
                    ) : ledger.length > 0 ? (
                      ledger.map((l, i) => {
                        const isDebit = l.entry_type === "debit";
                        return (
                          <tr key={l.id} className="hover:bg-gray-50/50 transition-colors">
                            <td className="p-4 text-gray-500 whitespace-nowrap">{new Date(l.entry_date).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })}</td>
                            <td className="p-4 font-medium text-gray-800">{l.description}</td>
                            <td className="p-4 text-right">
                              {isDebit && <span className="text-green-600 font-medium">+{fmtRp(l.amount)}</span>}
                            </td>
                            <td className="p-4 text-right">
                              {!isDebit && <span className="text-red-500 font-medium">-{fmtRp(l.amount)}</span>}
                            </td>
                            <td className="p-4 text-right bg-blue-50/10 font-bold text-gray-800">
                              {fmtRp(l.balance_after)}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr><td colSpan={5} className="p-8 text-center text-gray-400 italic">Belum ada transaksi di kas ini pada bulan terpilih</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ─── Realisasi 80:15:5 ─── */}
          <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
            <h2 className="font-bold text-gray-900 mb-4">📊 Realisasi Alokasi 80:15:5</h2>
            <div className="space-y-4">
              {([
                { key: "bahan_pangan" as const, label: "🥦 Bahan Pangan", pct: 80 },
                { key: "insentif" as const, label: "👷 Insentif / Upah", pct: 15 },
                { key: "operasional" as const, label: "⚙️ Operasional", pct: 5 },
              ]).map(cat => {
                const bd = data.juknis_breakdown[cat.key];
                const barPct = Math.min(bd.pct, 150);
                return (
                  <div key={cat.key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium text-gray-700">{cat.label} (Target {cat.pct}%)</span>
                      <span className={bd.over_budget ? "text-red-600 font-bold" : "text-gray-600"}>
                        {fmtRp(bd.realisasi)} / {fmtRp(bd.target)} — {bd.pct}%
                      </span>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          bd.over_budget ? "bg-red-500" : bd.pct > 90 ? "bg-yellow-400" : "bg-green-500"
                        }`}
                        style={{ width: `${Math.min(barPct, 100)}%` }}
                      />
                    </div>
                    {bd.over_budget && (
                      <p className="text-xs text-red-500 mt-1">⚠️ Melebihi target alokasi!</p>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-gray-400 mt-4">Sumber: Pengaturan tenant. Baris merah = melebihi alokasi.</p>
          </div>

          {/* ─── Pengembalian Dana ─── */}
          {hasSisa && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-5">
              <p className="text-red-800 font-bold text-lg">⚠️ Sisa Dana: {fmtRp(data.sisa_anggaran)}</p>
              <p className="text-red-600 text-sm mt-1">Wajib dikembalikan ke Kas Negara sebelum akhir periode.</p>
              <button onClick={() => { setRetAmount(data.sisa_anggaran); setShowReturn(true); }}
                className="mt-3 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium">
                📤 Catat Pengembalian
              </button>
            </div>
          )}
          {data.fund_return && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-green-800 font-bold">✅ Dana sudah dikembalikan: {fmtRp(data.fund_return.amount)}</p>
              <p className="text-green-600 text-sm">Tanggal: {data.fund_return.return_date} | Ref: {data.fund_return.reference_number || "-"}</p>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-12 text-gray-400">Tidak ada data anggaran</div>
      )}

      {/* ═══ MODALS ═══════════════════════════════════════════════════════ */}

      {/* Modal Pagu */}
      {showPagu && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowPagu(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg">🏛️ Set Pagu Anggaran</h3>
            <p className="text-sm text-gray-500">Pagu untuk {MONTHS[month]} {year}</p>
            <input type="number" value={paguAmount} onChange={e => setPaguAmount(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="Nominal pagu (Rp)" />
            <input type="text" value={paguNotes} onChange={e => setPaguNotes(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="Catatan (opsional)" />
            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowPagu(false)} className="flex-1 px-4 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50">Batal</button>
              <button onClick={savePagu} disabled={saving} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Menyimpan..." : "✅ Simpan"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Pencairan */}
      {showCair && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowCair(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg">💰 Catat Pencairan Dana</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Tanggal Cair</label>
                <input type="date" value={cairDate} onChange={e => setCairDate(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nominal</label>
                <input type="number" value={cairAmount} onChange={e => setCairAmount(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="Nominal pencairan" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">No. Referensi</label>
                <input type="text" value={cairRef} onChange={e => setCairRef(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="TRF001" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Catatan</label>
                <textarea value={cairNotes} onChange={e => setCairNotes(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" rows={2} />
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowCair(false)} className="flex-1 px-4 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50">Batal</button>
              <button onClick={saveCair} disabled={saving} className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                {saving ? "Menyimpan..." : "✅ Simpan"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Transfer Kas */}
      {showTransfer && data && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowTransfer(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg">↔️ Transfer Dana Antar Kas</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Dari Kas</label>
                <select value={tfFrom} onChange={e => setTfFrom(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm">
                  <option value="">Pilih kas asal</option>
                  {data.kas_balances.map(k => <option key={k.id} value={k.id}>{k.name} ({fmtRp(k.balance)})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ke Kas</label>
                <select value={tfTo} onChange={e => setTfTo(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm">
                  <option value="">Pilih kas tujuan</option>
                  {data.kas_balances.filter(k => k.id !== tfFrom).map(k =>
                    <option key={k.id} value={k.id}>{k.name} ({fmtRp(k.balance)})</option>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nominal</label>
                <input type="number" value={tfAmount} onChange={e => setTfAmount(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="Nominal transfer" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Tanggal</label>
                <input type="date" value={tfDate} onChange={e => setTfDate(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" />
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowTransfer(false)} className="flex-1 px-4 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50">Batal</button>
              <button onClick={saveTransfer} disabled={saving} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Memproses..." : "✅ Transfer"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Pengembalian */}
      {showReturn && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowReturn(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg">📤 Catat Pengembalian ke Kas Negara</h3>
            <p className="text-sm text-gray-500">Bulan: {MONTHS[month]} {year}</p>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nominal</label>
                <input type="number" value={retAmount} onChange={e => setRetAmount(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Tanggal Setor</label>
                <input type="date" value={retDate} onChange={e => setRetDate(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">No. Bukti</label>
                <input type="text" value={retRef} onChange={e => setRetRef(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="Nomor bukti setor" />
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowReturn(false)} className="flex-1 px-4 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50">Batal</button>
              <button onClick={saveReturn} disabled={saving} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50">
                {saving ? "Memproses..." : "✅ Catat Pengembalian"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Tambah Kas */}
      {showKasModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowKasModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 text-lg">🏦 Tambah Kas Baru</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nama Kas</label>
                <input type="text" value={kasName} onChange={e => setKasName(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" placeholder="VA BRI MBG / Kas Kecil Dapur" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Tipe</label>
                <select value={kasType} onChange={e => setKasType(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm">
                  <option value="va_bank">VA Bank</option>
                  <option value="kas_kecil">Kas Kecil</option>
                  <option value="rekening_lain">Rekening Lain</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Saldo Awal</label>
                <input type="number" value={kasBal} onChange={e => setKasBal(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-4 py-2 text-sm" />
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={() => setShowKasModal(false)} className="flex-1 px-4 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50">Batal</button>
              <button onClick={saveKas} disabled={saving} className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                {saving ? "Menyimpan..." : "✅ Simpan"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
