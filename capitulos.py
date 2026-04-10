import re

def detectar_capitulos(texto_completo: str) -> list:
    patrones = [
        r'(cap[ií]tulo\s+\w+[^\n]*)',
        r'(chapter\s+\w+[^\n]*)',
        r'(parte\s+\w+[^\n]*)',
        r'(secci[oó]n\s+\w+[^\n]*)',
        r'^(\d+\.\s+[A-ZÁÉÍÓÚÑ][^\n]{5,60})$',
        r'^([IVXLC]+\.\s+[^\n]{5,60})$',
    ]
    patron_combinado = '|'.join(patrones)
    lineas = texto_completo.split('\n')
    divisiones = []
    for i, linea in enumerate(lineas):
        linea_strip = linea.strip()
        if re.match(patron_combinado, linea_strip, re.IGNORECASE):
            divisiones.append((i, linea_strip))
    capitulos = []
    if len(divisiones) < 2:
        palabras = texto_completo.split()
        tamano = 800
        for i in range(0, len(palabras), tamano):
            bloque = ' '.join(palabras[i:i+tamano])
            capitulos.append({"titulo": f"Sección {len(capitulos)+1}", "texto": bloque})
    else:
        for idx, (num_linea, titulo) in enumerate(divisiones):
            siguiente = divisiones[idx+1][0] if idx+1 < len(divisiones) else len(lineas)
            texto_cap = '\n'.join(lineas[num_linea+1:siguiente]).strip()
            if len(texto_cap) > 100:
                capitulos.append({"titulo": titulo, "texto": texto_cap[:3000]})
    return capitulos[:12]
