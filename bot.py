import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "")
DATA_FILE = "data.json"

def load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "cobros": [],
        "gastos_pagados": [],
        "gastos_fijos": {
            "tarjeta": 500000,
            "monotributo": 48800,
            "expensas": 150000,
            "abl": 6950,
            "claro": 22000,
            "papa_envio": 65000,
            "papa_cond": 18000,
            "difex": 150000,
            "comida": 200000,
            "cp_viaje": 215000
        }
    }

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fmt(n):
    return f"${int(n):,}".replace(",", ".")

def total_cobrado(data):
    return sum(c["monto"] for c in data["cobros"])

def total_pagado(data):
    gf = data["gastos_fijos"]
    pagados = data["gastos_pagados"]
    return sum(gf[g] for g in pagados if g in gf)

def total_gastos(data):
    return sum(data["gastos_fijos"].values())

def saldo_ahora(data):
    return total_cobrado(data) - total_pagado(data)

def saldo_proyectado(data):
    return total_cobrado(data) - total_gastos(data)

TECLADO = ReplyKeyboardMarkup([
    ["💰 Cobré algo", "✅ Pagué algo"],
    ["📊 ¿Cuánto tengo?", "📋 Ver cobros"],
    ["📤 Ver gastos", "✏️ Corregir monto"],
    ["↩️ Desmarcar pago", "🔄 Nuevo mes"]
], resize_keyboard=True)

user_state = {}

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Hola Oscarelys!* Soy tu bot de presupuesto.\n\nUsá los botones de abajo 👇",
        parse_mode="Markdown",
        reply_markup=TECLADO
    )

async def cuanto_tengo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    cobrado  = total_cobrado(data)
    pagado   = total_pagado(data)
    falta    = total_gastos(data) - pagado
    ahora    = saldo_ahora(data)
    proyect  = saldo_proyectado(data)
    n_pagados= len(data["gastos_pagados"])
    n_total  = len(data["gastos_fijos"])
    msg = (
        f"📊 *Tu situación ahora mismo*\n\n"
        f"💰 Total cobrado: *{fmt(cobrado)}*\n"
        f"✅ Gastos pagados: *{fmt(pagado)}* ({n_pagados}/{n_total})\n"
        f"─────────────────\n"
        f"💵 *En mano ahora: {fmt(ahora)}*\n\n"
        f"⏳ Gastos que faltan: *{fmt(falta)}*\n"
        f"📈 Proyección al cerrar mes: *{fmt(proyect)}*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO)

async def ver_cobros(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    if not data["cobros"]:
        await update.message.reply_text("Todavía no cargaste ningún cobro este mes.", reply_markup=TECLADO)
        return
    lines = ["💰 *Cobros del mes:*\n"]
    acum = 0
    for c in data["cobros"]:
        acum += c["monto"]
        lines.append(f"• {c.get('fecha','—')} — {c['nombre']}: *{fmt(c['monto'])}*")
    lines.append(f"\n*Total: {fmt(acum)}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=TECLADO)

async def ver_gastos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = load()
    gf = data["gastos_fijos"]
    pagados = data["gastos_pagados"]
    lines = ["📤 *Gastos del mes:*\n"]
    for nombre, monto in gf.items():
        icono = "✅" if nombre in pagados else "⭕"
        lines.append(f"{icono} {nombre.replace('_',' ').title()}: *{fmt(monto)}*")
    lines.append(f"\n*Total: {fmt(sum(gf.values()))}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=TECLADO)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid  = update.effective_user.id
    data = load()
    gf   = data["gastos_fijos"]
    pagados = data["gastos_pagados"]

    # ── Botón: Cobré algo ──
    if text == "💰 Cobré algo":
        user_state[uid] = "esperando_cobro"
        await update.message.reply_text(
            "💰 ¿Cuánto cobraste y de quién?\n\n"
            "Escribí: *monto nombre*\n"
            "Ejemplo: `150000 Cliente A`\n"
            "o solo: `150000`",
            parse_mode="Markdown"
        )
        return

    # ── Botón: Pagué algo ──
    if text == "✅ Pagué algo":
        user_state[uid] = "esperando_gasto"
        lines = ["✅ *¿Qué pagaste?* Escribí el número:\n"]
        opciones = []
        for i, (nombre, monto) in enumerate(gf.items(), 1):
            icono = "✅" if nombre in pagados else "⭕"
            lines.append(f"{i}. {icono} {nombre.replace('_',' ').title()} — {fmt(monto)}")
            opciones.append(nombre)
        ctx.user_data["opciones_gasto"] = opciones
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ── Botón: Corregir monto ──
    if text == "✏️ Corregir monto":
        user_state[uid] = "esperando_correccion_item"
        lines = ["✏️ *¿Qué monto querés corregir?* Escribí el número:\n"]
        opciones = []
        for i, (nombre, monto) in enumerate(gf.items(), 1):
            lines.append(f"{i}. {nombre.replace('_',' ').title()} — {fmt(monto)}")
            opciones.append(nombre)
        ctx.user_data["opciones_correccion"] = opciones
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ── Botón: Desmarcar pago ──
    if text == "↩️ Desmarcar pago":
        if not pagados:
            await update.message.reply_text("No hay pagos marcados para desmarcar.", reply_markup=TECLADO)
            return
        user_state[uid] = "esperando_desmarcar"
        lines = ["↩️ *¿Cuál querés desmarcar?* Escribí el número:\n"]
        opciones = []
        for i, nombre in enumerate(pagados, 1):
            monto = gf.get(nombre, 0)
            lines.append(f"{i}. {nombre.replace('_',' ').title()} — {fmt(monto)}")
            opciones.append(nombre)
        ctx.user_data["opciones_desmarcar"] = opciones
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # ── Botones simples ──
    if text == "📊 ¿Cuánto tengo?":
        await cuanto_tengo(update, ctx); return
    if text == "📋 Ver cobros":
        await ver_cobros(update, ctx); return
    if text == "📤 Ver gastos":
        await ver_gastos(update, ctx); return
    if text == "🔄 Nuevo mes":
        data["cobros"] = []
        data["gastos_pagados"] = []
        save(data)
        await update.message.reply_text("🔄 *Nuevo mes iniciado!*\nCobros y pagos reiniciados.", parse_mode="Markdown", reply_markup=TECLADO)
        return

    # ── Estado: esperando cobro ──
    if user_state.get(uid) == "esperando_cobro":
        parts = text.split(None, 1)
        try:
            monto = float(parts[0].replace(".", "").replace(",", "."))
            nombre = parts[1] if len(parts) > 1 else "Cobro"
            fecha = datetime.now().strftime("%d/%m")
            data["cobros"].append({"nombre": nombre, "monto": monto, "fecha": fecha})
            save(data)
            user_state[uid] = None
            await update.message.reply_text(
                f"✅ *Cobro registrado!*\n• {nombre}: *{fmt(monto)}*\n\n💵 En mano ahora: *{fmt(saldo_ahora(data))}*",
                parse_mode="Markdown", reply_markup=TECLADO
            )
        except:
            await update.message.reply_text("No entendí. Escribí así: `150000 Cliente A`", parse_mode="Markdown")
        return

    # ── Estado: esperando gasto ──
    if user_state.get(uid) == "esperando_gasto":
        opciones = ctx.user_data.get("opciones_gasto", [])
        try:
            idx = int(text) - 1
            if 0 <= idx < len(opciones):
                gasto = opciones[idx]
                if gasto not in data["gastos_pagados"]:
                    data["gastos_pagados"].append(gasto)
                    save(data)
                monto = gf[gasto]
                user_state[uid] = None
                await update.message.reply_text(
                    f"✅ *{gasto.replace('_',' ').title()} marcado como pagado!*\n"
                    f"• Monto: *{fmt(monto)}*\n\n💵 En mano ahora: *{fmt(saldo_ahora(data))}*",
                    parse_mode="Markdown", reply_markup=TECLADO
                )
            else:
                await update.message.reply_text("Número inválido, intentá de nuevo.")
        except:
            await update.message.reply_text("Escribí el número de la lista, por ejemplo: `3`", parse_mode="Markdown")
        return

    # ── Estado: corregir item ──
    if user_state.get(uid) == "esperando_correccion_item":
        opciones = ctx.user_data.get("opciones_correccion", [])
        try:
            idx = int(text) - 1
            if 0 <= idx < len(opciones):
                ctx.user_data["item_a_corregir"] = opciones[idx]
                user_state[uid] = "esperando_correccion_monto"
                nombre = opciones[idx].replace('_',' ').title()
                monto_actual = gf[opciones[idx]]
                await update.message.reply_text(
                    f"✏️ *{nombre}*\nMonto actual: *{fmt(monto_actual)}*\n\nEscribí el nuevo monto:",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("Número inválido, intentá de nuevo.")
        except:
            await update.message.reply_text("Escribí el número de la lista.")
        return

    # ── Estado: corregir monto ──
    if user_state.get(uid) == "esperando_correccion_monto":
        item = ctx.user_data.get("item_a_corregir")
        try:
            nuevo_monto = float(text.replace(".", "").replace(",", "."))
            data["gastos_fijos"][item] = nuevo_monto
            save(data)
            user_state[uid] = None
            await update.message.reply_text(
                f"✅ *{item.replace('_',' ').title()}* actualizado a *{fmt(nuevo_monto)}*",
                parse_mode="Markdown", reply_markup=TECLADO
            )
        except:
            await update.message.reply_text("No entendí el monto. Escribí solo números, por ejemplo: `17305`", parse_mode="Markdown")
        return

    # ── Estado: desmarcar ──
    if user_state.get(uid) == "esperando_desmarcar":
        opciones = ctx.user_data.get("opciones_desmarcar", [])
        try:
            idx = int(text) - 1
            if 0 <= idx < len(opciones):
                gasto = opciones[idx]
                data["gastos_pagados"].remove(gasto)
                save(data)
                user_state[uid] = None
                await update.message.reply_text(
                    f"↩️ *{gasto.replace('_',' ').title()}* desmarcado.\n\n💵 En mano ahora: *{fmt(saldo_ahora(data))}*",
                    parse_mode="Markdown", reply_markup=TECLADO
                )
            else:
                await update.message.reply_text("Número inválido.")
        except:
            await update.message.reply_text("Escribí el número de la lista.")
        return

    await update.message.reply_text("Usá los botones de abajo 👇", reply_markup=TECLADO)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()

