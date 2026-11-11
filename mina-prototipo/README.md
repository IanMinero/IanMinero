# Prototipo: mina a cielo abierto

Prototipo para comprobar si la mecánica central es divertida antes de invertir en el juego completo.

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python juego.py
```

## Qué estás probando

Ves una **sección transversal** de un rajo. El yacimiento está oculto.

1. **Perforar** (tecla `1`, clic en una columna): cuesta US$60k y revela la ley de la columna, con ±10 % de error de muestreo. Los bloques cercanos se **estiman** por inverso de la distancia y aparecen en colores apagados, porque son inciertos.
2. **Extraer a planta** (`2`) o **a botadero** (`3`): solo puedes sacar bloques accesibles (talud de 45°: los tres bloques de arriba deben estar extraídos). Al extraer aparece la **ley real** y comparas con lo que estimaste (conciliación).
3. **Ley de corte**: cambia con el precio del cobre. Un bloque que hoy es estéril puede ser mineral el próximo mes.
4. **Restricciones**: la flota mueve 3 bloques por camión al mes y la planta procesa 3 bloques al mes. `C` compra un camión.
5. **Espacio** pasa el mes: se cobran los costos fijos y el precio se mueve.

Ganas si terminas los 36 meses con la mayor caja posible. Si la caja queda negativa, quiebras.

## Estructura

- `modelo.py`: toda la lógica (yacimiento, estimación, economía). No dibuja nada. Los parámetros de balance están arriba del archivo.
- `juego.py`: dibujo y controles con pygame.

La separación permite pasar `modelo.py` a GDScript (Godot) casi línea por línea.

## Preguntas a responder jugando

- ¿Es interesante decidir dónde perforar y cuánto gastar en información?
- ¿Se siente la sorpresa cuando la ley real no coincide con la estimada?
- ¿Las decisiones de mineral o estéril con precio variable generan tensión?
- ¿Qué es aburrido? (Probablemente: hacer clic bloque por bloque.)
