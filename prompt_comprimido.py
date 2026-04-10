ESTILOS_BASE = {
    "anime":      "anime style, cel shading, vibrant, 2D illustration",
    "cinematico": "cinematic, 8K, dramatic lighting, anamorphic lens",
    "oscuro":     "dark fantasy, moody, noir, chiaroscuro, deep shadows",
    "espiritual": "ethereal, mystical, sacred geometry, glowing aura",
}
CALIDAD = "masterpiece, best quality, sharp focus, high detail"
NEGATIVOS = "ugly, blurry, deformed, bad anatomy, watermark, low quality, pixelated"
TEMAS = {
    "liderazgo": "lone figure on mountain peak, golden light, powerful stance",
    "amor":      "two silhouettes, warm glow, soft bokeh, embracing",
    "exito":     "ascending staircase, sunrise, upward motion, bright horizon",
    "sabiduria": "ancient library, floating books, glowing runes, sage figure",
    "libertad":  "open sky, bird in flight, wide horizon, wind motion",
    "fuerza":    "warrior standing, storm background, resolute expression",
    "paz":       "calm water, lotus flower, soft mist, stillness",
}
STOP = {"el","la","los","las","un","una","de","del","al","en","y","o","que","con","por","para","su","sus","se","es","son","fue","ser","como","pero"}

def detectar_tema(texto):
    t = texto.lower()
    conteos = {k: t.count(k) for k in TEMAS}
    return max(conteos, key=conteos.get) if any(conteos.values()) else "sabiduria"

def comprimir_para_imagen(idea, estilo="anime", tema=None, width=512, height=512):
    palabras = [p for p in idea.lower().split() if p not in STOP and len(p) > 3]
    nucleo = ', '.join(palabras[:8])
    visual = TEMAS.get(tema, "") if tema else ""
    partes = [x for x in [nucleo, visual, ESTILOS_BASE.get(estilo, ESTILOS_BASE["anime"]), CALIDAD] if x]
    return {"prompt": ', '.join(partes), "negative_prompt": NEGATIVOS, "width": width, "height": height, "num_inference_steps": 28, "guidance_scale": 7.5}

def comprimir_para_video(idea, estilo="cinematico", duracion_seg=4):
    palabras = [p for p in idea.lower().split() if p not in STOP and len(p) > 3]
    nucleo = ', '.join(palabras[:6])
    visual = TEMAS.get(detectar_tema(idea), "")
    partes = [x for x in [nucleo, visual, "smooth camera motion, cinematic movement", ESTILOS_BASE.get(estilo, ESTILOS_BASE["cinematico"]), CALIDAD] if x]
    return {"prompt": ', '.join(partes), "negative_prompt": NEGATIVOS, "num_frames": duracion_seg*8, "num_inference_steps": 25, "guidance_scale": 7.5, "fps": 8}
