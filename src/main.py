"""Genera el Excel de cuotas vencidas desde la línea de comandos.

    python -m src.main --input data/flujo.xlsx
    python -m src.main --input data/flujo.xlsx --corte 2026-11-12      # cuotas con vencimiento del 01/11 al 12/11

(También puedes usar la app:  streamlit run app.py)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .calculo import calcular, fecha_por_defecto
from .excel_writer import construir_libro, nombre_archivo
from .loader import leer_flujo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cuotas vencidas y primeras cuotas vencidas por asesora")
    ap.add_argument("--input", required=True, help="Excel con la hoja FLUJO")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--corte", default=None, help="Fecha de corte AAAA-MM-DD (por defecto: ayer)")
    ap.add_argument("--output", default=None, help="Ruta del Excel de salida")
    a = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    corte = a.corte or cfg.get("fecha_corte") or fecha_por_defecto(cfg.get("zona_horaria", "America/Lima"),
                                                                    int(cfg.get("dias_antes_de_hoy", 1)))
    print("Leyendo el archivo (puede tardar ~1 minuto)...")
    df, hoja = leer_flujo(a.input, cfg["hojas_flujo"])
    res = calcular(df, cfg["asesoras"], corte)
    salida = Path(a.output or f"output/{nombre_archivo(res)}")
    salida.parent.mkdir(parents=True, exist_ok=True)
    construir_libro(res).save(salida)

    print(f"✔ Generado: {salida}")
    print(f"  Hoja: {hoja} | {len(df):,} filas | cuotas con vencimiento del {res.inicio:%d/%m/%Y} al {res.fecha_corte:%d/%m/%Y}")
    r = res.resumen
    print(f"  Cuotas vencidas: {int(r.cod_venc.sum())} códigos, US$ {r.saldo_venc.sum():,.2f} | "
          f"primeras: {int(r.cod_prim.sum())} códigos, US$ {r.saldo_prim.sum():,.2f}")
    for m in res.advertencias:
        print(f"  ⚠ {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
