import os
import requests
import io
from pypdf import PdfReader
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Cliente Groq
cliente = Groq(api_key=os.environ["GROQ_API_KEY"])

# Historial por usuario (memoria)
historial = {}

def get_historial(user_id):
    if user_id not in historial:
        historial[user_id] = []
    return historial[user_id]

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy tu asistente AI 🤖\n\n"
        "Puedo:\n"
        "• Responder preguntas con AI\n"
        "• Buscar info en internet\n"
        "• Leer y analizar PDFs\n"
        "• Recordar nuestra conversación\n\n"
        "Comandos:\n"
        "/start - Inicio\n"
        "/reset - Borrar historial\n"
        "/buscar [tema] - Buscar en internet"
    )

# Comando /reset
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    historial[user_id] = []
    await update.message.reply_text("✅ Historial borrado. Empezamos de cero.")

# Comando /buscar
async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usa: /buscar [lo que quieres buscar]")
        return
    await update.message.reply_text(f"🔍 Buscando: {query}...")
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        res = requests.get(url, timeout=10).json()
        resumen = res.get("AbstractText") or res.get("Answer") or "No encontré un resumen directo."
        mensajes = [{"role": "user", "content": f"El usuario buscó: '{query}'. Resultado: '{resumen}'. Explícalo claramente en español."}]
        respuesta = cliente.chat.completions.create(model="llama-3.3-70b-versatile", max_tokens=500, messages=mensajes)
        await update.message.reply_text(respuesta.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al buscar: {e}")

# Mensajes de texto normales
async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text
    msgs = get_historial(user_id)
    msgs.append({"role": "user", "content": texto})
    if len(msgs) > 20:
        msgs = msgs[-20:]
        historial[user_id] = msgs
    try:
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[{"role": "system", "content": "Eres un asistente amigable y útil. Respondes en el idioma del usuario. Eres conciso pero completo."}] + msgs
        )
        texto_respuesta = respuesta.choices[0].message.content
        msgs.append({"role": "assistant", "content": texto_respuesta})
        await update.message.reply_text(texto_respuesta)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# Documentos y PDFs
async def documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    mime = doc.mime_type or "desconocido"
    nombre = doc.file_name or "sin nombre"
    await update.message.reply_text(f"📄 Archivo recibido: {nombre}\nTipo: {mime}\nProcesando...")

    try:
        file = await context.bot.get_file(doc.file_id, read_timeout=60, write_timeout=60, connect_timeout=60)
        bytes_doc = await file.download_as_bytearray()

        # Detectar PDF por nombre o mime_type
        es_pdf = mime == "application/pdf" or nombre.lower().endswith(".pdf")

        if es_pdf:
            pdf_reader = PdfReader(io.BytesIO(bytes(bytes_doc)))
            texto_doc = ""
            for page in pdf_reader.pages:
                texto_doc += page.extract_text() or ""
            texto_doc = texto_doc[:4000]
            if not texto_doc.strip():
                await update.message.reply_text("❌ No pude extraer texto. Puede ser un PDF escaneado.")
                return
        elif "text" in mime:
            texto_doc = bytes_doc.decode("utf-8", errors="ignore")[:4000]
        else:
            await update.message.reply_text(f"❌ Tipo de archivo no soportado: {mime}")
            return

        caption = update.message.caption or "Resume y analiza este documento en detalle."
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"{caption}\n\nContenido:\n{texto_doc}"}]
        )
        await update.message.reply_text(respuesta.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"❌ Error procesando documento: {e}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot corriendo")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    TOKEN = os.environ["TELEGRAM_TOKEN"]
    threading.Thread(target=run_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).read_timeout(60).write_timeout(60).connect_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(MessageHandler(filters.Document.ALL, documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))
    print("Bot corriendo...")
    app.run_polling()
