"""
Prototipo: gestión de mina a cielo abierto.

Ejecutar:   python juego.py
Controles:
  1  Herramienta perforar (clic en una columna)
  2  Herramienta extraer -> PLANTA
  3  Herramienta extraer -> BOTADERO
  C  Comprar camión
  Espacio  Pasar al mes siguiente
  R  Reiniciar con un yacimiento nuevo
"""

import sys

import pygame

import modelo as m

TAM = 22                       # píxeles por bloque
MARGEN_X, MARGEN_Y = 20, 60
ANCHO_MAPA = m.COLUMNAS * TAM
ALTO_MAPA = m.FILAS * TAM
PANEL_X = MARGEN_X + ANCHO_MAPA + 20
ANCHO, ALTO = PANEL_X + 300, MARGEN_Y + ALTO_MAPA + 170

CIELO = (24, 28, 38)
DESCONOCIDO = (78, 62, 50)
TEXTO = (230, 230, 230)
TENUE = (150, 150, 160)
RESALTE = (255, 255, 255)

HERRAMIENTAS = {
    "perforar": "1 Perforar",
    "planta": "2 Extraer -> Planta",
    "botadero": "3 Extraer -> Botadero",
}


def color_ley(ley, corte):
    """Gris (estéril) -> amarillo (en la ley de corte) -> rojo (alta ley)."""
    if ley < corte:
        t = max(0.0, ley / corte)
        return _mezcla((95, 90, 85), (150, 140, 90), t)
    t = min(1.0, (ley - corte) / 1.0)
    return _mezcla((230, 200, 60), (210, 60, 40), t)


def _mezcla(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def celda_bajo_raton(pos):
    x, y = pos
    c = (x - MARGEN_X) // TAM
    f = (y - MARGEN_Y) // TAM
    if 0 <= c < m.COLUMNAS and 0 <= f < m.FILAS:
        return c, f
    return None


def dibujar(pantalla, mina, fuentes, herramienta, hover):
    f_chica, f_media, f_grande = fuentes
    pantalla.fill(CIELO)
    corte = mina.ley_de_corte()

    titulo = f"Mes {min(mina.mes, m.MESES_TOTALES)}/{m.MESES_TOTALES}   Caja: US${mina.caja:,.0f}"
    pantalla.blit(f_grande.render(titulo, True, TEXTO), (MARGEN_X, 18))

    # --- Bloques ---
    for f in range(m.FILAS):
        for c in range(m.COLUMNAS):
            b = mina.bloque(c, f)
            rect = pygame.Rect(MARGEN_X + c * TAM, MARGEN_Y + f * TAM, TAM, TAM)
            if b.extraido:
                pygame.draw.rect(pantalla, CIELO, rect)
                continue
            ley = mina.ley_conocida(c, f)
            if ley is None:
                pygame.draw.rect(pantalla, DESCONOCIDO, rect)
            elif b.ley_muestreada is not None:
                pygame.draw.rect(pantalla, color_ley(ley, corte), rect)
            else:
                # estimada: color más apagado para recordar que es incierta
                col = _mezcla(color_ley(ley, corte), DESCONOCIDO, 0.45)
                pygame.draw.rect(pantalla, col, rect)
            pygame.draw.rect(pantalla, (40, 35, 30), rect, 1)
            if mina.es_accesible(c, f) and herramienta != "perforar":
                pygame.draw.rect(pantalla, (120, 200, 255), rect.inflate(-6, -6), 1)

    # sondajes: línea vertical sobre la columna
    for c in mina.sondajes:
        x = MARGEN_X + c * TAM + TAM // 2
        pygame.draw.line(pantalla, (40, 160, 255), (x, MARGEN_Y - 8), (x, MARGEN_Y - 1), 3)

    # cursor
    if hover:
        c, f = hover
        if herramienta == "perforar":
            r = pygame.Rect(MARGEN_X + c * TAM, MARGEN_Y, TAM, ALTO_MAPA)
        else:
            r = pygame.Rect(MARGEN_X + c * TAM, MARGEN_Y + f * TAM, TAM, TAM)
        pygame.draw.rect(pantalla, RESALTE, r, 2)

    # --- Panel derecho ---
    y = MARGEN_Y
    lineas = [
        (f_media, f"Precio Cu: US${mina.precio:,.0f}/t", TEXTO),
        (f_media, f"Ley de corte: {corte:.2f}% Cu", (230, 200, 60)),
        (f_chica, "", TEXTO),
        (f_media, f"Camiones: {mina.camiones}", TEXTO),
        (f_chica, f"Movidos este mes: {mina.movidos_este_mes}/{mina.capacidad_mensual()} bloques", TEXTO),
        (f_chica, f"Planta este mes: {mina.planta_este_mes}/{m.CAPACIDAD_PLANTA} bloques", TEXTO),
        (f_chica, f"Cobre producido: {mina.cobre_producido:,.0f} t", TEXTO),
        (f_chica, "", TEXTO),
        (f_media, "Herramienta:", TEXTO),
    ]
    for clave, nombre in HERRAMIENTAS.items():
        color = RESALTE if clave == herramienta else TENUE
        lineas.append((f_chica, ("> " if clave == herramienta else "   ") + nombre, color))
    lineas += [
        (f_chica, "", TEXTO),
        (f_chica, "C  comprar camión (US$400k)", TENUE),
        (f_chica, "Espacio  pasar el mes", TENUE),
        (f_chica, "R  reiniciar", TENUE),
    ]
    for fuente, texto, color in lineas:
        pantalla.blit(fuente.render(texto, True, color), (PANEL_X, y))
        y += fuente.get_linesize() + 2

    # Info del bloque bajo el ratón
    if hover:
        c, f = hover
        b = mina.bloque(c, f)
        y += 10
        pantalla.blit(f_media.render(f"Bloque col {c + 1}, fila {f + 1}", True, TEXTO), (PANEL_X, y))
        y += 24
        if b.extraido:
            info = [f"Extraído -> {b.destino}", f"Ley real: {b.ley_real:.2f}%"]
        else:
            ley = mina.ley_conocida(c, f)
            fuente_dato = ("sondaje" if b.ley_muestreada is not None
                           else "estimada" if ley is not None else "sin datos")
            info = [f"Ley: {ley:.2f}% ({fuente_dato})" if ley is not None else "Ley: ? (sin datos)",
                    f"Costo mina: US${mina.costo_mina_bloque(f):,.0f}"]
            if ley is not None:
                info.append(f"Margen planta: US${mina.valor_planta(ley):,.0f}")
            info.append("Accesible" if mina.es_accesible(c, f) else "No accesible (talud)")
        for t in info:
            pantalla.blit(f_chica.render(t, True, TENUE), (PANEL_X, y))
            y += 18

    # --- Mensajes ---
    y = MARGEN_Y + ALTO_MAPA + 15
    for i, texto in enumerate(mina.mensajes):
        color = TEXTO if i == len(mina.mensajes) - 1 else TENUE
        pantalla.blit(f_chica.render(texto, True, color), (MARGEN_X, y))
        y += 18

    # --- Gráfico de precio ---
    hist = mina.historial_precio[-36:]
    gx, gy, gw, gh = PANEL_X, MARGEN_Y + ALTO_MAPA + 20, 260, 90
    pygame.draw.rect(pantalla, (40, 44, 56), (gx, gy, gw, gh))
    pantalla.blit(f_chica.render("Precio Cu", True, TENUE), (gx + 4, gy + 2))
    if len(hist) > 1:
        lo, hi = 4_000, 16_000
        pts = [(gx + i * gw / (len(hist) - 1), gy + gh - (p - lo) / (hi - lo) * gh)
               for i, p in enumerate(hist)]
        pygame.draw.lines(pantalla, (230, 200, 60), False, pts, 2)

    if mina.terminado:
        capa = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        capa.fill((0, 0, 0, 170))
        pantalla.blit(capa, (0, 0))
        t = f_grande.render(mina.mensajes[-1], True, RESALTE)
        pantalla.blit(t, t.get_rect(center=(ANCHO // 2, ALTO // 2)))
        t2 = f_media.render("R para jugar de nuevo", True, TEXTO)
        pantalla.blit(t2, t2.get_rect(center=(ANCHO // 2, ALTO // 2 + 36)))


def main():
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Prototipo: mina a cielo abierto")
    fuentes = (pygame.font.Font(None, 20), pygame.font.Font(None, 24), pygame.font.Font(None, 30))
    reloj = pygame.time.Clock()
    mina = m.Mina()
    herramienta = "perforar"

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_1:
                    herramienta = "perforar"
                elif ev.key == pygame.K_2:
                    herramienta = "planta"
                elif ev.key == pygame.K_3:
                    herramienta = "botadero"
                elif ev.key == pygame.K_c:
                    mina.comprar_camion()
                elif ev.key == pygame.K_SPACE:
                    mina.pasar_mes()
                elif ev.key == pygame.K_r:
                    mina = m.Mina()
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                celda = celda_bajo_raton(ev.pos)
                if celda:
                    c, f = celda
                    if herramienta == "perforar":
                        mina.perforar(c)
                    else:
                        mina.extraer(c, f, herramienta)

        dibujar(pantalla, mina, fuentes, herramienta, celda_bajo_raton(pygame.mouse.get_pos()))
        pygame.display.flip()
        reloj.tick(30)


if __name__ == "__main__":
    main()
