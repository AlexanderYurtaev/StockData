"""Соответствие фьючерса и базового актива.

Тикеры не всегда совпадают (SBRF — это акции SBER, GAZR — GAZP, TRNF —
привилегированные TRNFP), поэтому соответствие кураторское. Состав инструментов
биржи меняется: устаревшие ключи оставлены для старых дат в архиве.
"""

from typing import Literal

UnderlyingKind = Literal["share", "index"]

UNDERLYING_MAP: dict[str, str] = {
    "AFKS": "AFKS", "ALRS": "ALRS", "ASTR": "ASTR", "BANE": "BANE", "BELUGA": "BELU",
    "BSPB": "BSPB", "CBOM": "CBOM", "ENPG": "ENPG", "FEES": "FEES", "FESH": "FESH",
    "FLOT": "FLOT", "GAZR": "GAZP", "GAZPF": "GAZP", "GMKN": "GMKN", "HEAD": "HEAD",
    "HYDR": "HYDR", "IRAO": "IRAO", "ISKJ": "ABIO", "IVAT": "IVAT", "KMAZ": "KMAZ",
    "LEAS": "LEAS", "LKOH": "LKOH", "MAGN": "MAGN", "MDMG": "MDMG", "MGNT": "MGNT",
    "MOEX": "MOEX", "MTLR": "MTLR", "MTSI": "MTSS", "MVID": "MVID", "NLMK": "NLMK",
    "NOTKM": "NVTK", "OZON": "OZON", "PHOR": "PHOR", "PLZL": "PLZL", "PLZLM": "PLZL",
    "POSI": "POSI", "RASP": "RASP", "RNFT": "RNFT", "ROSN": "ROSN", "RTKM": "RTKM",
    "RTKMP": "RTKMP", "RUAL": "RUAL", "SBERF": "SBER", "SBPR": "SBERP", "SBRF": "SBER",
    "SFIN": "SFI", "SGZH": "SGZH", "SIBN": "SIBN", "SMLT": "SMLT", "SNGP": "SNGSP",
    "SNGR": "SNGS", "SOFL": "SOFL", "SPBE": "SPBE", "SVCB": "SVCB", "T": "T",
    "TATN": "TATN", "TATP": "TATP", "TRNF": "TRNFP", "UPRO": "UPRO", "VKCO": "VKCO",
    "VTBR": "VTBR", "WUSH": "WUSH", "X5": "X5", "YDEX": "YDEX",
}

INDEX_UNDERLYING: dict[str, str] = {
    "IMOEX": "IMOEX", "MIX": "IMOEX", "MXI": "IMOEX", "RTS": "RTS", "RTSM": "RTS",
}


def resolve_underlying(futures_ticker: str) -> tuple[UnderlyingKind, str] | None:
    """('share'|'index', тикер базового актива) или None, если не знаем."""
    if futures_ticker in INDEX_UNDERLYING:
        return "index", INDEX_UNDERLYING[futures_ticker]
    if futures_ticker in UNDERLYING_MAP:
        return "share", UNDERLYING_MAP[futures_ticker]
    return None
