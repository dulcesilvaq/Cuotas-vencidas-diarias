"""Cuotas vencidas y primeras cuotas vencidas por asesora.

CUOTA VENCIDA        = cuota de la asesora con Fecha de Vencimiento ACTUAL entre el día 1 del mes de la fecha de corte y
                       la fecha de corte (incluida) y SIN fecha de pago. Se suma 'Saldo Pendiente Dolar'.
PRIMERA CUOTA VENCIDA = el código con cuota vencida NO tiene ninguna cuota sin pagar con vencimiento ACTUAL anterior al
                       día 1 de ese mes (todo lo anterior está pagado; solo le falta la cuota de este mes).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from .loader import C, K, N, P, S, V


@dataclass
class Resultado:
    fecha_corte: pd.Timestamp
    inicio: pd.Timestamp
    codigos: pd.DataFrame           # una fila por código con cuota vencida
    resumen: pd.DataFrame           # una fila por asesora
    advertencias: list = field(default_factory=list)


def fecha_por_defecto(zona: str = "America/Lima", dias_antes: int = 1) -> date:
    """Hoy menos `dias_antes` en la zona horaria indicada (ej.: hoy 12 -> corte 11)."""
    return datetime.now(ZoneInfo(zona)).date() - timedelta(days=dias_antes)


def calcular(df: pd.DataFrame, asesoras: list[str], fecha_corte) -> Resultado:
    corte = pd.Timestamp(fecha_corte).normalize()
    ini = corte.replace(day=1)
    adv: list[str] = []

    presentes = set(df[K].dropna())
    ausentes = [a for a in asesoras if a not in presentes]
    if ausentes:
        adv.append("Asesoras de tu lista que NO aparecen en el archivo (revisa que el nombre sea idéntico): "
                   + "; ".join(ausentes) + ".")

    venc = df[df[K].isin(asesoras) & (df[V] >= ini) & (df[V] <= corte) & df[P].isna()].copy()

    # primera cuota vencida: ninguna cuota sin pagar con vencimiento actual anterior al mes de corte
    codigos_venc = set(venc[C])
    prev = df[df[C].isin(codigos_venc) & (df[V] < ini) & df[P].isna()]
    con_deuda_previa = set(prev[C])

    venc["_txt"] = venc[N].astype(str) + " (" + venc[V].dt.strftime("%d/%m") + ")"
    cod = (venc.groupby(C).agg(asesora=(K, "first"), saldo=(S, "sum"), cuotas=("_txt", lambda s: ", ".join(s)))
               .reset_index().rename(columns={C: "codigo"}))
    cod["primera"] = ~cod["codigo"].isin(con_deuda_previa)
    cod["saldo_primera"] = cod["saldo"].where(cod["primera"], 0.0)
    orden = {a: i for i, a in enumerate(asesoras)}
    cod["_o"] = cod["asesora"].map(orden)
    cod = cod.sort_values(["_o", "primera", "codigo"], ascending=[True, False, True]).drop(columns="_o").reset_index(drop=True)

    filas = []
    for a in asesoras:
        d = cod[cod["asesora"] == a]
        p_, o = d[d["primera"]], d[~d["primera"]]
        filas.append(dict(asesora=a, cod_venc=len(d), saldo_venc=float(d["saldo"].sum()),
                          cod_prim=len(p_), saldo_prim=float(p_["saldo"].sum()),
                          cod_ret=len(o), saldo_ret=float(o["saldo"].sum())))
    return Resultado(corte, ini, cod, pd.DataFrame(filas), adv)
