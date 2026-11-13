import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from src.calculo import calcular, fecha_por_defecto
from src.excel_writer import construir_libro, nombre_archivo
from src.loader import COLUMNAS, K, N, S, V, C, P, elegir_hoja, leer_flujo

BHIA, ANA = "Babilonia Begazo, Bhia Alejandra", "Cari Cruz, Ana Silvia"
T = pd.Timestamp


def fila(asesora, codigo, cuota, venc, pago, saldo):
    return {K: asesora, C: codigo, N: cuota, V: T(venc), P: (T(pago) if pago else pd.NaT), S: saldo}


def flujo(filas):
    return pd.DataFrame(filas, columns=COLUMNAS)


def cronograma(asesora, codigo, n, venc_nov, saldo, previas_pagadas=True):
    """Cuotas n-2 (sept) y n-1 (oct) previas + la de noviembre (sin pagar) + la de diciembre (futura)."""
    pago = "2026-10-20" if previas_pagadas else None
    return [fila(asesora, codigo, f"{n-2}-1", "2026-09-05", "2026-09-20", 0.0),
            fila(asesora, codigo, f"{n-1}-1", "2026-10-05", pago, 0.0 if previas_pagadas else saldo),
            fila(asesora, codigo, f"{n}-1", venc_nov, None, saldo),
            fila(asesora, codigo, f"{n+1}-1", "2026-12-05", None, saldo)]


def ejemplo_bhia():
    """9 códigos: 3 primeras cuotas vencidas (800.27) + 6 con deuda de retraso (912.17) = 1712.44."""
    filas = []
    for cod, saldo in (("10939970A30205", 123.88), ("11015347A32435", 398.45), ("15868A32378", 277.94)):
        filas += cronograma(BHIA, cod, 11, "2026-11-05", saldo)
    for cod, saldo in (("10127380A30205", 127.71), ("10946115A30205", 172.51), ("10947227A30205", 123.88),
                       ("10948498A30296", 162.21), ("11006123A32302", 201.98), ("9632338A30205", 123.88)):
        filas += cronograma(BHIA, cod, 11, "2026-11-08", saldo, previas_pagadas=False)
    return filas


def test_ejemplo_de_bhia_1712_44_y_800_27():
    r = calcular(flujo(ejemplo_bhia()), [BHIA], "2026-11-11")
    f = r.resumen.iloc[0]
    assert f.cod_venc == 9 and round(f.saldo_venc, 2) == 1712.44
    assert f.cod_prim == 3 and round(f.saldo_prim, 2) == 800.27
    assert f.cod_ret == 6 and round(f.saldo_ret, 2) == 912.17
    assert set(r.codigos[r.codigos.primera]["codigo"]) == {"10939970A30205", "11015347A32435", "15868A32378"}


def test_el_corte_es_editable_hasta_que_dia_de_vencimiento():
    df = flujo(cronograma(BHIA, "A1", 11, "2026-11-12", 100.0))
    assert calcular(df, [BHIA], "2026-11-11").resumen.iloc[0].cod_venc == 0       # vence el 12: aún no cuenta
    r12 = calcular(df, [BHIA], "2026-11-12").resumen.iloc[0]                      # "mañana": del 1 al 12
    assert r12.cod_venc == 1 and r12.saldo_venc == 100.0 and r12.cod_prim == 1


def test_el_corte_incluye_el_dia_y_desde_el_dia_1_del_mes():
    df = flujo([fila(BHIA, "A", "5-1", "2026-11-01", None, 10.0),      # día 1: cuenta
                fila(BHIA, "B", "5-1", "2026-11-11", None, 20.0),      # día del corte: cuenta
                fila(BHIA, "C", "5-1", "2026-10-31", None, 30.0)])     # octubre: no es del mes (es deuda previa)
    r = calcular(df, [BHIA], "2026-11-11")
    assert set(r.codigos["codigo"]) == {"A", "B"} and r.resumen.iloc[0].saldo_venc == 30.0


def test_cuota_con_fecha_de_pago_no_es_vencida_y_la_fecha_de_pago_no_da_avisos():
    df = flujo(cronograma(BHIA, "A1", 11, "2026-11-05", 100.0))
    df.loc[df[N] == "11-1", P] = T("2026-11-12")                 # pagada DESPUÉS del corte: tiene fecha de pago -> no cuenta
    r = calcular(df, [BHIA], "2026-11-11")
    assert r.resumen.iloc[0].cod_venc == 0 and r.advertencias == []


def test_solo_las_asesoras_de_la_lista():
    df = flujo(cronograma(BHIA, "A1", 11, "2026-11-05", 100.0) + cronograma("Otra, O", "B1", 11, "2026-11-05", 50.0))
    r = calcular(df, [BHIA], "2026-11-11")
    assert list(r.codigos["codigo"]) == ["A1"]


def test_deuda_previa_de_cualquier_mes_anterior_no_es_primera():
    filas = cronograma(BHIA, "P1", 11, "2026-11-05", 100.0)
    filas += [fila(BHIA, "R1", "9-1", "2026-08-05", None, 80.0),         # agosto sin pagar (octubre sí pagada)
              fila(BHIA, "R1", "10-1", "2026-10-05", "2026-10-30", 0.0),
              fila(BHIA, "R1", "11-1", "2026-11-05", None, 80.0)]
    r = calcular(flujo(filas), [BHIA], "2026-11-11").codigos.set_index("codigo")
    assert bool(r.loc["P1", "primera"]) is True and bool(r.loc["R1", "primera"]) is False


def test_orden_y_asesora_sin_cuotas_aparece_con_ceros():
    df = flujo(cronograma(ANA, "A1", 11, "2026-11-05", 10.0))
    r = calcular(df, [BHIA, ANA], "2026-11-11")
    assert list(r.resumen["asesora"]) == [BHIA, ANA] and r.resumen.iloc[0].cod_venc == 0 and r.resumen.iloc[1].cod_venc == 1


def test_avisa_si_el_nombre_de_una_asesora_no_aparece_en_el_archivo():
    r = calcular(flujo(cronograma(BHIA, "A1", 11, "2026-11-05", 10.0)), [BHIA, "Nombre con error"], "2026-11-11")
    assert any("Nombre con error" in a for a in r.advertencias)


def test_fecha_por_defecto_es_el_dia_anterior():
    esperado = datetime.now(ZoneInfo("America/Lima")).date() - timedelta(days=1)
    assert fecha_por_defecto("America/Lima", 1) == esperado


def test_excel_resumen_y_codigos_con_si_no():
    r = calcular(flujo(ejemplo_bhia()), [BHIA], "2026-11-11")
    wb = construir_libro(r)
    assert wb.sheetnames == ["RESUMEN", "CODIGOS"] and nombre_archivo(r) == "CUOTAS_VENCIDAS_AL_1111.xlsx"
    ws = wb["RESUMEN"]
    assert [c.value for c in ws[5]][:7] == [BHIA, 9, 1712.44, 3, 800.27, 6, 912.17]
    assert [c.value for c in ws[6]][:5] == ["TOTAL", 9, 1712.44, 3, 800.27]
    wc = wb["CODIGOS"]
    filas = [[c.value for c in f] for f in wc.iter_rows(min_row=2, max_row=10)]
    assert all(f[2] == "SI" for f in filas)                                         # todas son cuota vencida
    assert [f[3] for f in filas].count("SI") == 3 and [f[3] for f in filas].count("NO") == 6
    assert [c.value for c in wc[11]][:6] == ["TOTAL", None, 9, 3, 1712.44, 800.27]


# ------------------------------------------------------------------ lector
def xlsx(hojas: dict) -> io.BytesIO:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        for nombre, df in hojas.items():
            df.to_excel(xw, sheet_name=nombre, index=False)
    buf.seek(0)
    return buf


def test_elegir_hoja():
    assert elegir_hoja(["prev", "FLUJO", "BASE"], ["FLUJO"]) == "FLUJO"
    assert elegir_hoja(["prev", "flujo "], ["FLUJO"]) == "flujo "
    assert elegir_hoja(["prev", "FLUJO AL CORTE"], ["FLUJO"]) == "FLUJO AL CORTE"          # una sola que contiene FLUJO
    with pytest.raises(ValueError, match="varias hojas"):
        elegir_hoja(["FLUJO METAS", "FLUJO AL CORTE"], ["FLUJO"])
    with pytest.raises(ValueError, match="No encontré"):
        elegir_hoja(["prev", "BASE"], ["FLUJO"])


def test_leer_flujo_solo_6_columnas_y_tipos():
    base = flujo(ejemplo_bhia()).assign(DNI="12345678", Email="a@b.com", Alumno="X")
    df, hoja = leer_flujo(xlsx({"prev": pd.DataFrame({"a": [1]}), "FLUJO": base}), ["FLUJO"])
    assert hoja == "FLUJO" and list(df.columns) == COLUMNAS and len(df) == len(base)
    assert pd.api.types.is_datetime64_any_dtype(df[V]) and pd.api.types.is_datetime64_any_dtype(df[P])
    assert df[P].isna().sum() == base[P].isna().sum() and df[S].sum() == pytest.approx(base[S].sum())


def test_leer_flujo_errores_claros():
    sin_col = flujo(ejemplo_bhia()).drop(columns=[S])
    with pytest.raises(ValueError, match="faltan las columnas"):
        leer_flujo(xlsx({"FLUJO": sin_col}), ["FLUJO"])
    with pytest.raises(ValueError, match="No encontré"):
        leer_flujo(xlsx({"otra": flujo(ejemplo_bhia())}), ["FLUJO"])
    with pytest.raises(ValueError, match="no tiene filas"):
        leer_flujo(xlsx({"FLUJO": flujo([])}), ["FLUJO"])


def test_cli_de_punta_a_punta(tmp_path):
    from src.main import main
    ruta = tmp_path / "flujo.xlsx"
    ruta.write_bytes(xlsx({"prev": pd.DataFrame({"a": [1]}), "FLUJO": flujo(ejemplo_bhia())}).getvalue())
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f'hojas_flujo: ["FLUJO"]\nasesoras:\n  - "{BHIA}"\n', encoding="utf-8")
    salida = tmp_path / "out" / "r.xlsx"
    assert main(["--input", str(ruta), "--config", str(cfg), "--corte", "2026-11-11", "--output", str(salida)]) == 0
    assert salida.exists()
