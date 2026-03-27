"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { Plus, Edit2, Ban, CheckCircle, XCircle } from "lucide-react";

type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  telegram_id: number | null;
  is_active: boolean;
};

export function TabUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  // Add form
  const [addForm, setAddForm] = useState({ name: "", email: "", password: "", role: "admin" });

  // Role form
  const [newRole, setNewRole] = useState("");

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiGet("/auth/users");
      if (res?.data) {
        setUsers(res.data);
      }
    } catch (err: any) {
      if (err?.response?.status === 403) {
        setError("Hanya Owner yang dapat mengakses menu ini.");
      } else {
        setError("Gagal memuat data pengguna.");
      }
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleAddUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await apiPost("/auth/users/invite", addForm);
      setSuccess("User berhasil ditambahkan.");
      setShowAddModal(false);
      setAddForm({ name: "", email: "", password: "", role: "admin" });
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.error || "Gagal menambah user.");
    }
  };

  const handleUpdateRole = async () => {
    if (!selectedUser) return;
    setError("");
    setSuccess("");
    try {
      await apiPut(`/auth/users/${selectedUser.id}/role`, { role: newRole });
      setSuccess(`Role ${selectedUser.name} berhasil diubah.`);
      setShowRoleModal(false);
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.error || "Gagal mengubah role.");
    }
  };

  const handleToggleStatus = async () => {
    if (!selectedUser) return;
    setError("");
    setSuccess("");
    try {
      const newStatus = !selectedUser.is_active;
      await apiPut(`/auth/users/${selectedUser.id}/status`, { is_active: newStatus });
      setSuccess(`Status ${selectedUser.name} berhasil diubah.`);
      setShowStatusModal(false);
      fetchUsers();
    } catch (err: any) {
      setError(err?.response?.data?.error || "Gagal mengubah status.");
    }
  };

  const openRoleModal = (user: User) => {
    setSelectedUser(user);
    setNewRole(user.role);
    setShowRoleModal(true);
  };

  const openStatusModal = (user: User) => {
    setSelectedUser(user);
    setShowStatusModal(true);
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "owner": return <span className="px-2 py-1 text-xs rounded-full bg-blue-900 text-white font-medium">Owner</span>;
      case "admin": return <span className="px-2 py-1 text-xs rounded-full bg-blue-500 text-white font-medium">Admin</span>;
      case "kasir": return <span className="px-2 py-1 text-xs rounded-full bg-green-500 text-white font-medium">Kasir</span>;
      case "viewer": return <span className="px-2 py-1 text-xs rounded-full bg-gray-500 text-white font-medium">Viewer</span>;
      case "driver": return <span className="px-2 py-1 text-xs rounded-full bg-amber-500 text-amber-900 font-medium">Driver</span>;
      default: return <span className="px-2 py-1 text-xs rounded-full bg-gray-200 text-gray-800 font-medium">{role}</span>;
    }
  };

  if (loading) return <div className="py-8 text-center text-gray-500">Memuat data user...</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Tim & Akses</h2>
          <p className="text-sm text-gray-500 mt-1">Kelola anggota tim dan hak akses mereka.</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <Plus className="w-4 h-4 mr-2" />
          Tambah User
        </button>
      </div>

      {error && <div className="mb-4 bg-red-50 text-red-600 p-3 rounded-lg text-sm">{error}</div>}
      {success && <div className="mb-4 bg-green-50 text-green-600 p-3 rounded-lg text-sm">{success}</div>}

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b">
              <th className="p-4 font-medium text-gray-500">Nama</th>
              <th className="p-4 font-medium text-gray-500">Role</th>
              <th className="p-4 font-medium text-gray-500">Email</th>
              <th className="p-4 font-medium text-gray-500 text-center">Telegram</th>
              <th className="p-4 font-medium text-gray-500 text-center">Status</th>
              <th className="p-4 font-medium text-gray-500 text-center">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y text-sm">
            {users.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-500">
                  Tidak ada data user.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition">
                  <td className="p-4 font-medium text-gray-900">{u.name}</td>
                  <td className="p-4">{getRoleBadge(u.role)}</td>
                  <td className="p-4 text-gray-600">{u.email}</td>
                  <td className="p-4 text-center">
                    {u.telegram_id ? (
                      <span className="inline-flex items-center px-2 py-1 bg-green-50 text-green-700 rounded-full text-xs">
                        <CheckCircle className="w-3 h-3 mr-1" /> Terhubung
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-1 bg-red-50 text-red-700 rounded-full text-xs">
                        <XCircle className="w-3 h-3 mr-1" /> Belum
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${u.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
                      {u.is_active ? "Aktif" : "Non-aktif"}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex justify-center space-x-3">
                      {u.role !== "owner" && (
                        <>
                          <button onClick={() => openRoleModal(u)} className="text-gray-400 hover:text-blue-600 transition" title="Ubah Role">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button onClick={() => openStatusModal(u)} className="text-gray-400 hover:text-red-600 transition" title={u.is_active ? "Nonaktifkan" : "Aktifkan"}>
                            <Ban className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      {u.role === "owner" && <span className="text-gray-300 text-xs">—</span>}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      
      <div className="mt-6 bg-blue-50 border border-blue-100 rounded-lg p-4 flex gap-3 text-sm text-blue-800">
        <span className="text-lg">ℹ️</span>
        <p>Untuk menghubungkan Telegram, user baru harus login dan men-generate token di tab Telegram masing-masing. Role Owner secara otomatis memiliki akses penuh ke semua fitur.</p>
      </div>

      {/* Modal Add User */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-bold mb-4">Tambah Anggota Tim</h3>
            <form onSubmit={handleAddUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Lengkap</label>
                <input required type="text" value={addForm.name} onChange={e => setAddForm({...addForm, name: e.target.value})} className="w-full border rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input required type="email" value={addForm.email} onChange={e => setAddForm({...addForm, email: e.target.value})} className="w-full border rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <input required type="password" value={addForm.password} onChange={e => setAddForm({...addForm, password: e.target.value})} className="w-full border rounded-lg p-2 focus:ring-2 focus:ring-blue-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Role Akses</label>
                <div className="space-y-2">
                  <label className="flex items-center p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="radio" name="role" value="admin" checked={addForm.role === "admin"} onChange={e => setAddForm({...addForm, role: e.target.value})} className="mr-3" />
                    <div>
                      <div className="font-medium text-sm">Admin</div>
                      <div className="text-xs text-gray-500">Semua fitur kecuali kelola pengaturan user & sistem</div>
                    </div>
                  </label>
                  <label className="flex items-center p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="radio" name="role" value="kasir" checked={addForm.role === "kasir"} onChange={e => setAddForm({...addForm, role: e.target.value})} className="mr-3" />
                    <div>
                      <div className="font-medium text-sm">Kasir</div>
                      <div className="text-xs text-gray-500">Input transaksi harian (belanja, serah, absen)</div>
                    </div>
                  </label>
                  <label className="flex items-center p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="radio" name="role" value="viewer" checked={addForm.role === "viewer"} onChange={e => setAddForm({...addForm, role: e.target.value})} className="mr-3" />
                    <div>
                      <div className="font-medium text-sm">Viewer</div>
                      <div className="text-xs text-gray-500">Hanya melihat data & laporan (Read-only)</div>
                    </div>
                  </label>
                  <label className="flex items-center p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="radio" name="role" value="driver" checked={addForm.role === "driver"} onChange={e => setAddForm({...addForm, role: e.target.value})} className="mr-3" />
                    <div>
                      <div className="font-medium text-sm">Driver</div>
                      <div className="text-xs text-gray-500">Melihat jadwal pengiriman (Modul Ekspedisi)</div>
                    </div>
                  </label>
                </div>
              </div>
              <div className="mt-6 flex justify-end space-x-3 pt-4 border-t">
                <button type="button" onClick={() => setShowAddModal(false)} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">Tambah User</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Update Role */}
      {showRoleModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-lg font-bold mb-2">Ubah Role — {selectedUser.name}</h3>
            <p className="text-sm text-gray-500 mb-4">Role saat ini: <span className="font-semibold uppercase">{selectedUser.role}</span></p>
            <div className="space-y-2 mb-6">
              {['admin', 'kasir', 'viewer', 'driver'].map(r => (
                  <label key={r} className={`flex items-center p-3 border rounded-lg cursor-pointer ${newRole === r ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'}`}>
                    <input type="radio" name="editRole" value={r} checked={newRole === r} onChange={e => setNewRole(e.target.value)} className="mr-3" />
                    <span className="font-medium text-sm capitalize">{r}</span>
                  </label>
              ))}
            </div>
            <div className="flex justify-end space-x-3 pt-4 border-t">
              <button type="button" onClick={() => setShowRoleModal(false)} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 font-medium">Batal</button>
              <button type="button" onClick={handleUpdateRole} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium flex items-center">
                <CheckCircle className="w-4 h-4 mr-2"/>
                Simpan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Status */}
      {showStatusModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 text-center">
            <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <Ban className="w-8 h-8"/>
            </div>
            <h3 className="text-lg font-bold mb-2">{selectedUser.is_active ? 'Nonaktifkan' : 'Aktifkan'} {selectedUser.name}?</h3>
            <p className="text-sm text-gray-500 mb-6">
              {selectedUser.is_active 
                ? "User yang dinonaktifkan tidak akan bisa login ke dalam sistem lagi hingga diaktifkan kembali." 
                : "User akan bisa login kembali ke dalam sistem."}
            </p>
            <div className="flex justify-center space-x-3">
              <button type="button" onClick={() => setShowStatusModal(false)} className="px-4 py-2 border rounded-lg text-gray-600 hover:bg-gray-50 font-medium">Batal</button>
              <button type="button" onClick={handleToggleStatus} className={`px-4 py-2 text-white rounded-lg font-medium ${selectedUser.is_active ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'}`}>
                Ya, {selectedUser.is_active ? 'Nonaktifkan' : 'Aktifkan'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
