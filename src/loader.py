"""Lectura de la hoja FLUJO (solo las 6 columnas necesarias, en streaming: poca memoria)."""
from __future__ import annotations

import pandas as pd
from openpyxl import load_workbook

K = "Coordinadora Cobranza"
V = "Fecha Vencimiento Actual"
P = "Fecha Pago"
S = "Saldo Pendiente Dolar"
C = "Código Matricula"
N = "Nro Cuota"
COLUMNAS = [K, V, P, S, C, N]


def elegir_hoja(nombres: list[str], candidatas: list[str]) -> str:
    """Hoja del flujo: nombre exacto (sin importar mayúsculas) o la única hoja que contenga 'FLUJO'."""
    limpio = {n.strip().lower(): n for n in nombres}
    for c in candidatas:
        if c.strip().lower() in limpio:
            return limpio[c.strip().lower()]
    parecidas = [n for n in nombres if any(c.strip().lower() in n.lower() for c in candidatas)]
    if len(parecidas) == 1:
        return parecidas[0]
    if len(parecidas) > 1:
        raise ValueError(f"Hay varias hojas que parecen el flujo {parecidas}. Indica cuál en 'hojas_flujo' (config.yaml).")
    raise ValueError(f"No encontré la hoja del flujo ({candidatas}). Hojas del archivo: {nombres}")


def leer_flujo(archivo, candidatas: list[str]) -> tuple[pd.DataFrame, str]:
    """Lee la hoja FLUJO de `archivo` (ruta o archivo en memoria). Devuelve (DataFrame, nombre de la hoja)."""
    if hasattr(archivo, "seek"):
        archivo.seek(0)
    wb = load_workbook(archivo, read_only=True, data_only=True)
    try:
        hoja = elegir_hoja(wb.sheetnames, candidatas)
        ws = wb[hoja]
        ws.reset_dimensions()
        filas = ws.iter_rows(values_only=True)
        cab = [str(c).strip() if c is not None else "" for c in next(filas, [])]
        faltan = [c for c in COLUMNAS if c not in cab]
        if faltan:
            raise ValueError(f"En la hoja '{hoja}' faltan las columnas: {faltan}. "
                             f"(Los encabezados deben estar en la primera fila.)")
        idx = [cab.index(c) for c in COLUMNAS]
        datos = [tuple(f[i] if i < len(f) else None for i in idx) for f in filas if f and any(v is not None for v in f)]
    finally:
        wb.close()
    if not datos:
        raise ValueError(f"La hoja '{hoja}' no tiene filas de datos.")

    df = pd.DataFrame(datos, columns=COLUMNAS)
    for c in (V, P):
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True).dt.normalize()
    df[S] = pd.to_numeric(df[S], errors="coerce")
    for c in (K, C, N):
        df[c] = df[c].astype("string").str.strip().astype(object)
    return df, hoja
