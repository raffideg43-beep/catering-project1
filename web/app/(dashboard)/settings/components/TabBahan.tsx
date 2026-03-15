"use client";

import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Rupiah } from "@/components/ui/rupiah";

/* ═══ Types ════════════════════════════════════════════════════════════════ */

interface Product {
  id: string; name: string; category: string; unit: string;
  stock_qty: number; stock_min: number; hpp: number; sell_price: number;
}

interface ComponentItem {
  id: string; component_id: string; ingredient_id: string;
  qty_needed: number; unit: string | null; product_name: string | null;
}

interface Component {
  id: string; tenant_id: string; name: string;
  description: string | null; is_active: boolean;
  items: ComponentItem[];
}

interface Recipe {
  id: string; menu_id: string; ingredient_id: string | null;
  component_id: string | null; qty_needed: number; unit: string;
}

interface SimIngredient {
  ingredient_id: string; name: string; unit: string;
  total_needed: number; available: number; sufficient: boolean; shortage: number;
}

/* ═══ Main TabBahan ════════════════════════════════════════════════════════ */

export function TabBahan() {
  const [products, setProducts] = useState<Product[]>([]);
  const [bahan, setBahan] = useState<Product[]>([]);
  const [menus, setMenus] = useState<Product[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [loading, setLoading] = useState(true);

  /* ─── Bahan form ─────────────────────────────────────────────────── */
  const [showBahanModal, setShowBahanModal] = useState(false);
  const [editingBahanId, setEditingBahanId] = useState<string | null>(null);
  const [bahanForm, setBahanForm] = useState({
    name: "", category: "bahan_baku", unit: "kg", hpp: 0, sell_price: 0, stock_min: 0, notes: ""
  });

  /* ─── Component form ─────────────────────────────────────────────── */
  const [showCompModal, setShowCompModal] = useState(false);
  const [editingCompId, setEditingCompId] = useState<string | null>(null);
  const [compForm, setCompForm] = useState({ name: "", description: "" });

  /* ─── Component item form ────────────────────────────────────────── */
  const [addingItemFor, setAddingItemFor] = useState<string | null>(null);
  const [itemForm, setItemForm] = useState({ ingredient_id: "", qty_needed: 0, unit: "" });

  /* ─── Menu BOM ───────────────────────────────────────────────────── */
  const [expandedMenu, setExpandedMenu] = useState<string | null>(null);
  const [menuRecipes, setMenuRecipes] = useState<Record<string, Recipe[]>>({});
  const [bomPreview, setBomPreview] = useState<Record<string, SimIngredient[]>>({});
  const [attachingComp, setAttachingComp] = useState<string | null>(null);
  const [attachCompId, setAttachCompId] = useState("");
  const [addingDirectFor, setAddingDirectFor] = useState<string | null>(null);
  const [directForm, setDirectForm] = useState({ ingredient_id: "", qty_needed: 0, unit: "" });

  /* ─── Menu form ──────────────────────────────────────────────────── */
  const [showMenuModal, setShowMenuModal] = useState(false);
  const [menuForm, setMenuForm] = useState({ name: "", unit: "porsi" });

  /* ═══ Data fetching ══════════════════════════════════════════════════ */

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [prodRes, compRes] = await Promise.all([
        apiGet("/products"),
        apiGet("/recipes/components"),
      ]);
      const allProducts: Product[] = prodRes?.data?.items || prodRes?.data || [];
      setProducts(allProducts);
      setBahan(allProducts.filter((p: Product) => p.category === "bahan_baku" || p.category === "kemasan"));
      setMenus(allProducts.filter((p: Product) => p.category === "produk_jadi"));
      setComponents(compRes?.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const fetchMenuRecipes = async (menuId: string) => {
    try {
      const res = await apiGet("/recipes");
      const all: Recipe[] = res?.data || [];
      setMenuRecipes(prev => ({ ...prev, [menuId]: all.filter(r => r.menu_id === menuId) }));
    } catch (e) { console.error(e); }
  };

  const fetchBomPreview = async (menuId: string) => {
    try {
      const res = await apiGet(`/recipes/simulate?menu_id=${menuId}&qty=1`);
      setBomPreview(prev => ({ ...prev, [menuId]: res?.data?.ingredients || [] }));
    } catch (e) { console.error(e); }
  };

  /* ═══ Handlers ═══════════════════════════════════════════════════════ */

  // ── Bahan
  const openBahanForm = (prod?: Product) => {
    if (prod) {
      setEditingBahanId(prod.id);
      setBahanForm({ name: prod.name, category: prod.category, unit: prod.unit, hpp: prod.hpp, sell_price: prod.sell_price, stock_min: prod.stock_min, notes: "" });
    } else {
      setEditingBahanId(null);
      setBahanForm({ name: "", category: "bahan_baku", unit: "kg", hpp: 0, sell_price: 0, stock_min: 0, notes: "" });
    }
    setShowBahanModal(true);
  };

  const saveBahan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingBahanId) await apiPut(`/products/${editingBahanId}`, bahanForm);
      else await apiPost("/products", { ...bahanForm, stock_qty: 0 });
      setShowBahanModal(false);
      fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menyimpan bahan"); }
  };

  const deleteBahan = async (id: string) => {
    if (!confirm("Hapus bahan ini?")) return;
    try { await apiDelete(`/products/${id}`); fetchAll(); } catch { alert("Gagal menghapus bahan"); }
  };

  // ── Component
  const openCompForm = (comp?: Component) => {
    if (comp) {
      setEditingCompId(comp.id);
      setCompForm({ name: comp.name, description: comp.description || "" });
    } else {
      setEditingCompId(null);
      setCompForm({ name: "", description: "" });
    }
    setShowCompModal(true);
  };

  const saveComp = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingCompId) await apiPut(`/recipes/components/${editingCompId}`, compForm);
      else await apiPost("/recipes/components", compForm);
      setShowCompModal(false);
      fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menyimpan komponen"); }
  };

  const deleteComp = async (id: string) => {
    if (!confirm("Hapus komponen ini?")) return;
    try { await apiDelete(`/recipes/components/${id}`); fetchAll(); }
    catch (err: any) { alert(err?.response?.data?.detail || "Gagal menghapus komponen"); }
  };

  const saveCompItem = async (compId: string) => {
    if (!itemForm.ingredient_id || itemForm.qty_needed <= 0) return;
    try {
      await apiPost(`/recipes/components/${compId}/items`, itemForm);
      setAddingItemFor(null);
      setItemForm({ ingredient_id: "", qty_needed: 0, unit: "" });
      fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menambah bahan"); }
  };

  const deleteCompItem = async (compId: string, itemId: string) => {
    try { await apiDelete(`/recipes/components/${compId}/items/${itemId}`); fetchAll(); }
    catch { alert("Gagal menghapus bahan"); }
  };

  // ── Menu BOM
  const toggleMenu = async (menuId: string) => {
    if (expandedMenu === menuId) { setExpandedMenu(null); return; }
    setExpandedMenu(menuId);
    await fetchMenuRecipes(menuId);
  };

  const attachComponent = async (menuId: string) => {
    if (!attachCompId) return;
    try {
      await apiPost("/recipes/attach-component", { menu_id: menuId, component_id: attachCompId });
      setAttachingComp(null);
      setAttachCompId("");
      await fetchMenuRecipes(menuId);
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menambah komponen"); }
  };

  const addDirectIngredient = async (menuId: string) => {
    if (!directForm.ingredient_id || directForm.qty_needed <= 0) return;
    try {
      await apiPost("/recipes", {
        menu_id: menuId, ingredient_id: directForm.ingredient_id,
        qty_needed: directForm.qty_needed, unit: directForm.unit || "kg"
      });
      setAddingDirectFor(null);
      setDirectForm({ ingredient_id: "", qty_needed: 0, unit: "" });
      await fetchMenuRecipes(menuId);
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menambah bahan"); }
  };

  const deleteRecipe = async (recipeId: string, menuId: string) => {
    try { await apiDelete(`/recipes/${recipeId}`); await fetchMenuRecipes(menuId); }
    catch { alert("Gagal menghapus"); }
  };

  const saveMenu = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiPost("/products", { ...menuForm, category: "produk_jadi", stock_qty: 0, hpp: 0, sell_price: 0, stock_min: 0 });
      setShowMenuModal(false);
      setMenuForm({ name: "", unit: "porsi" });
      fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menyimpan menu"); }
  };

  /* ═══ Render helpers ═════════════════════════════════════════════════ */

  const getCompName = (compId: string) => components.find(c => c.id === compId)?.name || "?";
  const getIngName = (ingId: string) => products.find(p => p.id === ingId)?.name || "?";

  if (loading) return <div className="text-gray-500 py-8 text-center">Memuat data...</div>;

  /* ═══ JSX ════════════════════════════════════════════════════════════ */
  return (
    <div className="space-y-10">

      {/* ═══════════════════ BAGIAN 1: BAHAN BAKU ═══════════════════════ */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🧪 Bahan Baku & Kemasan</h2>
            <p className="text-gray-500 text-sm mt-1">Kelola master data bahan baku pembentuk resep MBG.</p>
          </div>
          <button onClick={() => openBahanForm()} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium text-sm">+ Tambah Bahan</button>
        </div>

        {bahan.length === 0 ? (
          <div className="text-gray-400 text-center py-6 bg-gray-50 rounded-lg">Belum ada data bahan baku.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm text-left border-collapse">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-4 py-3 font-semibold text-gray-700">Nama Bahan</th>
                  <th className="px-4 py-3 font-semibold text-gray-700">Kategori</th>
                  <th className="px-4 py-3 font-semibold text-gray-700">Satuan</th>
                  <th className="px-4 py-3 font-semibold text-gray-700">HPP</th>
                  <th className="px-4 py-3 font-semibold text-gray-700">Min. Stok</th>
                  <th className="px-4 py-3 font-semibold text-gray-700">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {bahan.map(p => (
                  <tr key={p.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{p.name}</td>
                    <td className="px-4 py-3 text-gray-600 capitalize">{p.category.replace("_", " ")}</td>
                    <td className="px-4 py-3 text-gray-600">{p.unit}</td>
                    <td className="px-4 py-3 text-gray-600"><Rupiah amount={p.hpp} /></td>
                    <td className="px-4 py-3 text-gray-600">{p.stock_min}</td>
                    <td className="px-4 py-3 flex gap-2">
                      <button onClick={() => openBahanForm(p)} className="text-blue-600 hover:text-blue-800 font-medium px-2 py-1 bg-blue-50 rounded text-xs">Edit</button>
                      <button onClick={() => deleteBahan(p.id)} className="text-red-600 hover:text-red-800 font-medium px-2 py-1 bg-red-50 rounded text-xs">Hapus</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <hr className="border-gray-200" />

      {/* ═══════════════════ BAGIAN 2: KOMPONEN ═════════════════════════ */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🧩 Komponen Resep (Reusable)</h2>
            <p className="text-gray-500 text-sm mt-1">Buat komponen sekali, pakai di banyak menu.</p>
          </div>
          <button onClick={() => openCompForm()} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium text-sm">+ Komponen Baru</button>
        </div>

        {components.length === 0 ? (
          <div className="text-gray-400 text-center py-6 bg-gray-50 rounded-lg">Belum ada komponen. Buat komponen resep reusable di sini.</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {components.map(comp => (
              <div key={comp.id} className="border rounded-xl p-4 bg-white shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-bold text-gray-900 text-lg">{comp.name}</h3>
                    {comp.description && <p className="text-gray-500 text-sm">{comp.description}</p>}
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => openCompForm(comp)} className="text-blue-600 hover:text-blue-800 px-2 py-1 bg-blue-50 rounded text-xs font-medium">✏️</button>
                    <button onClick={() => deleteComp(comp.id)} className="text-red-600 hover:text-red-800 px-2 py-1 bg-red-50 rounded text-xs font-medium">🗑️</button>
                  </div>
                </div>

                {/* Component items */}
                <div className="space-y-1 mb-3">
                  {comp.items.length === 0 ? (
                    <p className="text-gray-400 text-sm italic">Belum ada bahan</p>
                  ) : (
                    comp.items.map(item => (
                      <div key={item.id} className="flex justify-between items-center text-sm bg-gray-50 px-3 py-1.5 rounded">
                        <span className="text-gray-700">• {item.product_name || getIngName(item.ingredient_id)} <span className="text-gray-500">{item.qty_needed} {item.unit}</span></span>
                        <button onClick={() => deleteCompItem(comp.id, item.id)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                      </div>
                    ))
                  )}
                </div>

                {/* Add item form */}
                {addingItemFor === comp.id ? (
                  <div className="flex gap-2 items-end mt-2">
                    <select value={itemForm.ingredient_id} onChange={e => setItemForm({ ...itemForm, ingredient_id: e.target.value })}
                      className="flex-1 px-2 py-1.5 border rounded text-sm bg-white">
                      <option value="">Pilih bahan...</option>
                      {bahan.map(b => <option key={b.id} value={b.id}>{b.name} ({b.unit})</option>)}
                    </select>
                    <input type="number" step="0.001" min="0" placeholder="Qty" value={itemForm.qty_needed || ""} onChange={e => setItemForm({ ...itemForm, qty_needed: parseFloat(e.target.value) || 0 })}
                      className="w-20 px-2 py-1.5 border rounded text-sm" />
                    <button onClick={() => saveCompItem(comp.id)} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">✅</button>
                    <button onClick={() => setAddingItemFor(null)} className="px-2 py-1.5 text-gray-500 hover:text-gray-700 text-sm">✕</button>
                  </div>
                ) : (
                  <button onClick={() => { setAddingItemFor(comp.id); setItemForm({ ingredient_id: "", qty_needed: 0, unit: "" }); }}
                    className="text-purple-600 hover:text-purple-800 text-sm font-medium mt-1">+ Tambah Bahan</button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <hr className="border-gray-200" />

      {/* ═══════════════════ BAGIAN 3: MENU & BOM ══════════════════════ */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🍽️ Menu & Resep BOM</h2>
            <p className="text-gray-500 text-sm mt-1">Setiap menu = kombinasi komponen + bahan tambahan.</p>
          </div>
          <button onClick={() => setShowMenuModal(true)} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-medium text-sm">+ Menu Baru</button>
        </div>

        {menus.length === 0 ? (
          <div className="text-gray-400 text-center py-6 bg-gray-50 rounded-lg">Belum ada menu (produk jadi).</div>
        ) : (
          <div className="space-y-3">
            {menus.map(menu => {
              const isOpen = expandedMenu === menu.id;
              const recipes = menuRecipes[menu.id] || [];
              const compRecipes = recipes.filter(r => r.component_id);
              const directRecipes = recipes.filter(r => r.ingredient_id && !r.component_id);
              const preview = bomPreview[menu.id];

              return (
                <div key={menu.id} className="border rounded-xl bg-white shadow-sm overflow-hidden">
                  {/* Header */}
                  <button onClick={() => toggleMenu(menu.id)}
                    className="w-full flex justify-between items-center px-5 py-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{isOpen ? "▼" : "▶"}</span>
                      <div className="text-left">
                        <span className="font-bold text-gray-900">{menu.name}</span>
                        <span className="text-gray-500 text-sm ml-2">({menu.unit})</span>
                      </div>
                    </div>
                    <span className="text-gray-400 text-sm">
                      {compRecipes.length} komponen, {directRecipes.length} bahan langsung
                    </span>
                  </button>

                  {/* Expanded content */}
                  {isOpen && (
                    <div className="px-5 pb-5 border-t bg-gray-50/50 space-y-4">

                      {/* Komponen attached */}
                      <div className="mt-4">
                        <h4 className="font-semibold text-gray-700 mb-2 text-sm">🧩 Komponen:</h4>
                        {compRecipes.length === 0 ? (
                          <p className="text-gray-400 text-sm italic">Belum ada komponen</p>
                        ) : (
                          <div className="space-y-1">
                            {compRecipes.map(r => (
                              <div key={r.id} className="flex justify-between items-center bg-purple-50 px-3 py-2 rounded text-sm">
                                <span className="text-purple-800">🧩 {getCompName(r.component_id!)}</span>
                                <button onClick={() => deleteRecipe(r.id, menu.id)} className="text-red-400 hover:text-red-600 text-xs">🗑️</button>
                              </div>
                            ))}
                          </div>
                        )}

                        {attachingComp === menu.id ? (
                          <div className="flex gap-2 mt-2">
                            <select value={attachCompId} onChange={e => setAttachCompId(e.target.value)}
                              className="flex-1 px-2 py-1.5 border rounded text-sm bg-white">
                              <option value="">Pilih komponen...</option>
                              {components.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                            </select>
                            <button onClick={() => attachComponent(menu.id)} className="px-3 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700">✅</button>
                            <button onClick={() => setAttachingComp(null)} className="px-2 py-1.5 text-gray-500 text-sm">✕</button>
                          </div>
                        ) : (
                          <button onClick={() => { setAttachingComp(menu.id); setAttachCompId(""); }}
                            className="text-purple-600 hover:text-purple-800 text-sm font-medium mt-2">+ Attach Komponen</button>
                        )}
                      </div>

                      {/* Direct ingredients */}
                      <div>
                        <h4 className="font-semibold text-gray-700 mb-2 text-sm">🧪 Bahan Tambahan:</h4>
                        {directRecipes.length === 0 ? (
                          <p className="text-gray-400 text-sm italic">Belum ada bahan langsung</p>
                        ) : (
                          <div className="space-y-1">
                            {directRecipes.map(r => (
                              <div key={r.id} className="flex justify-between items-center bg-green-50 px-3 py-2 rounded text-sm">
                                <span className="text-green-800">• {getIngName(r.ingredient_id!)} <span className="text-green-600">{r.qty_needed} {r.unit}</span></span>
                                <button onClick={() => deleteRecipe(r.id, menu.id)} className="text-red-400 hover:text-red-600 text-xs">🗑️</button>
                              </div>
                            ))}
                          </div>
                        )}

                        {addingDirectFor === menu.id ? (
                          <div className="flex gap-2 items-end mt-2">
                            <select value={directForm.ingredient_id} onChange={e => setDirectForm({ ...directForm, ingredient_id: e.target.value })}
                              className="flex-1 px-2 py-1.5 border rounded text-sm bg-white">
                              <option value="">Pilih bahan...</option>
                              {bahan.map(b => <option key={b.id} value={b.id}>{b.name} ({b.unit})</option>)}
                            </select>
                            <input type="number" step="0.001" min="0" placeholder="Qty" value={directForm.qty_needed || ""} onChange={e => setDirectForm({ ...directForm, qty_needed: parseFloat(e.target.value) || 0 })}
                              className="w-20 px-2 py-1.5 border rounded text-sm" />
                            <input type="text" placeholder="unit" value={directForm.unit} onChange={e => setDirectForm({ ...directForm, unit: e.target.value })}
                              className="w-16 px-2 py-1.5 border rounded text-sm" />
                            <button onClick={() => addDirectIngredient(menu.id)} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">✅</button>
                            <button onClick={() => setAddingDirectFor(null)} className="px-2 py-1.5 text-gray-500 text-sm">✕</button>
                          </div>
                        ) : (
                          <button onClick={() => { setAddingDirectFor(menu.id); setDirectForm({ ingredient_id: "", qty_needed: 0, unit: "" }); }}
                            className="text-green-600 hover:text-green-800 text-sm font-medium mt-2">+ Tambah Bahan Langsung</button>
                        )}
                      </div>

                      {/* BOM Preview */}
                      <div>
                        <button onClick={() => fetchBomPreview(menu.id)}
                          className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors">
                          👁️ Lihat Total Bahan (BOM Preview)
                        </button>

                        {preview && (
                          <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <h4 className="font-bold text-blue-800 mb-2 text-sm">📋 Total Bahan per 1 Porsi (Setelah Expand Komponen):</h4>
                            {preview.length === 0 ? (
                              <p className="text-gray-500 text-sm">Tidak ada bahan (BOM kosong)</p>
                            ) : (
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="text-left text-blue-700 border-b border-blue-200">
                                    <th className="py-1 pr-4">Bahan</th>
                                    <th className="py-1 pr-4">Butuh</th>
                                    <th className="py-1 pr-4">Stok</th>
                                    <th className="py-1">Status</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {preview.map((ing, i) => (
                                    <tr key={i} className="border-b border-blue-100">
                                      <td className="py-1.5 pr-4 font-medium text-gray-800">{ing.name}</td>
                                      <td className="py-1.5 pr-4 text-gray-600">{ing.total_needed} {ing.unit}</td>
                                      <td className="py-1.5 pr-4 text-gray-600">{ing.available} {ing.unit}</td>
                                      <td className="py-1.5">{ing.sufficient
                                        ? <span className="text-green-600 font-medium">✅ Cukup</span>
                                        : <span className="text-red-600 font-medium">❌ Kurang {ing.shortage}</span>}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        )}
                      </div>

                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* ═══════════════════ MODALS ═════════════════════════════════════ */}

      {/* Bahan Modal */}
      {showBahanModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">{editingBahanId ? "Edit" : "Tambah"} Bahan Baku</h3>
            <form onSubmit={saveBahan} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Bahan</label>
                <input required type="text" value={bahanForm.name} onChange={e => setBahanForm({ ...bahanForm, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
                  <select value={bahanForm.category} onChange={e => setBahanForm({ ...bahanForm, category: e.target.value })} className="w-full px-4 py-2 border rounded-lg bg-white">
                    <option value="bahan_baku">Bahan Baku</option>
                    <option value="kemasan">Kemasan</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Satuan Dasar</label>
                  <input required placeholder="kg, liter, pcs" type="text" value={bahanForm.unit} onChange={e => setBahanForm({ ...bahanForm, unit: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Harga Beli (HPP)</label>
                  <input type="number" required min="0" value={bahanForm.hpp} onChange={e => setBahanForm({ ...bahanForm, hpp: parseInt(e.target.value) || 0 })} className="w-full px-4 py-2 border rounded-lg" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Min. Stok</label>
                  <input type="number" required min="0" step="0.1" value={bahanForm.stock_min} onChange={e => setBahanForm({ ...bahanForm, stock_min: parseFloat(e.target.value) || 0 })} className="w-full px-4 py-2 border rounded-lg" />
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setShowBahanModal(false)} className="flex-1 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium">Simpan</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Component Modal */}
      {showCompModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">{editingCompId ? "Edit" : "Buat"} Komponen</h3>
            <form onSubmit={saveComp} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Komponen</label>
                <input required type="text" placeholder="mis: Nasi Putih, Ayam Goreng" value={compForm.name} onChange={e => setCompForm({ ...compForm, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Deskripsi (opsional)</label>
                <input type="text" placeholder="Keterangan singkat" value={compForm.description} onChange={e => setCompForm({ ...compForm, description: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
              </div>
              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setShowCompModal(false)} className="flex-1 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" className="flex-1 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium">Simpan</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Menu Modal */}
      {showMenuModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h3 className="text-xl font-bold mb-4">Menu Baru</h3>
            <form onSubmit={saveMenu} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nama Menu</label>
                <input required type="text" placeholder="mis: Nasi Ayam Fillet" value={menuForm.name} onChange={e => setMenuForm({ ...menuForm, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Satuan</label>
                <input type="text" value={menuForm.unit} onChange={e => setMenuForm({ ...menuForm, unit: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
              </div>
              <div className="flex gap-3 mt-6">
                <button type="button" onClick={() => setShowMenuModal(false)} className="flex-1 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" className="flex-1 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-medium">Simpan</button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
