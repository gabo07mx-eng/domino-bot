"""
tablero_img.py — Dibuja el tablero de dominó centrado con crecimiento tipo "serpiente" (Snake Pathing).
Ajustado a proporción 4:3 para Telegram.
"""

from io import BytesIO

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit(
        "Falta Pillow, que es la librería que dibuja el tablero.\n"
        "Instálala con:  pip install pillow"
    )

# ── Medidas (en píxeles) ──────────────────────────────────────────────
LARGO = 84          # largo de una ficha
ANCHO = 42          # ancho de una ficha
PEGUE = 1           # separación entre fichas consecutivas
MARGEN_MESA = 30    # margen verde extra en los bordes de la imagen final
MIN_WIDTH = 630     # ancho mínimo de la imagen para Telegram

# ── Límites de la Serpiente ───────────────────────────────────────────
LIMIT_MAIN = 290    # Límite en píxeles desde el centro para la fila principal (~3 normales + 1 doble)
LIMIT_SEC = 290     # Límite en píxeles para las filas secundarias (~7 fichas normales)
ESPACIO_FILAS = 64  # Separación fija entre una fila y la siguiente (vez y media del ancho)
SALTO_Y = 88 #LARGO + ESPACIO_FILAS . Distancia vertical exacta al saltar de fila

# ── Colores ───────────────────────────────────────────────────────────
FONDO = (23, 82, 57)
FICHA = (250, 248, 243)
BORDE = (198, 192, 180)
SOMBRA = (15, 56, 39)
LINEA = (125, 119, 109)
PUNTO = (30, 28, 26)
PUNTA = (233, 190, 92)

PUNTOS = {
    0: [],
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
    4: [(0, 0), (2, 0), (0, 2), (2, 2)],
    5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)],
    6: [(0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)],
    7: [(0, 0), (0, 1), (0, 2), (1, 1), (2, 0), (2, 1), (2, 2)],
    8: [(0, 0), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1), (2, 2)],
    9: [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)],
}

def _puntos_en(d, valor, caja):
    if valor == 0:
        return
    x0, y0, x1, y1 = caja
    lado = min(x1 - x0, y1 - y0)
    cx0 = (x0 + x1) / 2 - lado / 2
    cy0 = (y0 + y1) / 2 - lado / 2
    radio = max(2, lado // 11)
    paso = lado / 4.0
    for col, fil in PUNTOS[valor]:
        px = cx0 + paso * (col + 1)
        py = cy0 + paso * (fil + 1)
        d.ellipse([px - radio, py - radio, px + radio, py + radio], fill=PUNTO)

def _ficha(d, a, b, x, y, vertical, punta_a=False, punta_b=False):
    ancho, alto = (ANCHO, LARGO) if vertical else (LARGO, ANCHO)
    radio = 6
    aire = 5

    d.rounded_rectangle([x + 1, y + 2, x + ancho + 1, y + alto + 2], radius=radio, fill=SOMBRA)
    d.rounded_rectangle([x, y, x + ancho, y + alto], radius=radio, fill=FICHA, outline=BORDE, width=1)

    if vertical:
        medio = y + alto / 2
        d.line([x + 7, medio, x + ancho - 7, medio], fill=LINEA, width=2)
        caja_a = (x + aire, y + aire, x + ancho - aire, medio - aire)
        caja_b = (x + aire, medio + aire, x + ancho - aire, y + alto - aire)
    else:
        medio = x + ancho / 2
        d.line([medio, y + 7, medio, y + alto - 7], fill=LINEA, width=2)
        caja_a = (x + aire, y + aire, medio - aire, y + alto - aire)
        caja_b = (medio + aire, y + aire, x + ancho - aire, y + alto - aire)

    _puntos_en(d, a, caja_a)
    _puntos_en(d, b, caja_b)

    for caja, marcar in ((caja_a, punta_a), (caja_b, punta_b)):
        if marcar:
            x0, y0, x1, y1 = caja
            d.rounded_rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], radius=4, outline=PUNTA, width=2)

def colocar_cadena(cadena, x_start, y_center_row, dir_x_ini, dir_y_salto):
    """Calcula las coordenadas (x,y) de una cadena de fichas trazando la 'serpiente'."""
    coordenadas = []
    row_num = 0
    cx = x_start
    cy = y_center_row
    dir_x = dir_x_ini

    for (v_in, v_out) in cadena:
        is_vert = (v_in == v_out)
        w = ANCHO if is_vert else LARGO
        h = LARGO if is_vert else ANCHO
        
        limite = LIMIT_MAIN if row_num == 0 else LIMIT_SEC

        # Comprobar si choca con el borde y debe hacer el salto de fila
        if dir_x == 1:
            if cx + w > limite:
                row_num += 1
                dir_x = -1
                cy += dir_y_salto * SALTO_Y
                cx = cx - PEGUE  # Alinea con el borde derecho de la fila anterior
        else:
            if cx - w < -limite:
                row_num += 1
                dir_x = 1
                cy += dir_y_salto * SALTO_Y
                cx = cx + PEGUE  # Alinea con el borde izquierdo de la fila anterior

        # Colocar la ficha según la dirección actual
        if dir_x == 1:
            x_draw = cx
            y_draw = cy - h / 2
            coordenadas.append((v_in, v_out, x_draw, y_draw, is_vert, dir_x))
            cx = x_draw + w + PEGUE
        else:
            x_draw = cx - w
            y_draw = cy - h / 2
            # Al dibujar de derecha a izquierda, pasamos invertidos para que conecte visualmente
            coordenadas.append((v_out, v_in, x_draw, y_draw, is_vert, dir_x))
            cx = x_draw - PEGUE

    return coordenadas

def dibujar_tablero(tablero):
    tablero_list = list(tablero)
    if not tablero_list:
        img_vacia = Image.new("RGB", (MIN_WIDTH, int(MIN_WIDTH / (4/3))), FONDO)
        buf = BytesIO()
        img_vacia.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf

    # 1. Identificar la ficha de salida (centro geométrico)
    idx_salida = -1
    mayor_doble = -1
    for i, (a, b) in enumerate(tablero_list):
        if a == b and a > mayor_doble:
            mayor_doble = a
            idx_salida = i
    if idx_salida == -1:
        idx_salida = len(tablero_list) // 2

    # 2. Dividir en las dos ramas (izquierda/A y derecha/B) y estandarizar enlaces (in, out)
    c_val_a, c_val_b = tablero_list[idx_salida]
    
    path_b = [(a, b) for a, b in tablero_list[idx_salida+1:]]
    # Invertimos las tuplas de Path A para que ambas ramas tengan lógica (val_in, val_out)
    path_a = [(b, a) for a, b in reversed(tablero_list[:idx_salida])]

    # 3. Preparar la ficha central
    is_vert_c = (c_val_a == c_val_b)
    w_c = ANCHO if is_vert_c else LARGO
    h_c = LARGO if is_vert_c else ANCHO
    x_c = -w_c / 2
    y_c = -h_c / 2

    punta_c_a = len(path_a) == 0
    punta_c_b = len(path_b) == 0

    fichas_a_dibujar = [ (c_val_a, c_val_b, x_c, y_c, is_vert_c, punta_c_a, punta_c_b) ]

    # 4. Calcular coordenadas de las ramas (Cámara Virtual)
    # Lado Derecho (B): Empieza hacia la derecha (1) y serpentea hacia Abajo (1)
    coords_b = colocar_cadena(path_b, x_c + w_c + PEGUE, 0, 1, 1)
    # Lado Izquierdo (A): Empieza hacia la izquierda (-1) y serpentea hacia Arriba (-1)
    coords_a = colocar_cadena(path_a, x_c - PEGUE, 0, -1, -1)

    # 5. Unir y marcar las Puntas Abiertas reales de cada extremo
    def procesar_coords(coords):
        for i, c in enumerate(coords):
            a_draw, b_draw, x, y, is_vert, dir_x = c
            is_last = (i == len(coords) - 1)
            p_a, p_b = False, False
            if is_last:
                if dir_x == 1: p_b = True
                else: p_a = True
            fichas_a_dibujar.append((a_draw, b_draw, x, y, is_vert, p_a, p_b))

    procesar_coords(coords_b)
    procesar_coords(coords_a)

    # 6. Calcular la Caja Delimitadora (Bounding Box) de todas las coordenadas
    min_x = min(f[2] for f in fichas_a_dibujar)
    min_y = min(f[3] for f in fichas_a_dibujar)
    max_x = max(f[2] + (ANCHO if f[4] else LARGO) for f in fichas_a_dibujar)
    max_y = max(f[3] + (LARGO if f[4] else ANCHO) for f in fichas_a_dibujar)

    # 7. Forzar simetría perfecta alrededor de (0,0) para mantener la salida clavada en el centro
    max_dist_x = max(abs(min_x), abs(max_x))
    max_dist_y = max(abs(min_y), abs(max_y))

    canvas_w = int(max_dist_x * 2) + MARGEN_MESA * 2
    canvas_h = int(max_dist_y * 2) + MARGEN_MESA * 2

    # 8. Ajustar Relación de Aspecto (4:3) y tamaño mínimo
    ratio_contenido = canvas_w / canvas_h if canvas_h > 0 else 1
    ratio_objetivo = 4 / 3

    if ratio_contenido > ratio_objetivo:
        canvas_h = int(canvas_w / ratio_objetivo)
    else:
        canvas_w = int(canvas_h * ratio_objetivo)

    if canvas_w < MIN_WIDTH:
        canvas_w = MIN_WIDTH
        canvas_h = int(canvas_w / ratio_objetivo)

    # 9. Crear el lienzo final y dibujar aplicando el Offset del centro
    img_final = Image.new("RGB", (canvas_w, canvas_h), FONDO)
    d = ImageDraw.Draw(img_final)

    offset_x = canvas_w // 2
    offset_y = canvas_h // 2

    for f in fichas_a_dibujar:
        a_d, b_d, x_d, y_d, vert_d, p_a, p_b = f
        _ficha(d, a_d, b_d, x_d + offset_x, y_d + offset_y, vert_d, p_a, p_b)

    buf = BytesIO()
    img_final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf