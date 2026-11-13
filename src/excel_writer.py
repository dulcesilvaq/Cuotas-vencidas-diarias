"""Excel de salida: RESUMEN (sumas por asesora) y CODIGOS (un código por fila, con SI / NO)."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .calculo import Resultado

F = "Arial"
AZUL = PatternFill("solid", start_color="1F3864", end_color="1F3864")
CLARO = PatternFill("solid", start_color="DDEBF7", end_color="DDEBF7")
VERDE = PatternFill("solid", start_color="E2EFDA", end_color="E2EFDA")
_l = Side(style="thin", color="8EA9DB")
BORDE = Border(left=_l, right=_l, top=_l, bottom=_l)


def nombre_archivo(res: Resultado) -> str:
    return f"CUOTAS_VENCIDAS_AL_{res.fecha_corte:%d%m}.xlsx"


def _encabezado(ws, fila, textos, alto):
    for j, t in enumerate(textos, start=1):
        c = ws.cell(fila, j, t)
        c.font = Font(name=F, bold=True, size=10, color="FFFFFF")
        c.fill, c.border = AZUL, BORDE
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[fila].height = alto


def construir_libro(res: Resultado) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "RESUMEN"
    ws["A1"] = f"Cuotas vencidas del {res.inicio:%d/%m/%Y} al {res.fecha_corte:%d/%m/%Y} (cuotas sin fecha de pago)"
    ws["A1"].font = Font(name=F, bold=True, size=12)
    ws["A2"] = ("Primera cuota vencida = el código no tiene ninguna cuota sin pagar con vencimiento anterior al "
                f"{res.inicio:%d/%m/%Y}; su deuda es solo la cuota vencida de este mes. "
                "Se usa siempre la Fecha de Vencimiento ACTUAL.")
    ws["A2"].font = Font(name=F, italic=True, size=9, color="595959")
    _encabezado(ws, 4, ["Asesora", "Códigos con cuota vencida", "Cuotas vencidas US$", "Códigos primeras cuotas vencidas",
                        "Primeras cuotas vencidas US$", "Códigos con deuda de retraso", "Cuotas con deuda de retraso US$"], 46)
    r = res.resumen
    filas = [(x.asesora, x.cod_venc, x.saldo_venc, x.cod_prim, x.saldo_prim, x.cod_ret, x.saldo_ret) for x in r.itertuples()]
    total = ("TOTAL", int(r.cod_venc.sum()), r.saldo_venc.sum(), int(r.cod_prim.sum()), r.saldo_prim.sum(),
             int(r.cod_ret.sum()), r.saldo_ret.sum())
    for i, f in enumerate(filas + [total], start=5):
        es_t = f[0] == "TOTAL"
        for j, v in enumerate(f, start=1):
            c = ws.cell(i, j, round(float(v), 2) if j in (3, 5, 7) else v)
            c.font = Font(name=F, size=10, bold=es_t)
            c.border = BORDE
            if es_t:
                c.fill = CLARO
            if j in (3, 5, 7):
                c.number_format = "0.00"
            if j > 1:
                c.alignment = Alignment(horizontal="right")
    ws.column_dimensions["A"].width = 40
    for j in range(2, 8):
        ws.column_dimensions[get_column_letter(j)].width = 20

    wc = wb.create_sheet("CODIGOS")
    _encabezado(wc, 1, ["Asesora", "Código Matricula", "Cuota vencida", "Primera cuota vencida", "Saldo cuota vencida US$",
                        "Saldo primera cuota vencida US$", "Cuota vencida (nro y fecha de vencimiento)"], 34)
    cod = res.codigos
    for i, x in enumerate(cod.itertuples(index=False), start=2):
        vals = [x.asesora, x.codigo, "SI", "SI" if x.primera else "NO", round(x.saldo, 2),
                round(x.saldo_primera, 2), x.cuotas]
        for j, v in enumerate(vals, start=1):
            c = wc.cell(i, j, v)
            c.font = Font(name=F, size=10, bold=(v == "SI"))
            c.border = BORDE
            if j in (3, 4):
                c.alignment = Alignment(horizontal="center")
            if v == "SI":
                c.fill = VERDE
            if j in (5, 6):
                c.number_format = "0.00"
    n = len(cod)
    if n:
        wc.auto_filter.ref = f"A1:G{n + 1}"
    t = n + 2
    wc.cell(t, 1, "TOTAL")
    wc.cell(t, 3, int(n))
    wc.cell(t, 4, int(cod["primera"].sum()) if n else 0)
    wc.cell(t, 5, round(float(cod["saldo"].sum()), 2) if n else 0)
    wc.cell(t, 6, round(float(cod["saldo_primera"].sum()), 2) if n else 0)
    for j in range(1, 8):
        c = wc.cell(t, j)
        c.font = Font(name=F, size=10, bold=True)
        c.fill, c.border = CLARO, BORDE
        if j in (3, 4):
            c.alignment = Alignment(horizontal="center")
        if j in (5, 6):
            c.number_format = "0.00"
    for j, w in enumerate([40, 18, 14, 18, 18, 22, 44], start=1):
        wc.column_dimensions[get_column_letter(j)].width = w
    wc.freeze_panes = "C2"
    return wb
