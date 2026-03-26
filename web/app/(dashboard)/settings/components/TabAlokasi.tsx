"use client";

export function TabAlokasi() {
    return (
        <div>
            <h2 className="text-2xl font-bold mb-6">Alokasi Anggaran MBG</h2>
            
            <div className="bg-blue-50 border border-blue-200 text-blue-900 p-6 rounded-xl">
                <h3 className="font-bold text-lg mb-2">ℹ️ Perubahan Sistem Alokasi</h3>
                <p className="mb-4">
                    Sistem alokasi anggaran persentase secara global yang sebelumnya menggunakan format 80:15:5 <b>telah dinonaktifkan</b>. Sistem saat ini telah diganti dengan 
                    sistem <b>Alokasi Harga Per Porsi (Fixed Budget)</b> yang lebih spesifik untuk setiap sekolah.
                </p>
                <p className="mb-4">
                    Alokasi per porsi dipisah menjadi metrik yang riil:
                    <ul className="list-disc ml-6 mt-2">
                        <li><b>Bahan Pangan:</b> Rp 10.000 / Rp 8.000</li>
                        <li><b>Operasional & Upah:</b> Rp 3.000 (Gaji: Rp 1.500, BBM: Rp 1.200, Utilitas: Rp 300)</li>
                        <li><b>Sewa Dapur (Laba/Net Profit):</b> Rp 2.000</li>
                    </ul>
                </p>
                <p>
                    Silakan atur alokasi (Paket Besar Rp 15.000 atau Paket Kecil Rp 13.000) 
                    secara individual pada tab <b>Sekolah & Beneficiaries</b> saat Anda menambah atau mengedit sekolah.
                </p>
            </div>
        </div>
    );
}
