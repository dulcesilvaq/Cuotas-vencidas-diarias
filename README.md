# Cuotas vencidas y primeras cuotas vencidas

Lee la hoja **FLUJO** de tu Excel y entrega, por asesora, las **cuotas vencidas** y las **primeras cuotas vencidas**.
Siempre se usa la **Fecha de Vencimiento ACTUAL**.

## Qué calcula
1. Filtra la hoja FLUJO por asesora (lista en `config.yaml`).
2. Se queda con las cuotas cuya Fecha de Vencimiento ACTUAL va **del día 1 del mes de la fecha de corte hasta la fecha de corte (incluida)**.
3. Quita las que **tienen fecha de pago** (columna *Fecha Pago*). Lo que queda son las **cuotas vencidas**; se suma *Saldo Pendiente Dolar*.
4. Un código es **primera cuota vencida** si no tiene **ninguna cuota sin pagar con vencimiento anterior al día 1 de ese mes**
   (todo lo anterior está pagado: ej. su cuota vencida es la 10-1 y la 9-1, de octubre, está pagada).
   Su monto es el saldo de su cuota vencida. El resto son **cuotas con deuda de retraso**.

**Ejemplo (Bhia, corte 11/11):** 9 códigos con cuota vencida = US$ 1,712.44. De ellos, 3 son primeras cuotas vencidas = US$ 800.27.

## Fecha de corte
Es "hasta qué día de vencimiento" se cuenta. Por defecto es **ayer** (hoy 12 → corte 11) en la zona horaria `America/Lima`.
Mañana puedes poner 12 y se cuentan las cuotas con vencimiento del 1 al 12. Se edita:
- en la **app**: campo *Fecha de corte*;
- en la **línea de comandos**: `--corte 2026-11-12`;
- en **`config.yaml`**: `fecha_corte: "2026-11-12"` (déjalo en `null` para usar ayer).

## Usarlo
### App web (Streamlit)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Subes el Excel (detecta solo la hoja FLUJO), eliges la fecha de corte, revisas las asesoras y pulsas **Generar**. La primera lectura de
un archivo grande tarda ~1 minuto; si luego cambias la fecha, recalcula al instante. Descargas el Excel.

### Línea de comandos
```bash
python -m src.main --input data/flujo.xlsx                  # corte = ayer
python -m src.main --input data/flujo.xlsx --corte 2026-11-12
```
El Excel queda en `output/CUOTAS_VENCIDAS_AL_DDMM.xlsx`.

## Excel de salida
- **`RESUMEN`**: por asesora, códigos y US$ de cuotas vencidas, de primeras cuotas vencidas y de cuotas con deuda de retraso, más el total.
- **`CODIGOS`**: una fila por código con `Cuota vencida` (SI) y `Primera cuota vencida` (SI / NO), los saldos y el nro de cuota con su fecha. Tiene filtros.

## Publicar en Streamlit
1. Sube el **contenido** de esta carpeta a un repositorio de GitHub (el `.gitignore` evita subir tus Excel).
2. En <https://share.streamlit.io> → **Create app** → elige el repositorio, la rama `main` y como archivo principal **`app.py`**.

## Privacidad
El archivo trae DNI, correos y teléfonos. Este programa **solo lee 6 columnas**: *Coordinadora Cobranza*, *Fecha Vencimiento Actual*,
*Fecha Pago*, *Saldo Pendiente Dolar*, *Código Matricula* y *Nro Cuota*. El resto nunca se carga. **No subas el Excel a GitHub.**

## Pruebas
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Estructura
```
app.py               <- app web
config.yaml          <- hoja, fecha de corte, asesoras
src/loader.py        <- detecta y lee la hoja FLUJO (6 columnas, poca memoria)
src/calculo.py       <- cuotas vencidas y primeras cuotas vencidas
src/excel_writer.py  <- Excel de salida
src/main.py          <- línea de comandos
tests/               <- pruebas (incluye el ejemplo de Bhia)
```
