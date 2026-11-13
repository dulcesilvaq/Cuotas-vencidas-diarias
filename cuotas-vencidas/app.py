"""App web (Streamlit): sube el Excel con la hoja FLUJO, elige hasta qué día de vencimiento y descarga el Excel.

Ejecutar en local:   streamlit run app.py
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from src.calculo import calcular, fecha_por_defecto
from src.excel_writer import construir_libro, nombre_archivo
from src.loader import K, leer_flujo

CFG = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

st.set_page_config(page_title="Cuotas vencidas", page_icon="📌", layout="wide")
st.title("📌 Cuotas vencidas y primeras cuotas vencidas")
st.caption("Sube el Excel con la hoja FLUJO. Se usa siempre la **Fecha de Vencimiento ACTUAL**. El archivo se procesa en "
           "memoria y solo se leen 6 columnas (no se leen DNI, correos ni teléfonos).")


@st.cache_data(show_spinner="Leyendo el archivo (puede tardar ~1 minuto)...", max_entries=2)
def _leer(contenido: bytes, hojas: tuple):
    return leer_flujo(io.BytesIO(contenido), list(hojas))


# ------------------------------------------------------------------ 1. archivo
archivo = st.file_uploader("1 · Excel con la hoja FLUJO", type=["xlsx", "xlsm"])
df = None
if archivo is not None:
    try:
        df, hoja = _leer(archivo.getvalue(), tuple(CFG["hojas_flujo"]))
        st.success(f"Hoja detectada: **{hoja}** · {len(df):,} filas")
    except Exception as e:  # noqa: BLE001
        st.error(str(e))
        st.stop()

# ------------------------------------------------------------------ 2. fecha de corte
cfg_fecha = CFG.get("fecha_corte")
fecha_def = (date.fromisoformat(str(cfg_fecha)) if cfg_fecha
             else fecha_por_defecto(CFG.get("zona_horaria", "America/Lima"), int(CFG.get("dias_antes_de_hoy", 1))))
fecha_corte = st.date_input("2 · Fecha de corte: se cuentan las cuotas con vencimiento hasta este día (incluido)",
                            value=fecha_def, format="DD/MM/YYYY")
st.caption(f"Cuotas con vencimiento del **{fecha_corte.replace(day=1):%d/%m/%Y}** al **{fecha_corte:%d/%m/%Y}** "
           f"y sin fecha de pago. Por defecto es el día anterior a hoy.")

# ------------------------------------------------------------------ 3. asesoras
st.subheader("3 · Asesoras")
st.caption("El nombre debe ser idéntico a la columna *Coordinadora Cobranza*. El orden es el orden del reporte.")
editado = st.data_editor(pd.DataFrame({"Asesora": CFG["asesoras"]}), num_rows="dynamic", hide_index=True, width="stretch")
if df is not None:
    with st.expander("Coordinadoras que aparecen en el archivo (para copiar el nombre exacto)"):
        st.dataframe(df[K].value_counts().rename_axis("Coordinadora Cobranza").reset_index(name="Filas"),
                     hide_index=True, width="stretch")

# ------------------------------------------------------------------ generar
st.divider()
if st.button("▶ Generar", type="primary", disabled=df is None):
    ases = list(dict.fromkeys(str(a).strip() for a in editado["Asesora"].dropna() if str(a).strip()))
    if not ases:
        st.error("Agrega al menos una asesora.")
    else:
        res = calcular(df, ases, fecha_corte)
        buf = io.BytesIO()
        construir_libro(res).save(buf)
        st.session_state["res"] = {"res": res, "excel": buf.getvalue(), "nombre": nombre_archivo(res)}
elif df is None:
    st.info("Sube el Excel para habilitar el botón.")

# ------------------------------------------------------------------ resultado
out = st.session_state.get("res")
if out:
    res = out["res"]
    r = res.resumen
    st.success(f"Listo · cuotas con vencimiento del {res.inicio:%d/%m/%Y} al {res.fecha_corte:%d/%m/%Y}")
    for m in res.advertencias:
        st.warning(m)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Códigos con cuota vencida", int(r.cod_venc.sum()))
    c2.metric("Cuotas vencidas US$", f"{r.saldo_venc.sum():.2f}")
    c3.metric("Códigos primeras cuotas", int(r.cod_prim.sum()))
    c4.metric("Primeras cuotas vencidas US$", f"{r.saldo_prim.sum():.2f}")
    st.download_button("⬇ Descargar Excel", out["excel"], file_name=out["nombre"], type="primary",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    t1, t2 = st.tabs(["Resumen por asesora", "Códigos"])
    with t1:
        vista = r.rename(columns={"asesora": "Asesora", "cod_venc": "Códigos con cuota vencida", "saldo_venc": "Cuotas vencidas US$",
                                  "cod_prim": "Códigos primeras cuotas vencidas", "saldo_prim": "Primeras cuotas vencidas US$",
                                  "cod_ret": "Códigos con deuda de retraso", "saldo_ret": "Cuotas con deuda de retraso US$"})
        st.dataframe(vista.style.format({c: "{:.2f}" for c in vista.columns if "US$" in c}), hide_index=True, width="stretch")
    with t2:
        v = res.codigos.assign(**{"Cuota vencida": "SI"}).copy()
        v["Primera cuota vencida"] = v["primera"].map({True: "SI", False: "NO"})
        v = v.rename(columns={"asesora": "Asesora", "codigo": "Código Matricula", "saldo": "Saldo cuota vencida US$",
                              "saldo_primera": "Saldo primera cuota vencida US$", "cuotas": "Cuota vencida (nro y fecha)"})
        st.dataframe(v[["Asesora", "Código Matricula", "Cuota vencida", "Primera cuota vencida", "Saldo cuota vencida US$",
                        "Saldo primera cuota vencida US$", "Cuota vencida (nro y fecha)"]], hide_index=True, width="stretch")
