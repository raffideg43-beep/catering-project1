import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from services.api_client import api_client
from keyboards.main_menu import get_back_button
from .security import requires_role

logger = logging.getLogger(__name__)

async def render_driver_trip(update: Update, context: ContextTypes.DEFAULT_TYPE, message_id: Optional[int] = None):
    token = context.user_data.get("token")
    if not token:
        return
    
    # Ambil data deliveries hari ini
    resp = await api_client.get("/mbg/deliveries/summary", token=token)
    data = resp.get("data", {})
    has_delivery = data.get("has_delivery", False)
    deliveries = data.get("deliveries", [])
    
    text_lines = [
        "🚚 *Daftar Pengiriman MBG Hari Ini*",
        f"📅 Tanggal: {data.get('date')}\n"
    ]
    
    keyboard = []
    
    if not has_delivery:
        text_lines.append("⚠️ *Belum ada surat jalan dari Dapur.*")
        text_lines.append("Silakan admin klik /serah terlebih dahulu untuk memproses stok dapur.")
    else:
        text_lines.append("Berikut adalah daftar sekolah yang siap diantar:")
        text_lines.append("")
        
        for d in deliveries:
            sid = d.get("id")
            sname = d.get("school_name")
            porsi = d.get("portions_sent")
            status = d.get("status")
            sent = d.get("sent_time")
            arrive = d.get("arrival_time")
            dist = d.get("distance_km", 0)
            
            # Formatting status text & buttons
            if not sent:
                status_icon = "⏳"
                status_text = "Menunggu Berangkat"
                if sid:
                    keyboard.append([InlineKeyboardButton(f"🚀 Berangkat - {sname}", callback_data=f"dr_depart_{sid}")])
            elif sent and not arrive:
                status_icon = "🚚"
                # Target = dist * 3 menit
                import datetime
                try:
                    s_dt = datetime.datetime.strptime(sent, "%H:%M:%S")
                    t_dt = s_dt + datetime.timedelta(minutes=dist * 3)
                    target = t_dt.strftime("%H:%M")
                except:
                    target = "?"
                status_text = f"Dalam Perjalanan (Target Tiba: {target})"
                if sid:
                    keyboard.append([InlineKeyboardButton(f"✅ Selesai (Tiba di {sname})", callback_data=f"dr_arrive_{sid}")])
            else:
                status_icon = "✅"
                status_text = f"Tiba di lokasi jam {arrive}"
            
            text_lines.append(f"{status_icon} *{sname}* ({porsi} porsi)")
            text_lines.append(f"└ Status: {status_text}")
            text_lines.append("")

    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="driver_trip")])
    keyboard.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_main")])
    
    final_text = "\n".join(text_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(final_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(final_text, reply_markup=reply_markup, parse_mode="Markdown")


@requires_role(["driver", "owner", "admin"])
async def driver_trip_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /perjalanan or Main Menu driver trip"""
    query = update.callback_query
    if query:
        await query.answer()
    
    await render_driver_trip(update, context)

@requires_role(["driver", "owner", "admin"])
async def driver_depart_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Memproses keberangkatan...")
    
    delivery_id = query.data.split("_")[2]
    token = context.user_data.get("token")
    
    try:
        await api_client.post(f"/mbg/deliveries/driver/depart/{delivery_id}", payload={}, token=token)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal berangakat: {e}")
        return
        
    await render_driver_trip(update, context)

@requires_role(["driver", "owner", "admin"])
async def driver_arrive_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Memproses ketibaan...")
    
    delivery_id = query.data.split("_")[2]
    token = context.user_data.get("token")
    
    try:
        await api_client.post(f"/mbg/deliveries/driver/arrive/{delivery_id}", payload={}, token=token)
    except Exception as e:
        await query.message.reply_text(f"❌ Gagal tiba: {e}")
        return
        
    await render_driver_trip(update, context)
