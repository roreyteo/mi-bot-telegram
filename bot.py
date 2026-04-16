import os
import requests
import io
import fcntl
import sys
from pypdf import PdfReader
from groq import Groq
import replicate
from gtts import gTTS
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from capitulos import detectar_capitulos
from video_capitulo import generar_video_capitulo
from prompt_comprimido import comprimir_para_imagen, comprimir_para_video, detectar_tema

cliente = Groq(api_key=os.environ["GROQ_API_KEY"])
historial = {}
ultimo_pdf = {}
ideas_por_capitulo = {}
imagenes_por_capitulo = {}
RUTA_MUSICA = "assets/musica.mp3"

def verificar_instancia_unica():
    lock_file = open("/tmp/mibot.lock", "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("❌ Ya hay una instancia corriendo.")
        sys.exit(1)

def get_historial(user_id):
    if user_id not in historial:
        historial[user_id] = []
    return historial[user_id]

ESTILOS = {
    "anime":      "anime style, cel shading, vibrant, 2D illustration, masterpiece",
    "cinematico": "cinematic, 8K, dramatic lighting, anamorphic lens, masterpiece",
    "oscuro":     "dark fantasy, moody, noir, chiaroscuro, deep shadows, masterpiece",
    "espiritual": "ethereal, mystical, sacred geometry, glowing aura, masterpiece",
    "acuarela":   "watercolor painting, soft edges, painterly, artistic, masterpiece",
}
NEGATIVOS = "ugly, blurry, deformed, bad anatomy, watermark, low quality, pixelated, nsfw"

def elegir_estilo(texto):
    texto = texto.lower()
    if any(p in texto for p in ["guerra","muerte","oscuro","miedo","sombra","dolor"]):
        return "oscuro"
    elif any(p in texto for p in ["espiritu","alma","dios","meditacion","paz","sagrado"]):
        return "espiritual"
    elif any(p in texto for p in ["historia","real","vida","persona","mundo","tiempo"]):
        return "cinematico"
    elif any(p in texto for p in ["arte","color","naturaleza","suave","belleza"]):
        return "acuarela"
    else:
        return "anime"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy tu asistente AI 🤖\n\n"
        "📄 Sube un PDF y usa los comandos:\n\n"
        "/ideas — Extrae ideas principales por capítulo\n"
        "/imagenes — Genera imágenes de las ideas\n"
        "/video — Genera video con voz + música\n\n"
        "Otros comandos:\n"
        "/start - Inicio\n"
        "/reset - Borrar historial\n"
        "/buscar [tema] - Buscar en internet\n"
        "/imagen [descripción] - Imagen suelta\n"
        "/voz [texto] - Audio en español\n"
        "/estilo - Definir estilo"
    )

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    historial[user_id] = []
    ideas_por_capitulo.pop(user_id, None)
    imagenes_por_capitulo.pop(user_id, None)
    await update.message.reply_text("✅ Todo borrado. Empieza subiendo un PDF.")

async def cmd_ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ultimo_pdf:
        await update.message.reply_text("⚠️ Primero sube un PDF.")
        return

    await update.message.reply_text("🧠 Analizando capítulos y extrayendo ideas...")

    texto_completo = ultimo_pdf[user_id]
    capitulos = detectar_capitulos(texto_completo)
    ideas_por_capitulo[user_id] = []

    for idx, cap in enumerate(capitulos):
        try:
            resp = cliente.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                messages=[{"role": "user", "content": (
                    f"Del siguiente capítulo '{cap['titulo']}' extrae SOLO las ideas principales necesarias "
                    f"(no inventes, solo las que realmente están). "
                    f"Responde en este formato exacto:\n"
                    f"IDEAS:\n- idea 1\n- idea 2\n- idea 3 (solo las necesarias)\n"
                    f"NARRACION: [historia dramática de 3-4 oraciones que capture la esencia del capítulo]\n\n"
                    f"Texto:\n{cap['texto'][:2000]}"
                )}]
            )
            contenido = resp.choices[0].message.content
            ideas = []
            narracion = ""
            seccion = ""
            for linea in contenido.split("\n"):
                if linea.startswith("IDEAS:"):
                    seccion = "ideas"
                elif linea.startswith("NARRACION:"):
                    narracion = linea.replace("NARRACION:", "").strip()
                    seccion = "narracion"
                elif linea.startswith("- ") and seccion == "ideas":
                    ideas.append(linea.replace("- ", "").strip())

            ideas_por_capitulo[user_id].append({
                "titulo": cap["titulo"],
                "ideas": ideas,
                "narracion": narracion,
                "texto": cap["texto"]
            })

            msg = f"📖 *{cap['titulo']}*\n\n"
            for i, idea in enumerate(ideas):
                msg += f"💡 {i+1}. {idea}\n"
            msg += f"\n🎭 _{narracion}_"
            await update.message.reply_text(msg, parse_mode="Markdown")

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error en cap. {idx+1}: {e}")

    await update.message.reply_text(
        f"✅ Ideas extraídas de {len(capitulos)} capítulos.\n\n"
        "Ahora usa /imagenes para generar las imágenes 🎨"
    )

async def cmd_imagenes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ideas_por_capitulo or not ideas_por_capitulo[user_id]:
        await update.message.reply_text("⚠️ Primero usa /ideas para extraer las ideas del PDF.")
        return

    await update.message.reply_text("🎨 Generando imágenes por capítulo...")
    imagenes_por_capitulo[user_id] = []

    for idx, cap in enumerate(ideas_por_capitulo[user_id]):
        titulo = cap["titulo"]
        ideas = cap["ideas"]
        texto = cap["texto"]

        if not ideas:
            imagenes_por_capitulo[user_id].append({"titulo": titulo, "imagenes": [], "narracion": cap["narracion"]})
            continue

        await update.message.reply_text(f"🖼️ Generando imágenes: *{titulo}*...", parse_mode="Markdown")

        estilo = elegir_estilo(texto)
        imagenes_cap = []

        for idea in ideas:
            try:
                tema = detectar_tema(idea)
                params = comprimir_para_imagen(idea=idea, estilo=estilo, tema=tema, width=512, height=512)
                output = replicate.run(
                    "cjwbw/anything-v3-better-vae:09a5805203f4c12da649ec1923bb7729517ca25fcac790e640eaa9ed66573b65",
                    input=params
                )
                imagen_url = output[0] if isinstance(output, list) else output
                img_data = requests.get(imagen_url).content
                imagenes_cap.append(img_data)
                await update.message.reply_photo(
                    photo=io.BytesIO(img_data),
                    caption=f"🎨 {idea[:100]}"
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ Error imagen '{idea[:40]}': {e}")

        imagenes_por_capitulo[user_id].append({
            "titulo": titulo,
            "imagenes": imagenes_cap,
            "narracion": cap["narracion"]
        })

    await update.message.reply_text(
        "✅ Imágenes generadas.\n\n"
        "Ahora usa /video para generar los videos 🎬"
    )

async def cmd_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in imagenes_por_capitulo or not imagenes_por_capitulo[user_id]:
        await update.message.reply_text("⚠️ Primero usa /imagenes para generar las imágenes.")
        return

    await update.message.reply_text("🎬 Generando videos con voz dramática + música...")

    for idx, cap in enumerate(imagenes_por_capitulo[user_id]):
        titulo = cap["titulo"]
        imagenes = cap["imagenes"]
        narracion = cap["narracion"]

        if not imagenes:
            await update.message.reply_text(f"⏭️ Saltando {titulo} — sin imágenes.")
            continue

        try:
            await update.message.reply_text(f"🎬 Video: *{titulo}*...", parse_mode="Markdown")

            video_bytes = generar_video_capitulo(
                imagenes_bytes=imagenes,
                texto_narracion=narracion,
                titulo_capitulo=titulo,
                ruta_musica=RUTA_MUSICA
            )

            # Descripción para redes sociales
            resp_desc = cliente.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=150,
                messages=[{"role": "user", "content": (
                    f"Crea una descripción corta y atractiva para redes sociales (máximo 3 líneas) "
                    f"del capítulo '{titulo}' con esta narración: '{narracion}'. "
                    f"Incluye emojis y que genere curiosidad. Solo el texto, sin explicaciones."
                )}]
            )
            descripcion = resp_desc.choices[0].message.content

            await update.message.reply_video(
                video=io.BytesIO(video_bytes),
                caption=f"🎬 *{titulo}*\n\n{descripcion}",
                parse_mode="Markdown",
                width=1080, height=1080
            )

        except Exception as e:
            await update.message.reply_text(f"⚠️ Error video cap. {idx+1}: {e}")

    await update.message.reply_text("✅ ¡Videos listos! 🚀")

async def buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Usa: /buscar [tema]")
        return
    await update.message.reply_text(f"🔍 Buscando: {query}...")
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        res = requests.get(url, timeout=10).json()
        resumen = res.get("AbstractText") or res.get("Answer") or "Sin resultado directo."
        resp = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile", max_tokens=500,
            messages=[{"role": "user", "content": f"Buscaron: '{query}'. Resultado: '{resumen}'. Explícalo en español."}]
        )
        await update.message.reply_text(resp.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = " ".join(context.args)
    if not texto:
        await update.message.reply_text("Usa: /voz [texto]")
        return
    try:
        tts = gTTS(text=texto, lang="es", slow=False)
        audio_io = io.BytesIO()
        tts.write_to_fp(audio_io)
        audio_io.seek(0)
        await update.message.reply_voice(voice=audio_io)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def estilo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args)
    if not args:
        await update.message.reply_text("Usa: /estilo [descripción]")
        return
    historial[update.effective_user.id] = [{"role": "system", "content": f"Estilo: {args}"}]
    await update.message.reply_text(f"✅ Estilo guardado: {args}")

async def generar_imagen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descripcion = " ".join(context.args)
    if not descripcion:
        await update.message.reply_text("Usa: /imagen [descripción]")
        return
    await update.message.reply_text("🎨 Generando imagen...")
    try:
        estilo_elegido = elegir_estilo(descripcion)
        tema = detectar_tema(descripcion)
        params = comprimir_para_imagen(idea=descripcion, estilo=estilo_elegido, tema=tema, width=512, height=512)
        output = replicate.run(
            "cjwbw/anything-v3-better-vae:09a5805203f4c12da649ec1923bb7729517ca25fcac790e640eaa9ed66573b65",
            input=params
        )
        imagen_url = output[0] if isinstance(output, list) else output
        img_data = requests.get(imagen_url).content
        await update.message.reply_photo(photo=img_data, caption=f"🎨 {descripcion}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    texto = update.message.text
    msgs = get_historial(user_id)
    msgs.append({"role": "user", "content": texto})
    if len(msgs) > 20:
        msgs = msgs[-20:]
        historial[user_id] = msgs
    try:
        resp = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile", max_tokens=1000,
            messages=[{"role": "system", "content": "Eres un asistente amigable. Respondes en el idioma del usuario."}] + msgs
        )
        texto_resp = resp.choices[0].message.content
        msgs.append({"role": "assistant", "content": texto_resp})
        await update.message.reply_text(texto_resp)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    mime = doc.mime_type or "desconocido"
    nombre = doc.file_name or "sin nombre"
    await update.message.reply_text(f"📄 Recibido: *{nombre}*\nProcesando...", parse_mode="Markdown")
    try:
        file = await context.bot.get_file(doc.file_id, read_timeout=60, write_timeout=60, connect_timeout=60)
        bytes_doc = await file.download_as_bytearray()
        es_pdf = mime == "application/pdf" or nombre.lower().endswith(".pdf")
        if es_pdf:
            pdf_reader = PdfReader(io.BytesIO(bytes(bytes_doc)))
            texto_doc = ""
            for page in pdf_reader.pages:
                texto_doc += page.extract_text() or ""
            if not texto_doc.strip():
                await update.message.reply_text("❌ No pude extraer texto.")
                return
            ultimo_pdf[update.effective_user.id] = texto_doc
            await update.message.reply_text(
                "✅ PDF guardado correctamente.\n\n"
                "Ahora usa:\n"
                "/ideas — para extraer las ideas\n"
                "/imagenes — para generar imágenes\n"
                "/video — para generar el video"
            )
        else:
            await update.message.reply_text(f"❌ Tipo no soportado: {mime}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot corriendo")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

if __name__ == "__main__":
    verificar_instancia_unica()
    TOKEN = os.environ["TELEGRAM_TOKEN"]
    threading.Thread(target=run_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).read_timeout(120).write_timeout(120).connect_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("buscar", buscar))
    app.add_handler(CommandHandler("ideas", cmd_ideas))
    app.add_handler(CommandHandler("imagenes", cmd_imagenes))
    app.add_handler(CommandHandler("video", cmd_video))
    app.add_handler(CommandHandler("imagen", generar_imagen))
    app.add_handler(CommandHandler("voz", voz))
    app.add_handler(CommandHandler("estilo", estilo))
    app.add_handler(MessageHandler(filters.Document.ALL, documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))
    print("✅ Bot corriendo...")
    app.run_polling()
