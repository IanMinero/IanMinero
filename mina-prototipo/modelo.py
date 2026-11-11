"""
Lógica del juego (sin gráficos).

Todo lo que es "la mina" vive aquí: el modelo de bloques, la perforación,
la estimación de leyes, la extracción, la economía y el paso del tiempo.
Al estar separado del dibujo, se puede probar solo y luego pasar a Godot.

Vista: sección transversal vertical de un rajo (open pit).
Fila 0 = superficie, fila FILAS-1 = fondo.
"""

import math
import random

# ---------------------------------------------------------------------------
# Parámetros del juego (cámbialos para balancear)
# ---------------------------------------------------------------------------
COLUMNAS = 40
FILAS = 20
TONELADAS_POR_BLOQUE = 10_000       # t
RECUPERACION = 0.88                 # recuperación metalúrgica

CAJA_INICIAL = 4_000_000            # US$
MESES_TOTALES = 36

PRECIO_BASE = 9_000                 # US$/t Cu
VOLATILIDAD_PRECIO = 0.06           # desviación mensual

COSTO_MINA_POR_T = 2.5              # US$/t en superficie
COSTO_ACARREO_POR_T_POR_FILA = 0.12  # US$/t extra por cada fila de profundidad
COSTO_PLANTA_POR_T = 18.0           # US$/t procesada
COSTO_SONDAJE = 60_000              # US$ por sondaje vertical completo
ERROR_MUESTREO = 0.10               # ±10 % de error en las leyes del sondaje

COSTO_FIJO_MENSUAL = 150_000        # administración, campamento, etc.
COSTO_CAMION_MENSUAL = 45_000
COSTO_COMPRA_CAMION = 400_000
BLOQUES_POR_CAMION = 3              # bloques que mueve un camión por mes
CAMIONES_INICIALES = 3
CAPACIDAD_PLANTA = 3                # bloques de mineral por mes

RADIO_ESTIMACION = 7                # bloques; más lejos no se estima


class Bloque:
    def __init__(self, ley_real):
        self.ley_real = ley_real        # % Cu. El jugador NO la ve hasta extraer.
        self.ley_muestreada = None      # dato de sondaje (con error)
        self.ley_estimada = None        # interpolación desde sondajes
        self.extraido = False
        self.destino = None             # "planta" o "botadero"


class Mina:
    def __init__(self, semilla=None):
        self.rng = random.Random(semilla)
        self.bloques = self._generar_yacimiento()
        self.sondajes = set()           # columnas perforadas
        self.caja = CAJA_INICIAL
        self.mes = 1
        self.precio = PRECIO_BASE
        self.historial_precio = [self.precio]
        self.camiones = CAMIONES_INICIALES
        self.movidos_este_mes = 0
        self.planta_este_mes = 0
        self.cobre_producido = 0.0      # t Cu
        self.terminado = False
        self.mensajes = ["Bienvenido. Perfora (1) para conocer el yacimiento."]

    # ------------------------------------------------------------------
    # Generación del yacimiento: un pórfido inclinado + ruido suavizado
    # ------------------------------------------------------------------
    def _generar_yacimiento(self):
        r = self.rng
        cx = r.uniform(14, 26)            # centro del cuerpo
        cy = r.uniform(8, 12)             # profundidad del centro
        inclinacion = r.uniform(-0.6, 0.6)
        largo, ancho = r.uniform(7, 10), r.uniform(3, 4.5)
        ley_max = r.uniform(1.2, 1.6)

        # Segundo cuerpo, más pequeño (una sorpresa para quien perfore)
        cx2, cy2 = r.uniform(4, 36), r.uniform(5, 16)
        ley2 = r.uniform(0.5, 1.0)

        ruido = [[r.random() for _ in range(COLUMNAS)] for _ in range(FILAS)]
        for _ in range(3):
            ruido = _suavizar(ruido)

        bloques = []
        for f in range(FILAS):
            fila = []
            for c in range(COLUMNAS):
                # coordenadas rotadas según la inclinación del cuerpo
                dx, dy = c - cx, f - cy
                u = dx * math.cos(inclinacion) + dy * math.sin(inclinacion)
                v = -dx * math.sin(inclinacion) + dy * math.cos(inclinacion)
                principal = ley_max * math.exp(-((u / largo) ** 2 + (v / ancho) ** 2))
                d2 = ((c - cx2) / 3) ** 2 + ((f - cy2) / 2) ** 2
                secundario = ley2 * math.exp(-d2)
                fondo = 0.03 + 0.15 * ruido[f][c]
                ley = (principal + secundario) * (0.7 + 0.6 * ruido[f][c]) + fondo
                # la cubierta superficial está lixiviada: casi sin cobre
                if f < 2:
                    ley *= 0.2
                fila.append(Bloque(round(ley, 3)))
            bloques.append(fila)
        return bloques

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def bloque(self, c, f):
        return self.bloques[f][c]

    def capacidad_mensual(self):
        return self.camiones * BLOQUES_POR_CAMION

    def costo_mina_bloque(self, f):
        return TONELADAS_POR_BLOQUE * (COSTO_MINA_POR_T + COSTO_ACARREO_POR_T_POR_FILA * f)

    def valor_planta(self, ley):
        """Margen de enviar un bloque de esta ley a planta (sin costo mina)."""
        cobre = TONELADAS_POR_BLOQUE * ley / 100 * RECUPERACION
        return cobre * self.precio - TONELADAS_POR_BLOQUE * COSTO_PLANTA_POR_T

    def ley_de_corte(self):
        """Ley a la que procesar un bloque ni gana ni pierde (con el precio actual)."""
        return COSTO_PLANTA_POR_T / (self.precio * RECUPERACION / 100)

    def ley_conocida(self, c, f):
        """Lo mejor que el jugador sabe del bloque: real > muestreada > estimada."""
        b = self.bloque(c, f)
        if b.extraido:
            return b.ley_real
        if b.ley_muestreada is not None:
            return b.ley_muestreada
        return b.ley_estimada

    def es_accesible(self, c, f):
        """Regla de talud a 45°: los 3 bloques de arriba deben estar extraídos."""
        if self.bloque(c, f).extraido:
            return False
        if f == 0:
            return True
        for dc in (-1, 0, 1):
            cc = c + dc
            if 0 <= cc < COLUMNAS and not self.bloque(cc, f - 1).extraido:
                return False
        return True

    # ------------------------------------------------------------------
    # Acciones del jugador. Devuelven (ok, mensaje).
    # ------------------------------------------------------------------
    def perforar(self, c):
        if self.terminado:
            return False, "El juego terminó."
        if c in self.sondajes:
            return False, "Esa columna ya está perforada."
        if self.caja < COSTO_SONDAJE:
            return False, "No alcanza la caja para perforar."
        self.caja -= COSTO_SONDAJE
        self.sondajes.add(c)
        for f in range(FILAS):
            b = self.bloque(c, f)
            if not b.extraido:
                error = self.rng.uniform(1 - ERROR_MUESTREO, 1 + ERROR_MUESTREO)
                b.ley_muestreada = round(b.ley_real * error, 3)
        self._reestimar()
        return self._msg(True, f"Sondaje en columna {c + 1}: -US${COSTO_SONDAJE:,.0f}")

    def extraer(self, c, f, destino):
        if self.terminado:
            return False, "El juego terminó."
        if not self.es_accesible(c, f):
            return False, "Bloque inaccesible: primero saca los de arriba (talud 45°)."
        if self.movidos_este_mes >= self.capacidad_mensual():
            return False, "Flota sin capacidad este mes. Pasa el mes (Espacio) o compra camiones (C)."
        if destino == "planta" and self.planta_este_mes >= CAPACIDAD_PLANTA:
            return False, "Planta llena este mes. Envía a botadero o pasa el mes."

        b = self.bloque(c, f)
        estimada = self.ley_conocida(c, f)
        costo = self.costo_mina_bloque(f)
        b.extraido = True
        b.destino = destino
        self.movidos_este_mes += 1
        self.caja -= costo

        if destino == "planta":
            self.planta_este_mes += 1
            margen = self.valor_planta(b.ley_real)
            self.caja += margen
            self.cobre_producido += TONELADAS_POR_BLOQUE * b.ley_real / 100 * RECUPERACION
            texto = f"A planta: ley real {b.ley_real:.2f}% Cu"
            if estimada is not None:
                texto += f" (estimada {estimada:.2f}%)"
            texto += f" -> resultado US${margen - costo:,.0f}"
        else:
            texto = f"A botadero: ley real {b.ley_real:.2f}% Cu, costo US${costo:,.0f}"
            if b.ley_real > self.ley_de_corte():
                texto += "  ¡Era mineral! Se perdió."
        self._reestimar()
        return self._msg(True, texto)

    def comprar_camion(self):
        if self.caja < COSTO_COMPRA_CAMION:
            return False, "No alcanza la caja para un camión."
        self.caja -= COSTO_COMPRA_CAMION
        self.camiones += 1
        return self._msg(True, f"Camión comprado. Flota: {self.camiones}.")

    def pasar_mes(self):
        if self.terminado:
            return False, "El juego terminó."
        fijo = COSTO_FIJO_MENSUAL + self.camiones * COSTO_CAMION_MENSUAL
        self.caja -= fijo
        # precio: camino aleatorio con reversión a la media
        cambio = self.rng.gauss(0, VOLATILIDAD_PRECIO)
        reversion = 0.1 * (PRECIO_BASE - self.precio) / PRECIO_BASE
        self.precio = max(4_000, min(16_000, self.precio * (1 + cambio + reversion)))
        self.historial_precio.append(self.precio)
        self.mes += 1
        self.movidos_este_mes = 0
        self.planta_este_mes = 0
        texto = f"Mes {self.mes}. Costos fijos -US${fijo:,.0f}. Precio Cu: US${self.precio:,.0f}/t"
        if self.caja < 0:
            self.terminado = True
            texto = "QUIEBRA. La caja quedó negativa. Fin del juego."
        elif self.mes > MESES_TOTALES:
            self.terminado = True
            texto = (f"Fin de la vida de la mina. Caja final US${self.caja:,.0f}, "
                     f"cobre producido {self.cobre_producido:,.0f} t")
        return self._msg(True, texto)

    # ------------------------------------------------------------------
    # Estimación: inverso de la distancia al cuadrado (IDW)
    # ------------------------------------------------------------------
    def _reestimar(self):
        muestras = []
        for f in range(FILAS):
            for c in range(COLUMNAS):
                b = self.bloque(c, f)
                if b.extraido:
                    muestras.append((c, f, b.ley_real))
                elif b.ley_muestreada is not None:
                    muestras.append((c, f, b.ley_muestreada))
        for f in range(FILAS):
            for c in range(COLUMNAS):
                b = self.bloque(c, f)
                if b.extraido or b.ley_muestreada is not None:
                    continue
                suma_p, suma_v = 0.0, 0.0
                for mc, mf, ley in muestras:
                    d2 = (mc - c) ** 2 + (mf - f) ** 2
                    if d2 <= RADIO_ESTIMACION ** 2:
                        p = 1.0 / d2
                        suma_p += p
                        suma_v += p * ley
                b.ley_estimada = round(suma_v / suma_p, 3) if suma_p else None

    def _msg(self, ok, texto):
        self.mensajes.append(texto)
        self.mensajes = self.mensajes[-6:]
        return ok, texto


def _suavizar(m):
    filas, cols = len(m), len(m[0])
    salida = []
    for f in range(filas):
        fila = []
        for c in range(cols):
            vals = [m[ff][cc]
                    for ff in range(max(0, f - 1), min(filas, f + 2))
                    for cc in range(max(0, c - 1), min(cols, c + 2))]
            fila.append(sum(vals) / len(vals))
        salida.append(fila)
    # re-escalar a 0..1
    lo = min(min(r) for r in salida)
    hi = max(max(r) for r in salida)
    return [[(v - lo) / (hi - lo) for v in r] for r in salida]
