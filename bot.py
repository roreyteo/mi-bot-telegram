import os
import requests
import io
import textwrap
from pypdf import PdfReader
from groq import Groq
import replicate
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Clientes
cliente = Groq(api_key=os.environ["GROQ_API_KEY"])

# Historial por usuario (memoria)
historial = {}
ultimo_pdf = {}
ultimo_prompt_imagen = {}

def get_historial(user_id):
    if user_id not in historial:
        historial[user_id] = []
    return historial[user_id]

def agregar_texto_imagen(img_bytes, texto, frase):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    ancho, alto = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fondo semitransparente abajo
    draw.rectangle([(0, alto - 180), (ancho, alto)], fill=(0, 0, 0, 160))

    try:
        fuente_grande = ImageFont.truetype("assets/fuente.ttf", 22)
        fuente_pequeña = ImageFont.truetype("assets/fuente.ttf", 16)
    except:
        fuente_grande = ImageFont.load_default()
        fuente_pequeña = ImageFont.load_default()

    # Texto de reflexión
    lineas = textwrap.wrap(frase, width=45)
    y = alto - 170
    for linea in lineas[:4]:
        draw.text((20, y), linea, font=fuente_grande, fill=(255, 255, 255, 255))
        y += 28

    img_final = Image.alpha_composite(img, overlay).convert("RGB")
    output = io.BytesIO()
    img_final.save(output, format="JPEG", quality=95)
    output.seek(0)
    return output.read()

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy tu asistente AI 🤖\n\n"
        "Puedo:\n"
        "• Responder preguntas con AI\n"
        "• Buscar info en internet\n"
        "• Leer y analizar PDFs\n"
        "• Generar prompts para videos e imágenes\n"
        "• Generar imágenes anime con reflexión\n"
        "• Crear audio con la reflexión en español\n\n"
        "Comandos:\n"
        "/start - Inicio\n"
        "/reset - Borrar historial\n"
        "/buscar [tema] - Buscar en internet\n"
        "/contenido - Generar prompts del último PDF\n"
        "/imagen [descripción] - Generar imagen anime\n"
        "/voz [texto] - Generar audio en español\n"
        "/estilo - Definir tu estilo de contenido"
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

# Comando /voz - genera audio en español
async def voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Usa: /voz [texto a convertir en audio]")
        return
    await update.message.reply_text("🎙️ Generando audio en español...")
    try:
        tts = gTTS(text=texto, lang="es", slow=False)
        audio_io = io.BytesIO()
        tts.write_to_fp(audio_io)
        audio_io.seek(0)
        await update.message.reply_voice(voice=audio_io)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando audio: {e}")

# Comando /estilo
async def estilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args)
    if not args:
        await update.message.reply_text(
            "Define tu estilo de contenido así:\n\n"
            "/estilo [descripción de tu estilo]\n\n"
            "Ejemplo:\n"
            "/estilo Contenido sobre crecimiento personal y metafísica, tono profundo y reflexivo, estética anime oscura con colores morados y dorados"
        )
        return
    user_id = update.effective_user.id
    historial[user_id] = [{"role": "system", "content": f"El usuario tiene este estilo de contenido: {args}. Adapta todo el contenido que generes a este estilo."}]
    await update.message.reply_text(f"✅ Estilo guardado:\n\n{args}\n\nAhora todo el contenido que genere seguirá este estilo 🎨")

# Comando /imagen - genera imagen anime con texto encima
async def generar_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Usa: /imagen [descripción en inglés]\nEjemplo: /imagen a monk meditating under cherry blossoms, anime style")
        return
    await update.message.reply_text("🎨 Generando imagen anime, espera unos segundos...")
    try:
        output = replicate.run(
            "cjwbw/anything-v3-better-vae:09a5805203f4c12da649ec1923bb7729517ca25fcac790e640eaa9ed66573b65",
            input={
                "prompt": f"{prompt}, anime style, high quality, detailed, beautiful",
                "negative_prompt": "ugly, blurry, bad anatomy, low quality",
                "width": 512,
                "height": 512,
                "num_inference_steps": 30
            }
        )
        imagen_url = output[0] if isinstance(output, list) else output
        img_data = requests.get(imagen_url).content

        # Guardar prompt para usar con /contenido
        user_id = update.effective_user.id
        ultimo_prompt_imagen[user_id] = prompt

        await update.message.reply_photo(photo=img_data, caption=f"🎨 {prompt}")
        await update.message.reply_text("💡 Usa /voz [frase] para generar el audio de la reflexión.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando imagen: {e}")

# Comando /contenido - genera prompts separados del último PDF
async def contenido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ultimo_pdf:
        await update.message.reply_text("⚠️ Primero envíame un PDF para generar contenido.")
        return

    texto = ultimo_pdf[user_id]
    await update.message.reply_text("🎨 Generando contenido, espera un momento...")

    try:
        # Prompt de video anime
        resp_video = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[{"role": "user", "content": f"Basándote en este texto:\n{texto[:1500]}\n\nGenera SOLO un prompt detallado en inglés para crear un video corto estilo anime. Incluye: escena, personajes, colores, movimiento, ambiente. Solo el prompt, sin explicaciones."}]
        )
        await update.message.reply_text(f"🎬 PROMPT VIDEO ANIME:\n\n{resp_video.choices[0].message.content}")

        # Prompt de imagen
        resp_imagen = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[{"role": "user", "content": f"Basándote en este texto:\n{texto[:1500]}\n\nGenera SOLO un prompt detallado en inglés para crear una imagen artística estilo anime. Incluye: composición, iluminación, estilo, elementos simbólicos. Solo el prompt, sin explicaciones."}]
        )
        await update.message.reply_text(f"🖼️ PROMPT IMAGEN ANIME:\n\n{resp_imagen.choices[0].message.content}")

        # Plantilla redes sociales
        resp_redes = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=200,
            messages=[{"role": "user", "content": f"Basándote en este texto:\n{texto[:1500]}\n\nGenera SOLO un texto corto impactante (máximo 5 líneas) listo para publicar en Instagram o TikTok en español. Incluye emojis relevantes. Solo el texto, sin explicaciones."}]
        )
        await update.message.reply_text(f"📱 PLANTILLA REDES SOCIALES:\n\n{resp_redes.choices[0].message.content}")

        # Frase reflexión
        resp_frase = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=100,
            messages=[{"role": "user", "content": f"Basándote en este texto:\n{texto[:1500]}\n\nGenera SOLO una frase poderosa y profunda de máximo 2 líneas en español que capture la esencia del texto. Solo la frase, sin explicaciones."}]
        )
        frase = resp_frase.choices[0].message.content
        await update.message.reply_text(f"💬 FRASE REFLEXIÓN:\n\n{frase}")
        await update.message.reply_text("✅ Listo.\n\n1️⃣ Copia el PROMPT IMAGEN y úsalo con /imagen [prompt]\n2️⃣ Copia la FRASE REFLEXIÓN y úsala con /voz [frase]")

    except Exception as e:
        await update.message.reply_text(f"❌ Error generando contenido: {e}")

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

        user_id = update.effective_user.id
        ultimo_pdf[user_id] = texto_doc

        caption = update.message.caption or "Resume y analiza este documento en detalle."
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"{caption}\n\nContenido:\n{texto_doc}"}]
        )
        await update.message.reply_text(respuesta.choices[0].message.content)
        await update.message.reply_text("💡 Escribe /contenido para generar prompts separados de video, imagen, redes sociales y frase.")
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
    app.add_handler(CommandHandler("contenido", contenido))
    app.add_handler(CommandHandler("imagen", generar_imagen))
    app.add_handler(CommandHandler("voz", voz))
    app.add_handler(CommandHandler("estilo", estilo))
    app.add_handler(MessageHandler(filters.Document.ALL, documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))
    print("Bot corriendo...")
    app.run_polling()
