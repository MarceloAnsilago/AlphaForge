TIMEFRAME_OPTIONS = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]

PRIMARY_TIMEFRAME_OPTIONS = [
    "CURRENT",
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "M6",
    "M10",
    "M12",
    "M15",
    "M30",
    "H1",
    "H2",
    "H3",
    "H4",
    "H6",
    "H8",
    "H12",
    "D1",
    "W1",
    "MN1",
]

TIMEFRAMES_SELECT = {
    "Corrente": {
        "CURRENT": "Corrente",
    },
    "Minutos": {
        "M1": "1 Minuto",
        "M2": "2 Minutos",
        "M3": "3 Minutos",
        "M4": "4 Minutos",
        "M5": "5 Minutos",
        "M6": "6 Minutos",
        "M10": "10 Minutos",
        "M12": "12 Minutos",
        "M15": "15 Minutos",
        "M30": "30 Minutos",
    },
    "Horas": {
        "H1": "1 Hora",
        "H2": "2 Horas",
        "H3": "3 Horas",
        "H4": "4 Horas",
        "H6": "6 Horas",
        "H8": "8 Horas",
        "H12": "12 Horas",
    },
    "Periodos maiores": {
        "D1": "1 Dia",
        "W1": "1 Semana",
        "MN1": "1 Mes",
    },
}

MARKET_PERIOD_OPTIONS = [
    "LAST_MONTH",
    "LAST_YEAR",
    "FULL_HISTORY",
    "CUSTOM",
]

INITIAL_INDICATORS = ["SMA", "EMA", "RSI", "MACD", "BBANDS", "CCI"]

OPERATORS = {
    "GREATER_THAN": ">",
    "LESS_THAN": "<",
}

PRICE_FIELDS = ["close", "open", "high", "low"]

YES_NO_OPTIONS = ["Sim", "Nao"]

TARGET_MARKET_OPTIONS = ["B3", "FOREX"]

OPERATIONAL_TYPE_OPTIONS = ["Swing Trade", "Day Trade"]

PROCESSING_MODE_OPTIONS = ["Cada tick", "Cada segundo"]

MAX_RULES = 3

DISTANCE_CALCULATION_OPTIONS = ["Pontos", "Percentual"]

ORDER_EXECUTION_OPTIONS = ["A mercado", "Pendente"]

PENDING_PRICE_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento"]

PENDING_CANDLE_REFERENCE_OPTIONS = ["Atual", "Penultimo", "Antipenultimo"]

PENDING_EXPIRATION_OPTIONS = ["Nao expirar", 1, 2, 3, 4, 5]

STOP_TYPES = ["points"]

TAKE_TYPES = ["RR", "fixed"]
