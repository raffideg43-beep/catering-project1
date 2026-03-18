"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { Rupiah } from "@/components/ui/rupiah";
import { UNIT_GROUPS, formatStok } from "@/lib/utils";

/* ═══ Types ════════════════════════════════════════════════════════════════ */

interface Product {
  id: string; name: string; category: string; unit: string;
  base_unit?: string; display_unit?: string; conversion_factor?: number;
  stock_qty: number; stock_qty_display?: number; stock_min: number; stock_min_display?: number;
  hpp: number; sell_price: number;
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

interface FormRowItem {
  ingredient_name: string; // for autocomplete
  ingredient_id: string | null;
  qty_needed: number;
  unit: string;
}

interface ParsedBelanja {
  name: string;
  qty: number;
  unit: string;
  price: number;
  subtotal: number;
}

/* ═══ Main TabBahan ════════════════════════════════════════════════════════ */

export function TabBahan() {
  const [products, setProducts] = useState<Product[]>([]);
  const [bahan, setBahan] = useState<Product[]>([]);
  const [menus, setMenus] = useState<Product[]>([]);
  const [components, setComponents] = useState<Component[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  /* ─── Belanja (Manual Input) ─────────────────────────────────────── */
  const [belanjaText, setBelanjaText] = useState("");
  const [parsedBelanja, setParsedBelanja] = useState<ParsedBelanja[]>([]);
  const [belanjaErrors, setBelanjaErrors] = useState<string[]>([]);
  const [paymentMethod, setPaymentMethod] = useState("tunai");
  
  // Set default due_date to 30 days from now
  const defaultDueDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split("T")[0];
  }, []);
  const [dueDate, setDueDate] = useState(defaultDueDate);

  /* ─── Component form (with inline ingredient rows) ───────────────── */
  const [showCompModal, setShowCompModal] = useState(false);
  const [editingCompId, setEditingCompId] = useState<string | null>(null);
  const [compForm, setCompForm] = useState({ name: "", description: "" });
  const [compFormItems, setCompFormItems] = useState<FormRowItem[]>([{ ingredient_name: "", ingredient_id: null, qty_needed: 0, unit: "" }]);

  /* ─── Menu BOM ───────────────────────────────────────────────────── */
  const [expandedMenu, setExpandedMenu] = useState<string | null>(null);
  const [menuRecipes, setMenuRecipes] = useState<Record<string, Recipe[]>>({});
  const [bomPreview, setBomPreview] = useState<Record<string, SimIngredient[]>>({});

  /* ─── Menu form (Integrated) ─────────────────────────────────────── */
  const [showMenuModal, setShowMenuModal] = useState(false);
  const [menuForm, setMenuForm] = useState({ name: "", unit: "porsi" });
  const [menuFormComps, setMenuFormComps] = useState<{ component_id: string }[]>([]);
  const [menuFormDirects, setMenuFormDirects] = useState<FormRowItem[]>([]);

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

  /* ═══ Helpers ═════════════════════════════════════════════════════════ */

  const getCompName = (compId: string) => components.find(c => c.id === compId)?.name || "?";
  const getIngName = (ingId: string) => products.find(p => p.id === ingId)?.name || "?";
  const getIngUnit = (ingId: string) => products.find(p => p.id === ingId)?.unit || "";

  // Helper: Find product by exact name (case insensitive)
  const findProductByName = (name: string): Product | undefined => {
    return products.find(p => p.name.toLowerCase().trim() === name.toLowerCase().trim());
  };

  // Helper: Create product if not exists
  const getOrCreateIngredient = async (name: string, unit: string): Promise<string> => {
    const existing = findProductByName(name);
    if (existing) return existing.id;
    // Create new
    const payload = { name: name.trim(), category: "bahan_baku", display_unit: unit || "kg", unit: unit || "kg", hpp: 0, sell_price: 0, stock_min: 0, stock_qty: 0 };
    const res = await apiPost("/products", payload);
    return res?.data?.id;
  };

  /* ═══ Belanja Parser Handlers ═════════════════════════════════════════ */

  useEffect(() => {
    if (!belanjaText.trim()) {
      setParsedBelanja([]);
      setBelanjaErrors([]);
      return;
    }
    const lines = belanjaText.split("\n").map(l => l.trim()).filter(l => l);
    const parsed: ParsedBelanja[] = [];
    const errs: string[] = [];

    lines.forEach(line => {
      // Format: nama qty satuan harga
      const parts = line.split(" ");
      if (parts.length < 4) {
        errs.push(`Format salah: "${line}" (butuh 4 kata)`);
        return;
      }
      const priceStr = parts.pop()!;
      const unitStr = parts.pop()!;
      const qtyStr = parts.pop()!;
      const nameStr = parts.join(" ");

      const qty = parseFloat(qtyStr.replace(/,/g, '.'));
      const price = parseFloat(priceStr.replace(/[^0-9.-]+/g, ""));

      if (isNaN(qty) || isNaN(price)) {
        errs.push(`Angka tidak valid: "${line}"`);
        return;
      }

      parsed.push({
        name: nameStr,
        qty,
        unit: unitStr.toLowerCase(),
        price,
        subtotal: qty * price
      });
    });
    setParsedBelanja(parsed);
    setBelanjaErrors(errs);
  }, [belanjaText]);

  const submitBelanja = async () => {
    if (parsedBelanja.length === 0 || saving) return;
    setSaving(true);
    try {
      const items = parsedBelanja.map(p => ({
        nama_item: p.name,
        qty: p.qty,
        satuan: p.unit,
        harga_satuan: p.price,
        subtotal: p.subtotal
      }));

      await apiPost("/transactions/manual", {
        supplier_name: "Input Manual Web",
        date: new Date().toISOString().split('T')[0],
        payment_method: paymentMethod,
        due_date: paymentMethod === "hutang" ? dueDate : null,
        items: items
      });

      setBelanjaText("");
      setParsedBelanja([]);
      setPaymentMethod("tunai");
      setDueDate(defaultDueDate);
      alert("✅ Belanja berhasil disimpan! Stok bertambah dan bahan baru telah dibuat otomatis.");
      await fetchAll();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Gagal menyimpan belanja");
    } finally {
      setSaving(false);
    }
  };

  /* ═══ Component Handlers ═════════════════════════════════════════════ */

  const openCompForm = (comp?: Component) => {
    if (comp) {
      setEditingCompId(comp.id);
      setCompForm({ name: comp.name, description: comp.description || "" });
      setCompFormItems(
        comp.items.length > 0
          ? comp.items.map(it => ({
            ingredient_id: it.ingredient_id,
            ingredient_name: it.product_name || getIngName(it.ingredient_id),
            qty_needed: it.qty_needed,
            unit: it.unit || ""
          }))
          : [{ ingredient_id: null, ingredient_name: "", qty_needed: 0, unit: "" }]
      );
    } else {
      setEditingCompId(null);
      setCompForm({ name: "", description: "" });
      setCompFormItems([{ ingredient_id: null, ingredient_name: "", qty_needed: 0, unit: "" }]);
    }
    setShowCompModal(true);
  };

  const updateCompRowName = (idx: number, val: string) => {
    setCompFormItems(prev => {
      const nw = [...prev];
      nw[idx].ingredient_name = val;
      const exist = findProductByName(val);
      if (exist) {
        nw[idx].ingredient_id = exist.id;
        nw[idx].unit = exist.unit;
      } else {
        nw[idx].ingredient_id = null;
      }
      return nw;
    });
  };

  const compFormValid = compForm.name.trim().length > 0
    && compFormItems.length > 0
    && compFormItems.every(r => r.ingredient_name.trim() && r.qty_needed > 0);

  const saveComp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (saving || !compFormValid) return;
    setSaving(true);
    try {
      let compId = editingCompId;

      if (editingCompId) {
        await apiPut(`/recipes/components/${editingCompId}`, compForm);
        const existing = components.find(c => c.id === editingCompId);
        if (existing) {
          for (const item of existing.items) {
            await apiDelete(`/recipes/components/${editingCompId}/items/${item.id}`);
          }
        }
      } else {
        const res = await apiPost("/recipes/components", compForm);
        compId = res?.data?.id;
        if (!compId) throw new Error("Gagal membuat komponen");
      }

      // Process items (auto-create ingredients if needed)
      for (const item of compFormItems) {
        if (item.ingredient_name.trim() && item.qty_needed > 0) {
          const actualIngId = await getOrCreateIngredient(item.ingredient_name, item.unit);
          await apiPost(`/recipes/components/${compId}/items`, {
            ingredient_id: actualIngId,
            qty_needed: item.qty_needed,
            unit: item.unit || undefined,
          });
        }
      }

      setShowCompModal(false);
      await fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menyimpan komponen"); }
    finally { setSaving(false); }
  };

  const deleteComp = async (id: string) => {
    if (!confirm("Hapus komponen ini?")) return;
    try { await apiDelete(`/recipes/components/${id}`); fetchAll(); }
    catch (err: any) { alert(err?.response?.data?.detail || "Gagal menghapus komponen"); }
  };

  /* ═══ Menu Handlers ══════════════════════════════════════════════════ */

  const toggleMenu = async (menuId: string) => {
    if (expandedMenu === menuId) { setExpandedMenu(null); return; }
    setExpandedMenu(menuId);
    await fetchMenuRecipes(menuId);
  };

  const deleteRecipe = async (recipeId: string, menuId: string) => {
    try { await apiDelete(`/recipes/${recipeId}`); await fetchMenuRecipes(menuId); } catch { alert("Gagal menghapus"); }
  };

  const openMenuForm = () => {
    setMenuForm({ name: "", unit: "porsi" });
    setMenuFormComps([]);
    setMenuFormDirects([{ ingredient_id: null, ingredient_name: "", qty_needed: 0, unit: "" }]);
    setShowMenuModal(true);
  };

  const updateMenuDirectRow = (idx: number, val: string) => {
    setMenuFormDirects(prev => {
      const nw = [...prev];
      nw[idx].ingredient_name = val;
      const exist = findProductByName(val);
      if (exist) {
        nw[idx].ingredient_id = exist.id;
        nw[idx].unit = exist.unit;
      } else {
        nw[idx].ingredient_id = null;
      }
      return nw;
    });
  };

  const menuFormValid = menuForm.name.trim().length > 0
    && (menuFormComps.length > 0 || menuFormDirects.some(r => r.ingredient_name.trim() && r.qty_needed > 0));

  const saveMenu = async (e: React.FormEvent) => {
    e.preventDefault();
    if (saving || !menuFormValid) return;
    setSaving(true);
    try {
      // 1. Create Menu Product
      const prodRes = await apiPost("/products", { ...menuForm, category: "produk_jadi", stock_qty: 0, hpp: 0, sell_price: 0, stock_min: 0 });
      const menuId = prodRes?.data?.id;
      if (!menuId) throw new Error("Gagal membuat menu");

      // 2. Attach Components
      for (const comp of menuFormComps) {
        if (comp.component_id) {
          await apiPost("/recipes/attach-component", { menu_id: menuId, component_id: comp.component_id });
        }
      }

      // 3. Attach Direct Ingredients
      for (const item of menuFormDirects) {
        if (item.ingredient_name.trim() && item.qty_needed > 0) {
          const actualIngId = await getOrCreateIngredient(item.ingredient_name, item.unit);
          await apiPost("/recipes", {
            menu_id: menuId, ingredient_id: actualIngId,
            qty_needed: item.qty_needed, unit: item.unit || "kg"
          });
        }
      }

      setShowMenuModal(false);
      await fetchAll();
    } catch (err: any) { alert(err?.response?.data?.detail || "Gagal menyimpan menu"); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="text-gray-500 py-8 text-center">Memuat data...</div>;

  /* ═══ JSX ════════════════════════════════════════════════════════════ */
  return (
    <div className="space-y-10">
      <datalist id="bahan-list">
        {bahan.map(b => <option key={b.id} value={b.name} />)}
      </datalist>

      {/* ═══════════════════ BAGIAN 1: BELANJA MANUAL ═══════════════════ */}
      <section>
        <div className="mb-4">
          <h2 className="text-2xl font-bold text-gray-900">🛒 Input Belanja Manual</h2>
          <p className="text-gray-500 text-sm mt-1">
            Jika tidak pakai Telegram, masukkan bahan dari nota di sini.<br />
            Format: <code className="bg-gray-100 px-1 rounded">nama qty satuan harga</code> per baris (contoh: <code className="bg-gray-100 px-1 rounded">Beras 10 kg 12000</code>). Bahan baru akan dibuat otomatis.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="flex flex-col gap-2">
            <textarea
              value={belanjaText}
              onChange={e => setBelanjaText(e.target.value)}
              placeholder="Telur 30 pcs 2000&#10;Minyak Goreng 2 liter 18000"
              className="w-full h-48 p-3 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-blue-500 outline-none"
            />
            {belanjaErrors.map((err, i) => (
              <p key={i} className="text-xs text-red-600">⚠️ {err}</p>
            ))}
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border flex flex-col">
            <h4 className="font-semibold text-gray-700 mb-3 text-sm">Preview Item:</h4>
            {parsedBelanja.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
                Belum ada item valid.
              </div>
            ) : (
              <div className="overflow-y-auto max-h-40 flex-1">
                <table className="w-full text-sm text-left">
                  <thead>
                    <tr className="border-b">
                      <th className="pb-1 text-gray-500 font-medium">Item</th>
                      <th className="pb-1 text-gray-500 font-medium text-right">Harga</th>
                      <th className="pb-1 text-gray-500 font-medium text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {parsedBelanja.map((p, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="py-2">
                          <div className="font-medium text-gray-900">{p.name}</div>
                          <div className="text-xs text-gray-500">{p.qty} {p.unit}</div>
                        </td>
                        <td className="py-2 text-right text-gray-600"><Rupiah amount={p.price} /></td>
                        <td className="py-2 text-right font-medium text-gray-900"><Rupiah amount={p.subtotal} /></td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr>
                      <td colSpan={2} className="pt-2 font-bold text-right">TOTAL:</td>
                      <td className="pt-2 font-bold text-right text-blue-700">
                        <Rupiah amount={parsedBelanja.reduce((sum, p) => sum + p.subtotal, 0)} />
                      </td>
                    </tr>
              </tfoot>
            </table>
          </div>
        )}

        {/* Payment Method Selector */}
        <div className="mt-4 p-3 bg-white border rounded-lg shadow-sm">
            <label className="block text-sm font-medium text-gray-700 mb-1">Metode Pembayaran</label>
            <select 
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500"
            >
              <option value="tunai">Tunai</option>
              <option value="transfer">Transfer</option>
              <option value="hutang">Hutang (Tempo)</option>
            </select>
            
            {paymentMethod === "hutang" && (
              <div className="mt-3">
                <label className="block text-sm font-medium text-gray-700 mb-1">Jatuh Tempo</label>
                <input 
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-gray-50 focus:bg-white focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
        </div>

        <button
              disabled={parsedBelanja.length === 0 || saving}
              onClick={submitBelanja}
              className="w-full mt-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium transition-colors"
            >
              {saving ? "Menyimpan..." : `Simpan ${parsedBelanja.length} Item ke Stok`}
            </button>
          </div>
        </div>
      </section>

      <hr className="border-gray-200" />

      {/* ═══════════════════ BAGIAN 2: KOMPONEN ═════════════════════════ */}
      <section>
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">🧩 Komponen Resep (Reusable)</h2>
            <p className="text-gray-500 text-sm mt-1">Buat komponen resep sekali, bisa dipakai di banyak menu.</p>
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
                    <h3 className="font-bold text-gray-900 text-lg">🧩 {comp.name}</h3>
                    {comp.description && <p className="text-gray-500 text-sm">{comp.description}</p>}
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => openCompForm(comp)} className="text-blue-600 hover:text-blue-800 px-2 py-1 bg-blue-50 rounded text-xs font-medium">✏️ Edit</button>
                    <button onClick={() => deleteComp(comp.id)} className="text-red-600 hover:text-red-800 px-2 py-1 bg-red-50 rounded text-xs font-medium">🗑️ Hapus</button>
                  </div>
                </div>

                <div className="space-y-1">
                  {comp.items.length === 0 ? (
                    <p className="text-gray-400 text-sm italic">Belum ada bahan</p>
                  ) : (
                    comp.items.map(item => (
                      <div key={item.id} className="text-sm bg-gray-50 px-3 py-1.5 rounded text-gray-700">
                        • {item.product_name || getIngName(item.ingredient_id)} — <span className="text-gray-500">{item.qty_needed} {item.unit}</span>
                      </div>
                    ))
                  )}
                </div>
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
            <p className="text-gray-500 text-sm mt-1">Setiap menu adalah tabel Bill of Material. Otomatis potong stok saat dibuat.</p>
          </div>
          <button onClick={openMenuForm} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-medium text-sm">+ Menu Baru</button>
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
                      {compRecipes.length} komponen, {directRecipes.length} bahan
                    </span>
                  </button>

                  {isOpen && (
                    <div className="px-5 pb-5 border-t bg-gray-50/50 space-y-4 pt-4">

                      {/* Komponen attached */}
                      <div>
                        <h4 className="font-semibold text-gray-700 mb-2 text-sm">🧩 Komponen:</h4>
                        {compRecipes.length === 0
                          ? <p className="text-gray-400 text-sm italic">Belum ada komponen terpasang</p>
                          : <div className="space-y-1">{compRecipes.map(r => (
                              <div key={r.id} className="flex justify-between items-center bg-purple-50 px-3 py-2 rounded text-sm">
                                <span className="text-purple-800">🧩 {getCompName(r.component_id!)}</span>
                                <button onClick={() => deleteRecipe(r.id, menu.id)} className="text-red-400 hover:text-red-600 text-xs">🗑️</button>
                              </div>
                            ))}</div>}
                      </div>

                      {/* Direct ingredients */}
                      <div>
                        <h4 className="font-semibold text-gray-700 mb-2 text-sm">🧪 Bahan Baku Langsung:</h4>
                        {directRecipes.length === 0
                          ? <p className="text-gray-400 text-sm italic">Belum ada bahan baku langsung</p>
                          : <div className="space-y-1">{directRecipes.map(r => (
                              <div key={r.id} className="flex justify-between items-center bg-green-50 px-3 py-2 rounded text-sm">
                                <span className="text-green-800">• {getIngName(r.ingredient_id!)} <span className="text-green-600">{r.qty_needed} {r.unit}</span></span>
                                <button onClick={() => deleteRecipe(r.id, menu.id)} className="text-red-400 hover:text-red-600 text-xs">🗑️</button>
                              </div>
                            ))}</div>}
                      </div>

                      {/* BOM Preview */}
                      <div className="pt-2 border-t border-gray-200">
                        <button onClick={() => fetchBomPreview(menu.id)} className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 transition-colors">
                          👁️ Lihat Total Bahan Asli (BOM Preview)
                        </button>
                        {preview && (
                          <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <h4 className="font-bold text-blue-800 mb-2 text-sm">📋 Total Kebutuhan Bahan per 1 {menu.unit}:</h4>
                            {preview.length === 0
                              ? <p className="text-gray-500 text-sm">Tidak ada bahan terhubung (BOM kosong)</p>
                              : <table className="w-full text-sm">
                                  <thead><tr className="text-left text-blue-700 border-b border-blue-200">
                                    <th className="py-1 pr-4">Bahan Asli</th><th className="py-1 pr-4">Kebutuhan</th><th className="py-1 pr-4">Stok Gudang</th><th className="py-1">Status Produksi</th>
                                  </tr></thead>
                                  <tbody>{preview.map((ing, i) => (
                                    <tr key={i} className="border-b border-blue-100">
                                      <td className="py-1.5 pr-4 font-medium text-gray-800">{ing.name}</td>
                                      <td className="py-1.5 pr-4 text-gray-600">{ing.total_needed} {ing.unit}</td>
                                      <td className="py-1.5 pr-4 text-gray-600">{ing.available} {ing.unit}</td>
                                      <td className="py-1.5">{ing.sufficient
                                        ? <span className="text-green-600 font-medium">✅ Aman</span>
                                        : <span className="text-red-600 font-medium">❌ Kurang {ing.shortage}</span>}</td>
                                    </tr>
                                  ))}</tbody>
                                </table>}
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

      {/* ── Modal: Komponen ───────────────────────────────────────────── */}
      {showCompModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <form onSubmit={saveComp}>
              <div className="p-6 space-y-4">
                <h3 className="text-xl font-bold">{editingCompId ? "Edit" : "Buat"} Komponen Resep</h3>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Nama Komponen</label>
                  <input required autoFocus type="text" placeholder="mis: Nasi Putih, Bumbu Halus" value={compForm.name} onChange={e => setCompForm({ ...compForm, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Deskripsi (opsional)</label>
                  <input type="text" placeholder="Keterangan singkat" value={compForm.description} onChange={e => setCompForm({ ...compForm, description: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                </div>

                <div className="pt-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Resep Komponen ini:</label>
                  <div className="bg-gray-50 border rounded-lg p-3">
                    <div className="flex text-xs font-semibold text-gray-500 mb-2 px-1">
                      <div className="flex-1">Nama Bahan Baku</div>
                      <div className="w-20">Qty</div>
                      <div className="w-16">Satuan</div>
                      <div className="w-6"></div>
                    </div>
                    <div className="space-y-2">
                      {compFormItems.map((row, idx) => (
                        <div key={idx} className="flex gap-2 items-start">
                          <input required type="text" list="bahan-list" placeholder="Pilih / ketik bahan..."
                            value={row.ingredient_name} onChange={e => updateCompRowName(idx, e.target.value)}
                            className="flex-1 px-2 py-1.5 border rounded text-sm bg-white" />
                          <input required type="number" step="0.001" min="0" placeholder="Qty" value={row.qty_needed || ""}
                            onChange={e => setCompFormItems(prev => prev.map((r, i) => i === idx ? { ...r, qty_needed: parseFloat(e.target.value) || 0 } : r))}
                            className="w-20 px-2 py-1.5 border rounded text-sm" />
                          <input required type="text" placeholder="Satuan" value={row.unit}
                            onChange={e => setCompFormItems(prev => prev.map((r, i) => i === idx ? { ...r, unit: e.target.value } : r))}
                            className="w-16 px-2 py-1.5 border rounded text-sm" />
                          <button type="button" onClick={() => setCompFormItems(prev => prev.filter((_, i) => i !== idx))}
                            disabled={compFormItems.length <= 1} className="text-gray-400 hover:text-red-500 text-lg disabled:opacity-30 pt-1">✕</button>
                        </div>
                      ))}
                    </div>
                    <button type="button" onClick={() => setCompFormItems(prev => [...prev, { ingredient_name: "", ingredient_id: null, qty_needed: 0, unit: "" }])}
                      className="text-purple-600 hover:text-purple-800 text-sm font-medium mt-3 block">+ Tambah Bahan</button>
                  </div>
                  <p className="text-xs text-gray-400 mt-2">💡 Jika nama bahan diketik manual dan belum terdaftar di master data, sistem akan otomatis mendaftarkannya.</p>
                </div>
              </div>

              <div className="p-4 border-t flex gap-2 justify-end sticky bottom-0 bg-white">
                <button type="button" onClick={() => setShowCompModal(false)} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" disabled={saving || !compFormValid} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium disabled:opacity-50">
                  {saving ? "Menyimpan..." : "Simpan Komponen"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Menu Baru (Integrated) ─────────────────────────────── */}
      {showMenuModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-xl max-h-[90vh] overflow-y-auto">
            <form onSubmit={saveMenu}>
              <div className="p-6 space-y-5">
                <h3 className="text-xl font-bold">Menu BOM Baru</h3>
                
                <div className="grid grid-cols-3 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Nama Menu</label>
                    <input required autoFocus type="text" placeholder="Bistik Sapi Mentega" value={menuForm.name} onChange={e => setMenuForm({ ...menuForm, name: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Satuan Produk</label>
                    <input required type="text" value={menuForm.unit} onChange={e => setMenuForm({ ...menuForm, unit: e.target.value })} className="w-full px-4 py-2 border rounded-lg" />
                  </div>
                </div>

                {/* Komponen Input */}
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <span>🧩 Komponen</span>
                  </label>
                  <div className="bg-purple-50/50 border border-purple-100 rounded-lg p-3">
                    <div className="space-y-2">
                      {menuFormComps.map((row, idx) => (
                        <div key={idx} className="flex gap-2 items-center">
                          <select required value={row.component_id} onChange={e => setMenuFormComps(prev => prev.map((r, i) => i===idx ? {component_id: e.target.value} : r))} className="flex-1 px-3 py-1.5 border rounded-lg text-sm bg-white">
                            <option value="">Pilih komponen resep...</option>
                            {components.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                          </select>
                          <button type="button" onClick={() => setMenuFormComps(prev => prev.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-500 text-lg">✕</button>
                        </div>
                      ))}
                    </div>
                    <button type="button" onClick={() => setMenuFormComps(prev => [...prev, { component_id: "" }])} className="text-purple-600 hover:text-purple-800 text-sm font-medium mt-2">+ Pasang Komponen</button>
                  </div>
                </div>

                {/* Direct Ingredients Input */}
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                    <span>🧪 Bahan Baku Langsung</span>
                  </label>
                  <div className="bg-green-50/50 border border-green-100 rounded-lg p-3">
                    <div className="flex text-xs font-semibold text-gray-500 mb-2 px-1">
                      <div className="flex-1">Nama Bahan Asli</div>
                      <div className="w-20">Qty</div>
                      <div className="w-16">Satuan</div>
                      <div className="w-6"></div>
                    </div>
                    <div className="space-y-2">
                      {menuFormDirects.map((row, idx) => (
                        <div key={idx} className="flex gap-2 items-start">
                          <input type="text" list="bahan-list" placeholder="Pilih / ketik bahan..."
                            value={row.ingredient_name} onChange={e => updateMenuDirectRow(idx, e.target.value)}
                            className="flex-1 px-2 py-1.5 border rounded text-sm bg-white" />
                          <input type="number" step="0.001" min="0" placeholder="Qty" value={row.qty_needed || ""}
                            onChange={e => setMenuFormDirects(prev => prev.map((r, i) => i === idx ? { ...r, qty_needed: parseFloat(e.target.value) || 0 } : r))}
                            className="w-20 px-2 py-1.5 border rounded text-sm" />
                          <input type="text" placeholder="Satuan" value={row.unit}
                            onChange={e => setMenuFormDirects(prev => prev.map((r, i) => i === idx ? { ...r, unit: e.target.value } : r))}
                            className="w-16 px-2 py-1.5 border rounded text-sm" />
                          <button type="button" onClick={() => setMenuFormDirects(prev => prev.filter((_, i) => i !== idx))}
                            className="text-gray-400 hover:text-red-500 text-lg pt-1">✕</button>
                        </div>
                      ))}
                    </div>
                    <button type="button" onClick={() => setMenuFormDirects(prev => [...prev, { ingredient_name: "", ingredient_id: null, qty_needed: 0, unit: "" }])}
                      className="text-green-600 hover:text-green-800 text-sm font-medium mt-3">+ Tambah Bahan Langsung</button>
                  </div>
                </div>

              </div>
              <div className="p-4 border-t flex gap-2 justify-end sticky bottom-0 bg-white shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                <button type="button" onClick={() => setShowMenuModal(false)} className="px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50 font-medium">Batal</button>
                <button type="submit" disabled={saving || !menuFormValid} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 font-medium disabled:opacity-50">
                  {saving ? "Menyimpan BOM..." : "Simpan Menu & Resep"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
