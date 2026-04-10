import io, os, tempfile
from gtts import gTTS
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
from PIL import Image

def generar_video_capitulo(imagenes_bytes, texto_narracion, titulo_capitulo, ruta_musica=None):
    with tempfile.TemporaryDirectory() as tmp:
        rutas_imgs = []
        for i, img_bytes in enumerate(imagenes_bytes):
            img = Image.open(io.BytesIO(img_bytes))
            img = img.resize((1080, 1080), Image.LANCZOS)
            ruta = os.path.join(tmp, f"img_{i}.jpg")
            img.save(ruta, "JPEG", quality=92)
            rutas_imgs.append(ruta)

        ruta_voz = os.path.join(tmp, "voz.mp3")
        tts = gTTS(text=texto_narracion, lang="es", slow=False)
        tts.save(ruta_voz)

        audio_voz = AudioFileClip(ruta_voz)
        duracion_total = audio_voz.duration
        duracion_por_imagen = duracion_total / len(rutas_imgs)

        clips = [
            ImageClip(r).set_duration(duracion_por_imagen).fadein(0.5).fadeout(0.5)
            for r in rutas_imgs
        ]
        video = concatenate_videoclips(clips, method="compose")

        audios = [audio_voz]
        if ruta_musica and os.path.exists(ruta_musica):
            try:
                musica = AudioFileClip(ruta_musica).subclip(0, min(duracion_total, AudioFileClip(ruta_musica).duration)).volumex(0.15)
                audios.append(musica)
            except:
                pass

        video = video.set_audio(CompositeAudioClip(audios) if len(audios) > 1 else audios[0])

        ruta_video = os.path.join(tmp, "video.mp4")
        video.write_videofile(ruta_video, fps=24, codec="libx264", audio_codec="aac", verbose=False, logger=None)

        with open(ruta_video, "rb") as f:
            return f.read()
