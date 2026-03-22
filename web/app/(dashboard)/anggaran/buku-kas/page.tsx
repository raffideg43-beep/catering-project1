"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";

type KasAccount = { id: string; name: string; current_balance: number };
type LedgerEntry = {
  id: string;
  entry_date: string;
  description: string;
  entry_type: "debit" | "credit";
  amount: number;
  balance_after: number;
  reference_type: string;
};

const fmtRp = (v: number) => "Rp " + Math.round(v).toLocaleString("id-ID");

export default function BukuKasPage() {
  const [loading, setLoading] = useState(true);
  const [kasAccounts, setKasAccounts] = useState<KasAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
  const [startDate, setStartDate] = useState(firstDay);
  const [endDate, setEndDate] = useState(today.toISOString().split('T')[0]);
  
  const [entries, setEntries] = useState<LedgerEntry[]>([]);

  // Init fetch kas options
  useEffect(() => {
    apiGet("/budget/kas-accounts").then(res => {
      if (res?.data) {
        setKasAccounts(res.data);
        if (res.data.length > 0 && !accountId) {
          setAccountId(res.data[0].id);
        } else {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    }).catch(e => {
        console.error(e);
        setLoading(false);
    });
  }, []);

  const fetchLedger = useCallback(async () => {
    if (!accountId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await apiGet(`/budget/ledger?kas_account_id=${accountId}&start_date=${startDate}&end_date=${endDate}&limit=500`);
      setEntries(res?.data?.entries || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [accountId, startDate, endDate]);

  useEffect(() => {
    if (accountId) fetchLedger();
  }, [fetchLedger]);

  const getBadge = (refType: string) => {
    switch (refType) {
      case "disbursement": return <span className="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full font-medium">🟡 Pencairan</span>;
      case "transfer": return <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full font-medium">🔵 Transfer</span>;
      case "expense": return <span className="bg-red-100 text-red-800 text-xs px-2 py-1 rounded-full font-medium">🔴 Pengeluaran</span>;
      case "payroll": return <span className="bg-purple-100 text-purple-800 text-xs px-2 py-1 rounded-full font-medium">🟣 Gaji</span>;
      case "return_to_gov": return <span className="bg-gray-200 text-gray-800 text-xs px-2 py-1 rounded-full font-medium">⚫ Kembali Negara</span>;
      case "income": return <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full font-medium">🟢 Pemasukan</span>;
      default: return <span className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full font-medium">{refType}</span>;
    }
  };

  const exportCSV = () => {
    const headers = ["Tanggal", "Keterangan", "Jenis", "Masuk", "Keluar", "Saldo"];
    const rows = entries.map(e => [
      e.entry_date,
      `"${e.description.replace(/"/g, '""')}"`, // escape quotes
      e.reference_type,
      e.entry_type === "debit" ? e.amount : "",
      e.entry_type === "credit" ? e.amount : "",
      e.balance_after
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.href = encodedUri;
    link.download = `buku_kas_${accountId}_${startDate}_${endDate}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <a href="/dashboard/anggaran" className="text-blue-600 text-sm hover:underline mb-1 inline-block">← Kembali ke Anggaran</a>
          <h1 className="text-2xl font-bold text-gray-900">📒 Buku Kas Lengkap</h1>
          <p className="text-sm text-gray-500 mt-1">Riwayat transaksi masuk keluarnya dana secara rinci</p>
        </div>
        <div className="flex gap-2">
          <button onClick={exportCSV} className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 flex items-center gap-2">
            📥 Export CSV
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Pilih Akun Kas</label>
            <select value={accountId} onChange={e => setAccountId(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
              <optgroup label="Tersedia">
                {kasAccounts.map(k => <option key={k.id} value={k.id}>{k.name}</option>)}
              </optgroup>
            </select>
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Dari Tanggal</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-500 mb-1">Sampai Tanggal</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div>
            <button onClick={fetchLedger} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2">
              🔍 Cari
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-0 overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100/50 text-xs text-gray-500 uppercase tracking-wider">
                <th className="p-4 font-medium">Tanggal</th>
                <th className="p-4 font-medium">Keterangan</th>
                <th className="p-4 font-medium min-w-[130px]">Jenis</th>
                <th className="p-4 font-medium text-right">Masuk</th>
                <th className="p-4 font-medium text-right">Keluar</th>
                <th className="p-4 font-medium text-right bg-blue-50/30">Saldo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100/50 text-sm">
              {loading ? (
                <tr><td colSpan={6} className="p-8 text-center text-gray-400 italic">Memuat data...</td></tr>
              ) : entries.length > 0 ? (
                entries.map(l => {
                  const isDebit = l.entry_type === "debit";
                  return (
                    <tr key={l.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="p-4 text-gray-500 whitespace-nowrap">{new Date(l.entry_date).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric'})}</td>
                      <td className="p-4 font-medium text-gray-800">{l.description}</td>
                      <td className="p-4">{getBadge(l.reference_type)}</td>
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
                <tr><td colSpan={6} className="p-8 text-center text-gray-400 italic">Tidak ada transaksi ditemukan pada filter tersebut.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
