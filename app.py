import os
import re
import requests
import random
import json
import argparse
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime, timedelta, time
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from functools import wraps



ADMIN_CHAT_ID = 00000000

# Variables para gestionar recordatorios
# Archivo para persistir recordatorios
REMINDERS_FILE = "reminders.json"
MAX_REMINDERS = 15

# Variables para gestionar recordatorios en memoria
REMINDER_COUNTER = 0
REMINDERS = {}  # mapping id -> Job
# --- Handlers existentes ---

# --- Funciones auxiliares de persistencia ---
def load_reminders(app):
    print(GO_CARDLESS_TOKEN)
    """
    Carga recordatorios desde REMINDERS_FILE y los programa.
    """
    global REMINDER_COUNTER, REMINDERS
    if not os.path.exists(REMINDERS_FILE):
        return
    try:
        with open(REMINDERS_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return

    now = datetime.now()
    for item in data:
        rid = item.get("id")
        chat_id = item.get("chat_id")
        dt_str = item.get("datetime")
        mensaje = item.get("message")
        try:
            run_at = datetime.fromisoformat(dt_str)
            # Normalizar a datetime naive (local)
            if run_at.tzinfo is not None:
                run_at = run_at.astimezone().replace(tzinfo=None)
        except Exception:
            continue
        # Solo reprogramar futuros
        if run_at <= now:
            continue
        delta = (run_at - now).total_seconds()
        job = app.job_queue.run_once(
            alarm_callback,
            when=delta,
            chat_id=chat_id,
            data=mensaje,
            name=f"recordatorio_{chat_id}_{int(run_at.timestamp())}"
        )
        REMINDERS[rid] = job
        REMINDER_COUNTER = max(REMINDER_COUNTER, rid)


def save_reminders():
    """
    Guarda en REMINDERS_FILE la lista actual de recordatorios.
    """
    items = []
    for rid, job in REMINDERS.items():
        run_at = job.next_t
        # Normalizar a datetime naive antes de guardar
        if run_at.tzinfo is not None:
            run_at = run_at.astimezone().replace(tzinfo=None)
        items.append({
            "id": rid,
            "chat_id": job.chat_id,
            "datetime": run_at.isoformat(),
            "message": job.data
        })
    try:
        with open(REMINDERS_FILE, "w") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def require_mention(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_type = update.effective_chat.type
        text = update.message.text or ""
        bot_username = context.bot.username

        # En grupo/ supergrupo, exige mención
        if chat_type in ("group", "supergroup"):
            if f"@{bot_username}" not in text:
                return  # ignora sin mención

        # En privado (o si pasa la mención), ejecuta normalmente
        return await func(update, context)

    return wrapper
def check_rate_limit(resp):
    """
    Si resp.status_code == 429, extrae de resp.json()['detail'] o del header Retry-After
    los segundos que faltan y devuelve una cadena formateada en días, horas, minutos, segundos.
    En otro caso devuelve None.
    """
    if resp.status_code != 429:
        return None

    # Intentamos extraer segundos de la clave "detail"
    try:
        detail = resp.json().get("detail", "")
        m = re.search(r"(\d+)\s*seconds", detail)
        seconds = int(m.group(1)) if m else int(resp.headers.get("Retry-After", 0))
    except Exception:
        seconds = int(resp.headers.get("Retry-After", 0))

    # Convertir segundos a d/h/m/s
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days} día{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
    if secs:
        parts.append(f"{secs} segundo{'s' if secs != 1 else ''}")
    if not parts:
        parts.append("menos de un segundo")

    # Unimos con comas y 'y' antes del último
    if len(parts) > 1:
        return ", ".join(parts[:-1]) + " y " + parts[-1]
    return parts[0]

@require_mention
async def hola(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("¡Hola! ¿En qué puedo ayudarte? 🤖")

async def fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    await update.message.reply_text(f"La fecha y hora actual es: {ahora}")

@require_mention
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    resp = requests.get(BALANCES_URL, headers=HEADERS)
    # 1) ¿Rate limit?
    wait = check_rate_limit(resp)
    if wait:
        return await update.message.reply_text(
            f"⚠️ Límite de peticiones excedido. Vuelve a intentarlo en {wait}."
        )

    # 2) Si no, seguimos con la lógica normal
    try:
        resp.raise_for_status()
        balances = resp.json().get("balances", [])
        if not balances:
            texto = "No se encontró información de saldo."
        else:
            lines = ["💰 *Saldos disponibles:*"]
            for bal in balances:
                tipo  = bal.get("balanceType", "desconocido")
                amt   = bal.get("balanceAmount", {}).get("amount", "N/A")
                curr  = bal.get("balanceAmount", {}).get("currency", "EUR")
                fecha = bal.get("referenceDate", "")
                lines.append(f"• _{tipo}_: {amt} {curr} (ref: {fecha})")
            texto = "\n".join(lines)
    except Exception as e:
        texto = f"⚠️ Error al obtener el saldo: {e}"
    await update.message.reply_text(texto, parse_mode="Markdown")

@require_mention
async def iban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    resp = requests.get(DETAILS_URL, headers=HEADERS)
    wait = check_rate_limit(resp)
    if wait:
        return await update.message.reply_text(
            f"⚠️ Límite de peticiones excedido. Vuelve a intentarlo en {wait}."
        )

    try:
        resp.raise_for_status()
        acct = resp.json().get("account", {})
        texto = (
            "🏦 *Detalles de la cuenta:*\n"
            f"• _IBAN_: `{acct.get('iban','N/A')}`\n"
            f"• _BIC_: `{acct.get('bic','N/A')}`\n"
            f"• _Titular_: {acct.get('ownerName','N/A')}\n"
            f"• _Moneda_: {acct.get('currency','EUR')}\n"
            f"• _Estado_: {acct.get('status','')}"
        )
    except Exception as e:
        texto = f"⚠️ Error al obtener el IBAN: {e}"
    await update.message.reply_text(texto, parse_mode="Markdown")

@require_mention
async def transacciones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    resp = requests.get(TRANSACTIONS_URL, headers=HEADERS)
    wait = check_rate_limit(resp)
    if wait:
        return await update.message.reply_text(
            f"⚠️ Límite de peticiones excedido. Vuelve a intentarlo en {wait}."
        )

    try:
        resp.raise_for_status()
        txs = resp.json().get("transactions", {}).get("booked", [])
        if not txs:
            texto = "No hay transacciones recientes."
        else:
            ultimas = txs[:6]
            lines = ["🧾 *Últimas 6 transacciones:*"]
            for tx in ultimas:
                date    = tx.get("bookingDate","")
                amt     = tx.get("transactionAmount",{}).get("amount","N/A")
                curr    = tx.get("transactionAmount",{}).get("currency","EUR")
                contra  = tx.get("creditorName") or tx.get("debtorName") or "—"
                info    = tx.get("remittanceInformationUnstructuredArray", [])
                concepto= "; ".join(info) if info else "—"
                sign    = "" if amt.startswith("-") else "+"
                lines.append(f"• {date}: {sign}{amt} {curr} — {contra} ({concepto})")
            texto = "\n".join(lines)
    except Exception as e:
        texto = f"⚠️ Error al obtener transacciones: {e}"
    await update.message.reply_text(texto, parse_mode="Markdown")

# --- Comando /putoAntonio ---
@require_mention
async def putoAntonio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hoy = datetime.today()
    if hoy.month > 1:
        primer_mes_anterior = hoy.replace(month=hoy.month-1, day=1)
    else:
        primer_mes_anterior = hoy.replace(year=hoy.year-1, month=12, day=1)
    params = {
        "date_from": primer_mes_anterior.strftime("%Y-%m-%d"),
        "date_to": hoy.strftime("%Y-%m-%d")
    }
    resp = requests.get(TRANSACTIONS_URL, headers=HEADERS, params=params)
    wait = check_rate_limit(resp)
    if wait:
        return await update.message.reply_text(
            f"⚠️ Límite de peticiones excedido. Vuelve a intentarlo en {wait}."
        )
    try:
        resp.raise_for_status()
        txs = resp.json().get("transactions", {}).get("booked", [])
        candidatos = [
            tx for tx in txs
            if float(tx.get("transactionAmount",{}).get("amount","0")) == -800.0
        ]
        if not candidatos:
            texto = "No se encontró ninguna transferencia de 800 € en el rango de este y mes anterior."
        else:
            ultima = max(candidatos, key=lambda t: t.get("bookingDate",""))
            fecha = ultima.get("bookingDate","")
            contra = ultima.get("creditorName") or ultima.get("debtorName") or "—"
            texto = (
                f"😈 */putoAntonio*: La última transferencia de 800 € fue el {fecha} "
                f"a *{contra}* (ID: `{ultima.get('transactionId')}`)."
            )
    except Exception as e:
        texto = f"⚠️ Error en /putoAntonio: {e}"
    await update.message.reply_text(texto, parse_mode="Markdown")

# --- Comando /morosos ---
@require_mention
async def morosos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    hoy = datetime.today()
    hace_20 = hoy - timedelta(days=20)
    params = {"date_from": hace_20.strftime("%Y-%m-%d"), "date_to": hoy.strftime("%Y-%m-%d")}
    resp = requests.get(TRANSACTIONS_URL, headers=HEADERS, params=params)
    wait = check_rate_limit(resp)
    if wait:
        return await update.message.reply_text(
            f"⚠️ Límite de peticiones excedido. Vuelve a intentarlo en {wait}."
        )

    try:
        resp.raise_for_status()
        txs = resp.json().get("transactions", {}).get("booked", [])
        personas = {"Marco": False, "Alejandro": False, "Luis Miguel": False}
        for tx in txs:
            amt = float(tx.get("transactionAmount",{}).get("amount","0"))
            if amt >= 200.0:
                nombre = tx.get("debtorName","").upper()
                if "LUIS MIGUEL" in nombre:
                    personas["Luis Miguel"] = True
                elif "ALEJANDRO" in nombre:
                    personas["Alejandro"] = True
                elif "MARCO" in nombre:
                    personas["Marco"] = True

        hechos  = [p for p,v in personas.items() if v]
        morosos= [p for p,v in personas.items() if not v]
        lines  = ["📋 */morosos* (últimos 20 días y 200 €):"]
        if hechos:
            lines.append("• Han pagado:")
            for p in hechos: lines.append(f"   – {p}")
        else:
            lines.append("• Nadie ha pagado aún.")
        if morosos:
            lines.append("• Morosos:")
            for p in morosos: lines.append(f"   – {p}")
        texto = "\n".join(lines)
    except Exception as e:
        texto = f"⚠️ Error en /morosos: {e}"
    await update.message.reply_text(texto, parse_mode="Markdown")


# --- Comando /recordatorio (modificado) ---
@require_mention
async def recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REMINDER_COUNTER, REMINDERS
    # Límite de recordatorios
    if len(REMINDERS) >= MAX_REMINDERS:
        return await update.message.reply_text(
            f"❌ Has alcanzado el límite de {MAX_REMINDERS} recordatorios."
        )

    try:
        args = context.args
        fecha_str = args[0]
        hora_str  = args[1]
        mensaje   = " ".join(args[2:])
        dt_record = datetime.fromisoformat(f"{fecha_str}T{hora_str}")
        ahora     = datetime.now()
        if dt_record <= ahora:
            return await update.message.reply_text(
                "❌ La fecha y hora deben ser en el futuro."
            )

        delta = dt_record - ahora
        dias, segundos = delta.days, delta.seconds
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        faltan = []
        if dias:
            faltan.append(f"{dias} día{'s' if dias != 1 else ''}")
        if horas:
            faltan.append(f"{horas} hora{'s' if horas != 1 else ''}")
        if minutos:
            faltan.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
        if not faltan:
            faltan.append("menos de un minuto")
        faltan_str = ", ".join(faltan)
        ahora_str = ahora.strftime("%d/%m/%Y %H:%M")

        # Generar ID y programar recordatorio
        REMINDER_COUNTER += 1
        reminder_id = REMINDER_COUNTER
        segundos_espera = delta.total_seconds()
        job = context.application.job_queue.run_once(
            alarm_callback,
            when=segundos_espera,
            chat_id=update.effective_chat.id,
            data=mensaje,
            name=f"recordatorio_{update.effective_chat.id}_{int(dt_record.timestamp())}"
        )
        REMINDERS[reminder_id] = job
        save_reminders()

        await update.message.reply_text(
            "👌 Recordatorio programado correctamente:\n"
            f"• ID: {reminder_id}\n"
            f"• Ahora: {ahora_str}\n"
            f"• Queda(n): {faltan_str}\n"
            f"• Para: {dt_record.strftime('%d/%m/%Y %H:%M')}\n"
            f"• Mensaje: “{mensaje}”"
        )
    except Exception:
        await update.message.reply_text(
            "❌ Uso: /recordatorio YYYY-MM-DD HH:MM <tu mensaje>"
        )

# --- Nuevo comando /ListaRecordatorios ---
@require_mention
async def lista_recordatorios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not REMINDERS:
        texto = "No hay recordatorios programados."
    else:
        lines = ["📋 *Recordatorios pendientes:*"]
        for rid, job in REMINDERS.items():
            run_at = job.next_t.strftime("%d/%m/%Y %H:%M")
            msg    = job.data
            lines.append(f"• ID {rid}: Para {run_at} — “{msg}”")
        texto = "\n".join(lines)
    await update.message.reply_text(texto, parse_mode="Markdown")

# --- Nuevo comando /borrarRecordatorio ---
@require_mention
async def borrar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global REMINDERS
    try:
        # 1. Convertir el argumento a entero
        rid = int(context.args[0])
    except (IndexError, ValueError):
        return await update.message.reply_text("❌ Uso: /borrarRecordatorio <id>")

    # 2. Buscar el job en memoria
    job = REMINDERS.get(rid)
    if job is None:
        # Si no existe, informamos y no tocamos el fichero
        texto = f"❌ No existe un recordatorio con ID {rid}."
    else:
        # 3. Desprogramar el job y eliminar de REMINDERS
        job.schedule_removal()
        del REMINDERS[rid]

        # 4. Actualizar el JSON con la lista restante
        save_reminders()

        texto = f"🗑️ Recordatorio ID {rid} eliminado."

    await update.message.reply_text(texto)


# --- Comando desconocido ---

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Comando no reconocido. Prueba con alguno de estos:\n"
        "/hola, /fecha, /saldo, /iban, /transacciones, /putoAntonio, /morosos,\n"
        "/recordatorio, /ListaRecordatorios, /borrarRecordatorio,\n"
        "/Rata, /InsultarMarco, /Huevos, /QuienEsElMejorBotDelMundo"
    )


# --- Lógica auxiliar para morosos ---

def get_morosos_text() -> str:
    hoy = datetime.today()
    hace_20 = hoy - timedelta(days=20)
    params = {
        "date_from": hace_20.strftime("%Y-%m-%d"),
        "date_to": hoy.strftime("%Y-%m-%d")
    }
    personas = {"Marco": False, "Alejandro": False, "Luis Miguel": False}
    resp = requests.get(TRANSACTIONS_URL, headers=HEADERS, params=params)
    resp.raise_for_status()
    txs = resp.json().get("transactions", {}).get("booked", [])
    for tx in txs:
        amt = float(tx["transactionAmount"]["amount"])
        if amt >= 200.0:
            nombre = tx.get("debtorName","").upper()
            if "LUIS MIGUEL" in nombre:
                personas["Luis Miguel"] = True
            elif "ALEJANDRO" in nombre:
                personas["Alejandro"] = True
            elif "MARCO" in nombre:
                personas["Marco"] = True
    hechos = [p for p,v in personas.items() if v]
    morosos = [p for p,v in personas.items() if not v]
    lines = ["📋 *Morosos* (automático):"]
    if hechos:
        lines.append("• Han pagado:")
        for p in hechos: lines.append(f"   – {p}")
    else:
        lines.append("• Nadie ha pagado aún.")
    if morosos:
        lines.append("• Morosos:")
        for p in morosos: lines.append(f"   – {p}")
    return "\n".join(lines)

# --- Callback programado: morosos el día 29 (y 26 feb) ---
async def scheduled_morosos(context: ContextTypes.DEFAULT_TYPE) -> None:
    hoy = datetime.now()
    if hoy.day == 29 or (hoy.month == 2 and hoy.day == 26):
        texto = get_morosos_text()
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text="⏰ *Mensaje automático:*\n" + texto,
            parse_mode="Markdown"
        )

# --- Callback programado: chequeo mensual de alquiler ---
from requests.exceptions import HTTPError

async def scheduled_rent(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Solo corremos si es día 13 (en producción sería == 1)
    hoy = datetime.today()
    if hoy.day != 1:
        return

    hace_10 = hoy - timedelta(days=10)
    params = {
        "date_from": hace_10.strftime("%Y-%m-%d"),
        "date_to": hoy.strftime("%Y-%m-%d")
    }

    try:
        resp = requests.get(TRANSACTIONS_URL, headers=HEADERS, params=params)
        # Si la cabecera indica Retry-After, reprogramamos el mismo job
        if resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 60))
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    "⚠️ *Mensaje automático:* Límite de peticiones alcanzado. "
                    f"Reintentando en {retry}s…"
                ),
                parse_mode="Markdown"
            )
            # reprogamamos este mismo callback para dentro de `retry` segundos
            context.job_queue.run_once(scheduled_rent, when=retry, name="rent_retry")
            return

        # Esto lanzará HTTPError para otros 4xx/5xx
        resp.raise_for_status()

        txs = resp.json().get("transactions", {}).get("booked", [])
        paid = any(
            abs(float(tx["transactionAmount"]["amount"])) > 800.0
            for tx in txs
        )

        if paid:
            texto = "⏰ *Mensaje automático:* Ya se ha pagado la mensualidad al casero."
        else:
            texto = (
                "⏰ *Mensaje automático:* No se ha realizado aún el pago de la mensualidad.\n\n"
                + get_morosos_text()
            )

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=texto, parse_mode="Markdown"
        )

    except HTTPError as e:
        # Captura errores distintos a 429
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ *Error automático:* {e}",
            parse_mode="Markdown"
        )
    except Exception as e:
        # Cualquier otra cosa inesperada
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"❌ *Error inesperado:* {e}",
            parse_mode="Markdown"
        )

# --- Callback de alarma ---
async def alarm_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    global REMINDERS
    job = context.job
    chat_id = job.chat_id
    mensaje = job.data

    # 1. Enviar la notificación
    await context.bot.send_message(chat_id, f"⏰ Recordatorio: {mensaje}")

    # 2. Quitarlo de la lista en memoria
    rid_to_remove = None
    for rid, j in REMINDERS.items():
        if j is job:
            rid_to_remove = rid
            break

    if rid_to_remove is not None:
        del REMINDERS[rid_to_remove]
        save_reminders()

    # 3. Intentar desprogramarlo en APScheduler
    try:
        job.schedule_removal()
    except JobLookupError:
        # Ya no estaba en el scheduler, pero no pasa nada
        pass

@require_mention
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    # Sin parse_mode ni backticks: ya no hay caracteres especiales
    await update.message.reply_text(f"🔢 Tu chat ID es: {chat_id}")

# --- Nuevos comandos ---
@require_mention
async def rata(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Sólo en grupos, y sólo si me mencionan


    insults = [
        "Eres más rastrero que una rata apestosa en un callejón oscuro.",
        "Pareces una rata hambrienta buscando migajas en cada esquina.",
        "Más repugnante que una rata con pulgas de circo.",
        "Con la gracia de una rata de alcantarilla en hora punta.",
        "Tu ingenio es tan escaso como la cola de una rata.",
        "Rata de laboratorio: siempre dando malos resultados.",
        "Tu astucia solo la superan las ratas enfermas de peste.",
        "Eres la rata que se esconde cuando suena el ruido de los zapatos.",
        "Hueles peor que una rata mojada tras la lluvia.",
        "Tan despreciable como una rata siniestro rondando basureros.",
        "Más traicionero que la rata que abandona el barco que se hunde.",
        "Con menos encanto que una rata con sarna.",
        "Tu presencia recuerda a la de una rata corriendo por un túnel.",
        "Rata de alcantarilla con complejo de grandeza.",
        "Tu sonrisa de rata no engaña a nadie.",
        "Más escurridizo que una rata en un laberinto.",
        "Rata de cuero: dura por fuera, sarnosa por dentro.",
        "Eres la rata que nadie quiere tener cerca.",
        "Con tu carita de rata, das ganas de huir.",
        "Ni la rata más feroz de los suburbios se atreve a cruzarse contigo."
    ]
    await update.message.reply_text(random.choice(insults))

@require_mention
async def insultar_marco(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:


    frases = [
        "Nunca sería capaz de insultar a alguien tan increíble como Marco.",
        "Mi respeto por Marco me impide decir algo malo.",
        "¿Insultar a Marco? ¡Jamás haría algo así!",
        "Marco es tan genial que no encuentro palabras de insulto.",
        "Mis peores insultos se rinden ante Marco.",
        "Marco merece elogios, no improperios.",
        "No hay insulto lo suficientemente fuerte contra Marco.",
        "Marco trasciende cualquier ofensa que intente formular.",
        "Mi creatividad no alcanza para ofender a Marco.",
        "¿Insultar a Marco? Prefiero elogiarlo eternamente."
    ]
    await update.message.reply_text(random.choice(frases))
@require_mention
async def huevos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    mensajes = [
        "La gran avenida principal de Sevilla hoy ha tenido que cerrar debido al paso programado de Alexander y sus increíbles 🥚🥚.",
        "Atención: desfile especial de Alexander y sus legendarios 🥚 en la calle Feria.",
        "Hoy Alexander conquista Sevilla portando sus poderosos 🥚 por Triana.",
        "Están cortando el tráfico en Nervión por el desfile de Alexander y sus épicos 🥚.",
        "Alexander y sus 🥚 han parado de nuevo la autopista A-4 a su paso.",
        "La procesión de Alexander con sus gigantes 🥚 arrasa en la Alameda de Hércules.",
        "Operativo especial por el paso de Alexander y sus inigualables 🥚.",
        "Cierre temporal de la Macarena: Alexander y sus 🥚 van a pasar.",
        "Los comerciantes de Sevilla aclaman el paso de Alexander con sus 🥚.",
        "Aviso: Alexander y sus imponentes 🥚 cruzan San Bernardo."
    ]
    await update.message.reply_text(random.choice(mensajes))

@require_mention
async def quien_es_mejor_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:


    respuestas = [
        "Ohhhh no me digas esas cosas tan bonitas, pero claro que soy yo, el chispitas.",
        "¡Evidentemente soy yo, el bot más brillante del universo!",
        "¿Quién? ¡Yo mismo, tu bot favorito!",
        "¿El mejor? No hay duda, ¡soy yo!",
        "Con modestia digo: soy el mejor bot del mundo.",
        "Nadie se compara conmigo, ¡yo soy el mejor!",
        "¡Tú lo has dicho! Soy yo, el inigualable bot.",
        "No hay competencia: yo gano por goleada.",
        "Soy el campeón indiscutible de los bots.",
        "¡El mejor bot? ¡Aquí me tienes, listo para servir!"
    ]
    await update.message.reply_text(random.choice(respuestas))


def main() -> None:
    global TELEGRAM_TOKEN, GO_CARDLESS_TOKEN, ACCOUNT_ID
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    load_reminders(app)

    # Registro de handlers
    app.add_handler(CommandHandler("recordatorio", recordatorio))
    app.add_handler(CommandHandler("ListaRecordatorios", lista_recordatorios))
    app.add_handler(CommandHandler("borrarRecordatorio", borrar_recordatorio))
    app.add_handler(CommandHandler("hola", hola))
    app.add_handler(CommandHandler("fecha", fecha))
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("iban", iban))
    app.add_handler(CommandHandler("transacciones", transacciones))
    app.add_handler(CommandHandler("putoAntonio", putoAntonio))
    app.add_handler(CommandHandler("morosos", morosos))
    app.add_handler(CommandHandler("chatid", get_id))
    app.add_handler(CommandHandler("Rata", rata))
    app.add_handler(CommandHandler("InsultarMarco", insultar_marco))
    app.add_handler(CommandHandler("Huevos", huevos))
    app.add_handler(CommandHandler("QuienEsElMejorBotDelMundo", quien_es_mejor_bot))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    # PROGRAMACIÓN DE TAREAS
    job_queue = app.job_queue
    # Morosos: todos los días a las 09:00, pero solo envía si es día 29 o 26-feb
    job_queue.run_daily(scheduled_morosos, time=time(hour=9, minute=0))
    # Alquiler: todos los días a las 09:05, pero solo actúa si es día 1
    job_queue.run_daily(scheduled_rent,   time=time(hour=9, minute=5))
    # Solo para pruebas
    # job_queue.run_once(scheduled_rent, when=5)

    print("Bot de Telegram iniciado. Esperando comandos...")
    app.run_polling()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="App segura con parámetros externos")
    parser.add_argument("--telegram_token", required=True, help="Token del bot de Telegram")
    parser.add_argument("--go_cardless_token", required=True, help="Token de GoCardless")
    parser.add_argument("--account_id", required=True, help="Account ID")

    args = parser.parse_args()
    
    TELEGRAM_TOKEN = args.telegram_token
    GO_CARDLESS_TOKEN = args.go_cardless_token
    ACCOUNT_ID = args.account_id
    BASE_URL           = f"https://bankaccountdata.gocardless.com/api/v2/accounts/{ACCOUNT_ID}"
    BALANCES_URL       = f"{BASE_URL}/balances/"
    DETAILS_URL        = f"{BASE_URL}/details/"
    TRANSACTIONS_URL   = f"{BASE_URL}/transactions/"
    HEADERS = {
    "Authorization": f"Bearer {GO_CARDLESS_TOKEN}",
    "Accept": "application/json"
}
    main()
