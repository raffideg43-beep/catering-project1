"use client";

import { useState } from "react";

type Section = "overview" | "akuntan" | "bahan" | "bom" | "penyerahan" | "telegram" | "stok" | "anggaran";

const sections: { id: Section; icon: string; title: string }[] = [
  { id: "overview", icon: "🏠", title: "Ikhtisar Sistem" },
  { id: "telegram", icon: "🤖", title: "Telegram Bot" },
  { id: "bahan", icon: "📦", title: "Input Bahan & Belanja" },
  { id: "bom", icon: "🍽️", title: "Menu BOM & Nutrisi" },
  { id: "penyerahan", icon: "🍱", title: "Penyerahan MBG" },
  { id: "stok", icon: "🏪", title: "Manajemen Stok" },
  { id: "anggaran", icon: "💰", title: "Keuangan & Anggaran" },
  { id: "akuntan", icon: "📊", title: "Peran Akuntan" },
];

function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 items-start bg-blue-50 border border-blue-100 rounded-xl p-4 my-3">
      <span className="text-blue-500 text-lg shrink-0 mt-0.5">💡</span>
      <div className="text-sm text-blue-900 leading-relaxed">{children}</div>
    </div>
  );
}

function Warning({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 items-start bg-amber-50 border border-amber-200 rounded-xl p-4 my-3">
      <span className="text-amber-500 text-lg shrink-0 mt-0.5">⚠️</span>
      <div className="text-sm text-amber-900 leading-relaxed">{children}</div>
    </div>
  );
}

function Step({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 items-start mb-5">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center text-sm font-black shrink-0 shadow-md">{num}</div>
      <div className="flex-1">
        <h4 className="font-bold text-gray-900 text-sm mb-1">{title}</h4>
        <div className="text-sm text-gray-600 leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

function SectionOverview() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Sistem MBG Catering adalah platform terintegrasi untuk mengelola operasional Makan Bergizi Gratis. Berikut alur kerja utama:</p>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
      {[
        { icon: "📦", title: "Master Bahan", desc: "Daftarkan semua bahan baku di menu Dapur → Tab Komponen" },
        { icon: "🍽️", title: "Resep / BOM", desc: "Susun komposisi per porsi di Dapur → Tab Master Menu BOM" },
        { icon: "📅", title: "Jadwal Menu", desc: "Atur menu mingguan di halaman MBG → Jadwal" },
        { icon: "🛒", title: "Belanja Harian", desc: "Catat nota belanja via Telegram /belanja atau Web → Pembukuan" },
        { icon: "🍱", title: "Penyerahan", desc: "Serahkan makanan ke sekolah via Telegram /serah" },
        { icon: "📊", title: "Laporan", desc: "Download Excel/PDF di Pembukuan → Kumpulan Dokumen" },
      ].map((item, i) => (
        <div key={i} className="flex gap-3 bg-white border border-gray-100 rounded-2xl p-4 shadow-sm hover:shadow-md transition-shadow">
          <span className="text-2xl">{item.icon}</span>
          <div>
            <h4 className="font-bold text-gray-900 text-sm">{item.title}</h4>
            <p className="text-xs text-gray-500 mt-0.5">{item.desc}</p>
          </div>
        </div>
      ))}
    </div>
    <Tip>Semua data saling terhubung. Saat Anda melakukan Penyerahan MBG, stok otomatis dipotong berdasarkan BOM, piutang otomatis tercatat, dan anggaran otomatis terupdate.</Tip>
  </div>);
}

function SectionTelegram() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Bot Telegram adalah jalur utama operasional harian. Pastikan bot sudah terhubung di <b>Pengaturan → Telegram</b>.</p>
    <div className="bg-slate-900 text-green-400 rounded-2xl p-5 font-mono text-sm space-y-3 shadow-inner">
      <p className="text-gray-400">── Perintah Utama ──</p>
      <p><span className="text-cyan-400">/start</span> — Memulai bot dan melihat menu utama</p>
      <p><span className="text-cyan-400">/belanja</span> — Catat belanja harian (OCR foto nota / manual)</p>
      <p><span className="text-cyan-400">/serah</span> — Laporkan penyerahan MBG ke sekolah</p>
      <p><span className="text-cyan-400">/stok</span> — Cek stok bahan di gudang</p>
      <p><span className="text-cyan-400">/menu</span> — Lihat jadwal menu minggu ini</p>
      <p><span className="text-cyan-400">/laporan</span> — Generate & download laporan bulanan</p>
      <p><span className="text-cyan-400">/help</span> — Panduan lengkap semua perintah</p>
    </div>
    <h3 className="font-bold text-gray-900 mt-6 mb-2">📸 Cara Belanja via Foto Nota (OCR)</h3>
    <Step num={1} title="Ketik /belanja di chat bot">Bot akan bertanya apakah ingin input manual atau foto nota.</Step>
    <Step num={2} title="Pilih 'Foto Nota' lalu kirim gambar struk">Bot akan membaca teks di nota secara otomatis menggunakan AI (OCR).</Step>
    <Step num={3} title="Konfirmasi hasil pembacaan">Bot menampilkan daftar item yang terbaca. Periksa nama bahan, jumlah, dan harga. Koreksi jika ada kesalahan.</Step>
    <Step num={4} title="Simpan">Data masuk ke sistem pembukuan dan stok otomatis bertambah.</Step>
    <Tip>Pastikan foto nota tidak buram dan pencahayaan cukup. Letakkan nota di permukaan rata untuk hasil OCR terbaik.</Tip>
    <Warning>Jika OCR salah membaca, Anda bisa mengedit secara manual di Web → Pembukuan setelah data tersimpan.</Warning>
  </div>);
}

function SectionBahan() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Bahan baku harus terdaftar di sistem agar bisa digunakan di BOM, stok, dan belanja.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Cara Input Bahan Baru (Web)</h3>
    <Step num={1} title="Buka menu Dapur → Tab Komponen">Di sini terdapat daftar semua bahan baku yang terdaftar di sistem.</Step>
    <Step num={2} title="Klik '+ Tambah Bahan Baku'">Isi nama bahan, satuan (kg/liter/pcs), dan harga terakhir.</Step>
    <Step num={3} title="Perhatikan Satuan!">
      <div className="mt-1">
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs border-collapse">
            <thead><tr className="bg-gray-100"><th className="px-3 py-2 text-left border-b">Bahan</th><th className="px-3 py-2 text-left border-b">Satuan Benar</th><th className="px-3 py-2 text-left border-b">Contoh Qty/Porsi</th></tr></thead>
            <tbody>
              <tr><td className="px-3 py-1.5 border-b">Beras</td><td className="px-3 py-1.5 border-b font-mono">kg</td><td className="px-3 py-1.5 border-b">0.1 kg (100g)</td></tr>
              <tr><td className="px-3 py-1.5 border-b">Minyak Goreng</td><td className="px-3 py-1.5 border-b font-mono">liter</td><td className="px-3 py-1.5 border-b">0.01 liter (10ml)</td></tr>
              <tr><td className="px-3 py-1.5 border-b">Telur</td><td className="px-3 py-1.5 border-b font-mono">pcs</td><td className="px-3 py-1.5 border-b">1 pcs</td></tr>
              <tr><td className="px-3 py-1.5 border-b">Daging Ayam</td><td className="px-3 py-1.5 border-b font-mono">kg</td><td className="px-3 py-1.5 border-b">0.1 kg (100g)</td></tr>
              <tr><td className="px-3 py-1.5">Susu Kotak</td><td className="px-3 py-1.5 font-mono">pcs</td><td className="px-3 py-1.5">1 pcs</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </Step>
    <h3 className="font-bold text-gray-900 mt-6 mb-2">Cara Belanja via Web</h3>
    <Step num={1} title="Buka Pembukuan → Belanja">Klik tombol '+ Catat Belanja Baru'.</Step>
    <Step num={2} title="Isi form belanja">Pilih supplier, masukkan item belanja (bahan, qty, harga), dan upload foto nota jika ada.</Step>
    <Step num={3} title="Simpan">Data transaksi tersimpan dan stok bahan otomatis bertambah.</Step>
    <Warning>Bahan yang dibeli via Telegram (/belanja) juga otomatis menambah stok. Jangan input ulang di Web supaya tidak double.</Warning>
  </div>);
}

function SectionBOM() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">BOM (Bill of Materials) menentukan berapa banyak bahan yang dibutuhkan untuk membuat 1 porsi makanan. Ini penting untuk kalkulasi stok, nutrisi, dan biaya.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Membuat Menu BOM Baru</h3>
    <Step num={1} title="Buka Dapur → Tab Master Menu BOM">Klik '+ Ciptakan Menu Baru'.</Step>
    <Step num={2} title="Isi nama menu dan satuan output">Contoh: "Nasi Ayam Balado", satuan "porsi".</Step>
    <Step num={3} title="Tambahkan bahan-bahan">Ketik nama bahan (sistem akan auto-suggest dari master bahan). Isi jumlah qty dan satuan.</Step>
    <Step num={4} title="⚠️ Perhatikan 'Limitasi Konteks'!">
      <div className="mt-2 space-y-2">
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <span className="font-bold text-green-800 text-xs">🟢 Per Porsi (Default)</span>
          <p className="text-xs text-green-700 mt-1">Qty akan <b>dikali jumlah porsi</b>. Contoh: Beras 0.1 kg/porsi × 2000 porsi = 200 kg.</p>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
          <span className="font-bold text-orange-800 text-xs">🟠 Per Hari (Fixed)</span>
          <p className="text-xs text-orange-700 mt-1">Qty tetap <b>TIDAK dikali porsi</b>. Untuk bahan yang pemakaiannya fixed per hari. Contoh: Minyak goreng 5 liter/hari (untuk keseluruhan produksi, bukan per porsi).</p>
        </div>
      </div>
    </Step>
    <Warning>
      <b>Kesalahan Paling Umum:</b> Memasukkan Minyak Goreng "5 liter" dengan mode "Per Porsi". Akibatnya: 5 liter × 2000 porsi = 10.000 liter minyak! Kalori meledak jadi 23 juta kkal. Gunakan mode <b>"Per Hari (Fixed)"</b> untuk bahan seperti minyak goreng, gas, dll.
    </Warning>
    <h3 className="font-bold text-gray-900 mt-6 mb-2">Tabel Nutrisi</h3>
    <p className="text-sm text-gray-600">Setelah BOM disimpan, sistem otomatis menghitung nutrisi per porsi berdasarkan database nutrisi. Jika ada bahan yang belum memiliki data nutrisi (label <span className="px-1 py-0.5 bg-amber-200 text-amber-800 rounded text-[10px] font-bold">NO DATA</span>), klik tombol 🤖 untuk auto-link AI atau ✏️ untuk input manual.</p>
    <Tip>Target nutrisi MBG: min 400 kkal, protein 15g, sayur ≥30% berat total. Pantau indikator sayur di kartu nutrisi.</Tip>
  </div>);
}

function SectionPenyerahan() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Penyerahan MBG dicatat saat makanan dikirim ke sekolah. Ini memicu pemotongan stok otomatis dan pencatatan piutang ke pemerintah.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Alur Penyerahan via Telegram</h3>
    <Step num={1} title="Ketik /serah di bot Telegram">Bot menampilkan daftar sekolah terdaftar.</Step>
    <Step num={2} title="Pilih sekolah tujuan">Bisa pilih satu atau beberapa sekolah sekaligus.</Step>
    <Step num={3} title="Masukkan jumlah porsi per sekolah">Bot akan meminta jumlah porsi untuk masing-masing jenjang (SD/SMP, PAUD/TK).</Step>
    <Step num={4} title="Konfirmasi & Kirim">
      Setelah dikonfirmasi, sistem akan otomatis:
      <ul className="list-disc list-inside mt-1 space-y-1 text-xs">
        <li>Mencatat pengiriman di database</li>
        <li>Memotong stok bahan berdasarkan BOM menu hari itu</li>
        <li>Membuat catatan piutang (receivable) ke pemerintah</li>
        <li>Update data anggaran realisasi</li>
      </ul>
    </Step>
    <Tip>Penyerahan juga bisa dilihat dan dimonitor di Web → MBG Penyerahan & Nutrisi. Web hanya untuk monitoring, input dilakukan via Telegram.</Tip>
    <Warning>Pastikan jadwal menu mingguan sudah diatur di MBG → Jadwal sebelum melakukan penyerahan. Jika belum ada jadwal, stok tidak akan terpotong otomatis.</Warning>
  </div>);
}

function SectionStok() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Stok bahan dikelola secara otomatis. Bertambah saat belanja, berkurang saat penyerahan MBG.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Sumber Pergerakan Stok</h3>
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs border-collapse bg-white rounded-xl overflow-hidden border border-gray-200">
        <thead><tr className="bg-gray-800 text-white"><th className="px-4 py-2.5 text-left">Aksi</th><th className="px-4 py-2.5 text-left">Efek Stok</th><th className="px-4 py-2.5 text-left">Sumber</th></tr></thead>
        <tbody>
          <tr className="border-b"><td className="px-4 py-2">Belanja (Telegram/Web)</td><td className="px-4 py-2 text-green-600 font-bold">+ Bertambah</td><td className="px-4 py-2">Otomatis dari transaksi</td></tr>
          <tr className="border-b"><td className="px-4 py-2">Penyerahan MBG</td><td className="px-4 py-2 text-red-600 font-bold">− Berkurang</td><td className="px-4 py-2">Otomatis dari BOM × porsi</td></tr>
          <tr className="border-b"><td className="px-4 py-2">Koreksi Manual / Opname</td><td className="px-4 py-2 text-blue-600 font-bold">± Adjustment</td><td className="px-4 py-2">Manual di Web → Stok</td></tr>
          <tr><td className="px-4 py-2">Import Data</td><td className="px-4 py-2 text-green-600 font-bold">+ Bertambah</td><td className="px-4 py-2">Pengaturan → Import</td></tr>
        </tbody>
      </table>
    </div>
    <Tip>Cek stok cepat via Telegram dengan perintah <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">/stok</code>. Bahan yang menipis (di bawah stok minimum) akan ditandai merah.</Tip>
    <Warning>Jika Anda belanja bahan di Telegram DAN juga di Web untuk transaksi yang sama, stok akan double. Pilih salah satu jalur input saja.</Warning>
  </div>);
}

function SectionAnggaran() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Halaman Keuangan & Anggaran menyediakan pemantauan realisasi dana MBG terhadap pagu yang ditetapkan pemerintah.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Istilah Penting</h3>
    <div className="space-y-2">
      {[
        { term: "Pagu Anggaran", desc: "Batas maksimal dana yang dialokasikan pemerintah untuk bulan ini." },
        { term: "Dana Cair", desc: "Uang yang sudah benar-benar masuk ke rekening VA Bank MBG." },
        { term: "Total Terpakai", desc: "Seluruh pengeluaran nyata: Belanja bahan + Operasional + Gaji." },
        { term: "Sisa Anggaran", desc: "Dana Cair − Total Terpakai. Ini adalah uang sisa yang masih bisa digunakan." },
        { term: "Tagihan Terbentuk", desc: "Nilai klaim porsi MBG ke pemerintah. Ini BUKAN pendapatan/revenue." },
        { term: "Piutang Bahan Pangan", desc: "Hak tagih komponen bahan (Rp 10.000/porsi) yang belum masuk kas." },
        { term: "Sewa Dapur", desc: "Satu-satunya sumber keuntungan/profit pemilik usaha." },
      ].map((item, i) => (
        <div key={i} className="flex gap-3 bg-gray-50 rounded-xl p-3 border border-gray-100">
          <span className="font-bold text-indigo-700 text-sm shrink-0 w-40">{item.term}</span>
          <span className="text-sm text-gray-600">{item.desc}</span>
        </div>
      ))}
    </div>
    <Warning>Dana MBG bersifat <b>titipan/amanat</b>. Kata "Revenue" atau "Pendapatan" tidak tepat digunakan untuk nilai porsi. Satu-satunya profit yang sah adalah komponen Sewa Dapur.</Warning>
  </div>);
}

function SectionAkuntan() {
  return (<div className="space-y-4">
    <p className="text-gray-700 leading-relaxed">Peran Akuntan memiliki akses khusus ke modul pembukuan dan laporan. Berikut panduan untuk pengguna dengan peran Akuntan.</p>
    <h3 className="font-bold text-gray-900 mt-4 mb-2">Akses yang Tersedia</h3>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {[
        { icon: "✅", label: "Dashboard (read-only)", desc: "Lihat ringkasan operasional" },
        { icon: "✅", label: "Pembukuan", desc: "Log transaksi & download laporan" },
        { icon: "✅", label: "Keuangan & Anggaran", desc: "Pantau realisasi vs pagu" },
        { icon: "✅", label: "MBG Penyerahan", desc: "Monitor data pengiriman" },
        { icon: "⛔", label: "Settings (terbatas)", desc: "Tidak bisa ubah konfigurasi" },
        { icon: "⛔", label: "Hapus Data", desc: "Tidak bisa menghapus transaksi" },
      ].map((item, i) => (
        <div key={i} className="flex gap-3 items-center bg-white border border-gray-100 rounded-xl p-3 shadow-sm">
          <span className="text-lg">{item.icon}</span>
          <div>
            <span className="font-bold text-gray-900 text-sm">{item.label}</span>
            <p className="text-xs text-gray-500">{item.desc}</p>
          </div>
        </div>
      ))}
    </div>
    <h3 className="font-bold text-gray-900 mt-6 mb-2">Workflow Akuntan Bulanan</h3>
    <Step num={1} title="Periksa Log Transaksi di Pembukuan">Filter berdasarkan bulan berjalan. Pastikan semua nota sudah tercatat dan statusnya lunas.</Step>
    <Step num={2} title="Cek Keuangan & Anggaran">Bandingkan Pagu vs Dana Cair vs Terpakai. Pastikan realisasi tidak melebihi target alokasi.</Step>
    <Step num={3} title="Download Laporan Excel Dinas">Di Pembukuan → Kumpulan Dokumen → Generate Excel. Laporan berisi 10 sheet lengkap untuk pelaporan ke Dinas.</Step>
    <Step num={4} title="Periksa Piutang & Hutang">Pastikan piutang bahan pangan sesuai dengan jumlah porsi yang sudah diserahkan.</Step>
    <Tip>Jika Anda menemukan perbedaan angka antara Pembukuan (belanja struk) dan Anggaran (total terpakai), itu wajar. Anggaran termasuk biaya operasional/gaji yang tidak muncul di log transaksi kasir.</Tip>
  </div>);
}

export function TabTips() {
  const [active, setActive] = useState<Section>("overview");

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">📖</span>
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Panduan & Tips Penggunaan</h2>
          <p className="text-sm text-gray-500">Pelajari cara menggunakan seluruh fitur sistem MBG Catering</p>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar */}
        <div className="lg:w-56 shrink-0">
          <nav className="flex lg:flex-col gap-1.5 overflow-x-auto lg:overflow-x-visible no-scrollbar bg-gray-50 lg:bg-transparent rounded-2xl lg:rounded-none p-2 lg:p-0 border border-gray-100 lg:border-0">
            {sections.map((s) => (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                className={`flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm font-semibold whitespace-nowrap transition-all duration-200 text-left ${
                  active === s.id
                    ? "bg-white text-indigo-700 shadow-md ring-1 ring-indigo-100 scale-[1.02]"
                    : "text-gray-500 hover:text-gray-900 hover:bg-white/60"
                }`}
              >
                <span className="text-base">{s.icon}</span>
                <span>{s.title}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm min-h-[400px]">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2 border-b border-gray-100 pb-3">
              <span className="text-xl">{sections.find(s => s.id === active)?.icon}</span>
              {sections.find(s => s.id === active)?.title}
            </h3>
            {active === "overview" && <SectionOverview />}
            {active === "telegram" && <SectionTelegram />}
            {active === "bahan" && <SectionBahan />}
            {active === "bom" && <SectionBOM />}
            {active === "penyerahan" && <SectionPenyerahan />}
            {active === "stok" && <SectionStok />}
            {active === "anggaran" && <SectionAnggaran />}
            {active === "akuntan" && <SectionAkuntan />}
          </div>
        </div>
      </div>
    </div>
  );
}
