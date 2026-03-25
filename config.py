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

PENDING_POSITION_OPTIONS = ["Referencia de preco", "Media"]

PENDING_PRICE_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento", "Corpo", "Pavios"]

PENDING_CANDLE_REFERENCE_OPTIONS = ["Atual", "Penultimo", "Antipenultimo"]

STOP_CANDLE_REFERENCE_OPTIONS = ["Ultimo", "Penultimo", "Antepenultimo"]
STOP_CALCULATION_OPTIONS = ["Media", "Multiplicar"]

PENDING_EXPIRATION_OPTIONS = ["Nao expirar", 1, 2, 3, 4, 5]

STOP_TYPES = ["points", "percentual"]

TAKE_TYPES = ["RR", "fixed"]
