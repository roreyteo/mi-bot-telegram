import os
import requests
import base64
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
        "• Analizar imágenes\n"
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

    url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
    res = requests.get(url).json()
    resumen = res.get("AbstractText") or res.get("Answer") or "No encontré un resumen directo."

    mensajes = [{"role": "user", "content": f"El usuario buscó: '{query}'. Resultado encontrado: '{resumen}'. Explícalo de forma clara y útil en español."}]
    respuesta = cliente.chat.completions.create(model="llama-3.3-70b-versatile", max_tokens=500, messages=mensajes)
    await update.message.reply_text(respuesta.choices[0].message.content)

# Mensajes de texto normales
async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text
    msgs = get_historial(user_id)

    msgs.append({"role": "user", "content": texto})

    if len(msgs) > 20:
        msgs = msgs[-20:]
        historial[user_id] = msgs

    respuesta = cliente.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1000,
        messages=[{"role": "system", "content": "Eres un asistente amigable y útil. Respondes en el idioma del usuario. Eres conciso pero completo."}] + msgs
    )
    texto_respuesta = respuesta.choices[0].message.content
    msgs.append({"role": "assistant", "content": texto_respuesta})
    await update.message.reply_text(texto_respuesta)

# Imágenes
async def imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼️ Analizando imagen...")
    caption = update.message.caption or "Describe esta imagen."
    respuesta = cliente.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1000,
        messages=[{"role": "user", "content": caption}]
    )
    await update.message.reply_text(respuesta.choices[0].message.content)

# Documentos
async def documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.mime_type and "text" in doc.mime_type:
        file = await context.bot.get_file(doc.file_id)
        bytes_doc = await file.download_as_bytearray()
        texto_doc = bytes_doc.decode("utf-8", errors="ignore")[:3000]
        caption = update.message.caption or "Resume y analiza este documento."
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[{"role": "user", "content": f"{caption}\n\nContenido:\n{texto_doc}"}]
        )
        await update.message.reply_text(respuesta.choices[0].message.content)
    else:
        await update.message.reply_text("📄 Solo puedo analizar archivos de texto por ahora.")

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
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(MessageHandler(filters.PHOTO, imagen))
    app.add_handler(MessageHandler(filters.Document.ALL, documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))
    print("Bot corriendo...")
    app.run_polling()
