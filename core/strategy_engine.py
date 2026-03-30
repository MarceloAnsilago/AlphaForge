from __future__ import annotations

from collections import OrderedDict
from typing import Any

import math

import pandas as pd


AND_CONNECTORS = {"SE", "E", "E SE", "E Tambem"}
OR_CONNECTORS = {"OU", "OU SE", "OU Tambem"}

PRICE_MODE_FIELD_MAP = {
    "Fechamento": "close",
    "Abertura": "open",
    "Maximo": "high",
    "Minimo": "low",
}


def _empty_series(candles: pd.DataFrame) -> pd.Series:
    return pd.Series(index=candles.index, dtype="float64")


def _false_series(candles: pd.DataFrame) -> pd.Series:
    return pd.Series(False, index=candles.index, dtype="bool")


def _as_float_series(value: float, candles: pd.DataFrame) -> pd.Series:
    return pd.Series(float(value), index=candles.index, dtype="float64")


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, float("nan"))


def _apply_offset(series: pd.Series, offset: int) -> pd.Series:
    return series.shift(int(offset))


def _resolve_price_mode_field(price_mode: str | None) -> str:
    if price_mode in PRICE_MODE_FIELD_MAP:
        return PRICE_MODE_FIELD_MAP[price_mode]
    return "close"


def _resolve_price_mode_series(candles: pd.DataFrame, price_mode: str | None) -> pd.Series:
    if price_mode in PRICE_MODE_FIELD_MAP:
        return candles[_resolve_price_mode_field(price_mode)].astype(float)
    if price_mode == "Mediano":
        return ((candles["high"] + candles["low"]) / 2).astype(float)
    if price_mode == "Tipico":
        return ((candles["high"] + candles["low"] + candles["close"]) / 3).astype(float)
    if price_mode == "Medio":
        return ((candles["high"] + candles["low"] + (candles["close"] * 2)) / 4).astype(float)
    return candles["close"].astype(float)


def _resolve_volume_series(candles: pd.DataFrame, volume_type: str | None) -> pd.Series:
    if volume_type == "Volume Real":
        if "real_volume" in candles.columns:
            return candles["real_volume"].astype(float)
        if "volume" in candles.columns:
            return candles["volume"].astype(float)
    if "tick_volume" in candles.columns:
        return candles["tick_volume"].astype(float)
    if "volume" in candles.columns:
        return candles["volume"].astype(float)
    if "real_volume" in candles.columns:
        return candles["real_volume"].astype(float)
    return _empty_series(candles)


def _resolve_special_source(source: dict[str, Any], candles: pd.DataFrame) -> pd.Series:
    source_value = source["value"]
    if source_value == "CANDLE_SIZE":
        return _apply_offset((candles["high"] - candles["low"]).astype(float), source.get("candle_offset", 0))
    if source_value == "CANDLE_BODY":
        return _apply_offset((candles["close"] - candles["open"]).abs().astype(float), source.get("candle_offset", 0))
    if source_value in {"DAY_OPEN", "DAY_HIGH", "DAY_LOW", "DAY_CLOSE"}:
        grouped = candles.groupby(candles["time"].dt.floor("D"))
        if source_value == "DAY_OPEN":
            series = grouped["open"].transform("first")
        elif source_value == "DAY_HIGH":
            series = grouped["high"].transform("max")
        elif source_value == "DAY_LOW":
            series = grouped["low"].transform("min")
        else:
            series = grouped["close"].transform("last")
        return _apply_offset(series.astype(float), source.get("candle_offset", 0))
    return _empty_series(candles)


def _weighted_moving_average(series: pd.Series, period: int) -> pd.Series:
    weights = list(range(1, period + 1))
    return series.rolling(period).apply(
        lambda values: sum(weight * value for weight, value in zip(weights, values)) / sum(weights),
        raw=True,
    )


def _moving_average(series: pd.Series, period: int, ma_type: str) -> pd.Series:
    normalized_type = ma_type.upper()
    if normalized_type == "SMA":
        return series.rolling(period).mean()
    if normalized_type == "EMA":
        return series.ewm(span=period, adjust=False).mean()
    if normalized_type == "SMMA":
        return series.ewm(alpha=1 / period, adjust=False).mean()
    if normalized_type == "LWMA":
        return _weighted_moving_average(series, period)
    return series.rolling(period).mean()


def _extract_ma_type(parameters: dict[str, Any], default: str = "SMA") -> str:
    raw_type = str(parameters.get("ma_type", default))
    if "EMA" in raw_type:
        return "EMA"
    if "SMMA" in raw_type:
        return "SMMA"
    if "LWMA" in raw_type:
        return "LWMA"
    return "SMA"


def _indicator_input_series(candles: pd.DataFrame, parameters: dict[str, Any]) -> pd.Series:
    return _resolve_price_mode_series(candles, parameters.get("price_mode"))


def _median_price(candles: pd.DataFrame) -> pd.Series:
    return ((candles["high"] + candles["low"]) / 2).astype(float)


def _typical_price(candles: pd.DataFrame) -> pd.Series:
    return ((candles["high"] + candles["low"] + candles["close"]) / 3).astype(float)


def _true_range(candles: pd.DataFrame) -> pd.Series:
    previous_close = candles["close"].shift(1)
    components = pd.concat(
        [
            (candles["high"] - candles["low"]).abs(),
            (candles["high"] - previous_close).abs(),
            (candles["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return components.max(axis=1).astype(float)


def _compute_atr(candles: pd.DataFrame, period: int) -> pd.Series:
    return _true_range(candles).ewm(alpha=1 / period, adjust=False).mean()


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, adjust=False).mean()
    rs = _safe_divide(avg_gain, avg_loss)
    return 100 - (100 / (1 + rs))


def _compute_cci(candles: pd.DataFrame, period: int) -> pd.Series:
    typical_price = _typical_price(candles)
    moving_average = typical_price.rolling(period).mean()
    mean_deviation = (typical_price - moving_average).abs().rolling(period).mean()
    denominator = (0.015 * mean_deviation).replace(0, float("nan"))
    return (typical_price - moving_average) / denominator


def _compute_bbands(series: pd.Series, period: int, deviation: float) -> pd.DataFrame:
    middle = series.rolling(period).mean()
    std = series.rolling(period).std(ddof=0)
    upper = middle + (std * deviation)
    lower = middle - (std * deviation)
    return pd.DataFrame({"Superior": upper, "Media": middle, "Inferior": lower})


def _compute_macd(series: pd.Series, fast_period: int, slow_period: int, signal_period: int) -> pd.DataFrame:
    fast_ema = series.ewm(span=fast_period, adjust=False).mean()
    slow_ema = series.ewm(span=slow_period, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {
            "Linha MACD": macd_line,
            "Linha de sinal": signal_line,
            "Histograma": histogram,
        }
    )


def _compute_keltner(candles: pd.DataFrame, parameters: dict[str, Any]) -> pd.DataFrame:
    period = _coerce_int(parameters.get("period"), 20)
    deviation = _coerce_float(parameters.get("deviation"), 2.0)
    ma_type = _extract_ma_type(parameters, default="EMA")
    middle = _moving_average(_typical_price(candles), period, ma_type)
    atr = _compute_atr(candles, period)
    return pd.DataFrame(
        {
            "Superior": middle + (atr * deviation),
            "Media": middle,
            "Inferior": middle - (atr * deviation),
        }
    )


def _compute_donchian(candles: pd.DataFrame, period: int) -> pd.DataFrame:
    upper = candles["high"].rolling(period).max()
    lower = candles["low"].rolling(period).min()
    middle = (upper + lower) / 2
    return pd.DataFrame({"Superior": upper, "Meio": middle, "Inferior": lower})


def _compute_regression(series: pd.Series, period: int) -> pd.Series:
    x = list(range(period))

    def _endpoint(values: list[float]) -> float:
        y = list(values)
        if len(y) != period:
            return float("nan")
        x_mean = sum(x) / period
        y_mean = sum(y) / period
        numerator = sum((xv - x_mean) * (yv - y_mean) for xv, yv in zip(x, y))
        denominator = sum((xv - x_mean) ** 2 for xv in x)
        if denominator == 0:
            return float("nan")
        slope = numerator / denominator
        intercept = y_mean - (slope * x_mean)
        return intercept + (slope * (period - 1))

    return series.rolling(period).apply(_endpoint, raw=True)


def _compute_mean_deviation(series: pd.Series, period: int, ma_type: str) -> pd.Series:
    moving_average = _moving_average(series, period, ma_type)
    return (series - moving_average).abs().rolling(period).mean()


def _compute_envelopes(series: pd.Series, period: int, ma_type: str, deviation: float) -> pd.DataFrame:
    middle = _moving_average(series, period, ma_type)
    deviation_factor = deviation / 100
    return pd.DataFrame(
        {
            "Superior": middle * (1 + deviation_factor),
            "Media": middle,
            "Inferior": middle * (1 - deviation_factor),
        }
    )


def _compute_stochastic(candles: pd.DataFrame, parameters: dict[str, Any]) -> pd.DataFrame:
    k_period = _coerce_int(parameters.get("k_period"), 5)
    d_period = _coerce_int(parameters.get("d_period"), 3)
    slowing = _coerce_int(parameters.get("slowing"), 3)
    ma_type = _extract_ma_type(parameters)
    stochastic_type = str(parameters.get("stochastic_type", "Minimo/Maximo"))

    if stochastic_type == "Fechamento/Fechamento":
        lowest = candles["close"].rolling(k_period).min()
        highest = candles["close"].rolling(k_period).max()
    else:
        lowest = candles["low"].rolling(k_period).min()
        highest = candles["high"].rolling(k_period).max()

    raw_k = 100 * _safe_divide(candles["close"] - lowest, highest - lowest)
    percent_k = _moving_average(raw_k.astype(float), slowing, ma_type)
    percent_d = _moving_average(percent_k.astype(float), d_period, ma_type)
    return pd.DataFrame({"%K": percent_k, "%D": percent_d})


def _compute_stddev(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).std(ddof=0)


def _compute_parabolic_sar(candles: pd.DataFrame, step: float, maximum: float) -> pd.Series:
    if candles.empty:
        return _empty_series(candles)

    highs = candles["high"].astype(float).tolist()
    lows = candles["low"].astype(float).tolist()
    sar_values = [lows[0]]
    is_uptrend = True
    acceleration = step
    extreme_point = highs[0]

    for index in range(1, len(candles)):
        previous_sar = sar_values[-1]
        current_sar = previous_sar + (acceleration * (extreme_point - previous_sar))

        if is_uptrend:
            current_sar = min(current_sar, lows[index - 1])
            if index > 1:
                current_sar = min(current_sar, lows[index - 2])
            if lows[index] < current_sar:
                is_uptrend = False
                current_sar = extreme_point
                extreme_point = lows[index]
                acceleration = step
            else:
                if highs[index] > extreme_point:
                    extreme_point = highs[index]
                    acceleration = min(acceleration + step, maximum)
        else:
            current_sar = max(current_sar, highs[index - 1])
            if index > 1:
                current_sar = max(current_sar, highs[index - 2])
            if highs[index] > current_sar:
                is_uptrend = True
                current_sar = extreme_point
                extreme_point = highs[index]
                acceleration = step
            else:
                if lows[index] < extreme_point:
                    extreme_point = lows[index]
                    acceleration = min(acceleration + step, maximum)

        sar_values.append(current_sar)

    return pd.Series(sar_values, index=candles.index, dtype="float64")


def _compute_fractal(candles: pd.DataFrame) -> pd.DataFrame:
    upper = pd.Series(float("nan"), index=candles.index, dtype="float64")
    lower = pd.Series(float("nan"), index=candles.index, dtype="float64")

    for index in range(2, len(candles) - 2):
        high_value = float(candles.iloc[index]["high"])
        low_value = float(candles.iloc[index]["low"])

        if high_value > float(candles.iloc[index - 1]["high"]) and high_value > float(candles.iloc[index - 2]["high"]):
            if high_value > float(candles.iloc[index + 1]["high"]) and high_value > float(candles.iloc[index + 2]["high"]):
                upper.iloc[index] = high_value

        if low_value < float(candles.iloc[index - 1]["low"]) and low_value < float(candles.iloc[index - 2]["low"]):
            if low_value < float(candles.iloc[index + 1]["low"]) and low_value < float(candles.iloc[index + 2]["low"]):
                lower.iloc[index] = low_value

    return pd.DataFrame({"Superior": upper, "Inferior": lower})


def _compute_obv(candles: pd.DataFrame, volume_type: str | None) -> pd.Series:
    volume = _resolve_volume_series(candles, volume_type)
    direction = candles["close"].diff().fillna(0).apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
    return (direction * volume).cumsum().astype(float)


def _compute_accumulation_distribution(candles: pd.DataFrame, volume_type: str | None) -> pd.Series:
    volume = _resolve_volume_series(candles, volume_type)
    spread = (candles["high"] - candles["low"]).replace(0, float("nan"))
    money_flow_multiplier = ((candles["close"] - candles["low"]) - (candles["high"] - candles["close"])) / spread
    money_flow_volume = money_flow_multiplier.fillna(0) * volume
    return money_flow_volume.cumsum().astype(float)


def _compute_mfi(candles: pd.DataFrame, period: int, volume_type: str | None) -> pd.Series:
    typical_price = _typical_price(candles)
    volume = _resolve_volume_series(candles, volume_type)
    raw_money_flow = typical_price * volume
    price_delta = typical_price.diff()
    positive_flow = raw_money_flow.where(price_delta > 0, 0.0).rolling(period).sum()
    negative_flow = raw_money_flow.where(price_delta < 0, 0.0).abs().rolling(period).sum()
    money_ratio = _safe_divide(positive_flow, negative_flow)
    return 100 - (100 / (1 + money_ratio))


def _compute_cmo(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0).rolling(period).sum()
    losses = (-delta.clip(upper=0)).rolling(period).sum()
    return 100 * _safe_divide(gains - losses, gains + losses)


def _compute_vidya(series: pd.Series, cmo_period: int, ema_period: int) -> pd.Series:
    cmo = _compute_cmo(series, cmo_period).abs() / 100
    alpha = 2 / (ema_period + 1)
    vidya = pd.Series(index=series.index, dtype="float64")

    for index, value in enumerate(series):
        if index == 0:
            vidya.iloc[index] = float(value)
            continue
        previous = vidya.iloc[index - 1]
        dynamic_alpha = alpha * (0 if pd.isna(cmo.iloc[index]) else float(cmo.iloc[index]))
        vidya.iloc[index] = previous + (dynamic_alpha * (float(value) - previous))

    return vidya


def _compute_dema(series: pd.Series, period: int) -> pd.Series:
    ema_one = series.ewm(span=period, adjust=False).mean()
    ema_two = ema_one.ewm(span=period, adjust=False).mean()
    return (2 * ema_one) - ema_two


def _compute_tema(series: pd.Series, period: int) -> pd.Series:
    ema_one = series.ewm(span=period, adjust=False).mean()
    ema_two = ema_one.ewm(span=period, adjust=False).mean()
    ema_three = ema_two.ewm(span=period, adjust=False).mean()
    return (3 * ema_one) - (3 * ema_two) + ema_three


def _compute_frama(series: pd.Series, period: int) -> pd.Series:
    frama = pd.Series(index=series.index, dtype="float64")
    half_period = max(period // 2, 1)

    for index in range(len(series)):
        value = float(series.iloc[index])
        if index == 0 or index < period:
            frama.iloc[index] = value
            continue

        window = series.iloc[index - period + 1 : index + 1]
        first_half = window.iloc[:half_period]
        second_half = window.iloc[half_period:]
        n1 = (first_half.max() - first_half.min()) / max(len(first_half), 1)
        n2 = (second_half.max() - second_half.min()) / max(len(second_half), 1)
        n3 = (window.max() - window.min()) / period

        if n1 <= 0 or n2 <= 0 or n3 <= 0:
            alpha = 1.0
        else:
            fractal_dimension = math.log((n1 + n2) / n3) / math.log(2)
            alpha = math.exp(-4.6 * (fractal_dimension - 1))

        alpha = min(max(alpha, 0.01), 1.0)
        frama.iloc[index] = alpha * value + ((1 - alpha) * float(frama.iloc[index - 1]))

    return frama


def _compute_trix(series: pd.Series, period: int) -> pd.Series:
    ema_one = series.ewm(span=period, adjust=False).mean()
    ema_two = ema_one.ewm(span=period, adjust=False).mean()
    ema_three = ema_two.ewm(span=period, adjust=False).mean()
    return 100 * _safe_divide(ema_three.diff(), ema_three.shift(1))


def _compute_bears_power(candles: pd.DataFrame, period: int) -> pd.Series:
    basis = candles["close"].ewm(span=period, adjust=False).mean()
    return candles["low"].astype(float) - basis.astype(float)


def _compute_bulls_power(candles: pd.DataFrame, period: int) -> pd.Series:
    basis = candles["close"].ewm(span=period, adjust=False).mean()
    return candles["high"].astype(float) - basis.astype(float)


def _compute_awesome_oscillator(candles: pd.DataFrame) -> pd.Series:
    median = _median_price(candles)
    return median.rolling(5).mean() - median.rolling(34).mean()


def _compute_chaikin_oscillator(candles: pd.DataFrame, parameters: dict[str, Any]) -> pd.Series:
    ad_line = _compute_accumulation_distribution(candles, parameters.get("volume_type"))
    fast_period = _coerce_int(parameters.get("fast_ma"), 3)
    slow_period = _coerce_int(parameters.get("slow_ma"), 10)
    ma_type = _extract_ma_type(parameters, default="EMA")
    fast_ma = _moving_average(ad_line, fast_period, ma_type)
    slow_ma = _moving_average(ad_line, slow_period, ma_type)
    return fast_ma - slow_ma


def _compute_demarker(candles: pd.DataFrame, period: int) -> pd.Series:
    demax = (candles["high"] - candles["high"].shift(1)).clip(lower=0)
    demin = (candles["low"].shift(1) - candles["low"]).clip(lower=0)
    demax_average = demax.rolling(period).mean()
    demin_average = demin.rolling(period).mean()
    return _safe_divide(demax_average, demax_average + demin_average)


def _compute_alligator(parameters: dict[str, Any], candles: pd.DataFrame) -> pd.DataFrame:
    ma_type = _extract_ma_type(parameters, default="SMMA")
    price_series = _resolve_price_mode_series(candles, parameters.get("price_mode"))

    jaw = _moving_average(price_series, _coerce_int(parameters.get("jaw_period"), 13), ma_type).shift(
        _coerce_int(parameters.get("jaw_shift"), 8)
    )
    teeth = _moving_average(price_series, _coerce_int(parameters.get("teeth_period"), 8), ma_type).shift(
        _coerce_int(parameters.get("teeth_shift"), 5)
    )
    lips = _moving_average(price_series, _coerce_int(parameters.get("lips_period"), 5), ma_type).shift(
        _coerce_int(parameters.get("lips_shift"), 3)
    )
    return pd.DataFrame({"Mandibula": jaw, "Dente": teeth, "Boca": lips})


def _compute_ichimoku(candles: pd.DataFrame, parameters: dict[str, Any]) -> pd.DataFrame:
    tenkan_period = _coerce_int(parameters.get("tenkan_sen"), 9)
    kijun_period = _coerce_int(parameters.get("kijun_sen"), 26)
    senkou_span_b_period = _coerce_int(parameters.get("senkou_span_b"), 52)

    tenkan = (candles["high"].rolling(tenkan_period).max() + candles["low"].rolling(tenkan_period).min()) / 2
    kijun = (candles["high"].rolling(kijun_period).max() + candles["low"].rolling(kijun_period).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(kijun_period)
    span_b = (
        (candles["high"].rolling(senkou_span_b_period).max() + candles["low"].rolling(senkou_span_b_period).min())
        / 2
    ).shift(kijun_period)
    chikou = candles["close"].shift(-kijun_period)
    return pd.DataFrame(
        {
            "Tenkan-sen": tenkan,
            "Kijun-sen": kijun,
            "Senkou Span A": span_a,
            "Senkou Span B": span_b,
            "Chikou Span": chikou,
        }
    )


def _compute_adx(candles: pd.DataFrame, period: int) -> pd.DataFrame:
    up_move = candles["high"].diff()
    down_move = -candles["low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr = _compute_atr(candles, period)
    plus_di = 100 * _safe_divide(plus_dm.ewm(alpha=1 / period, adjust=False).mean(), atr)
    minus_di = 100 * _safe_divide(minus_dm.ewm(alpha=1 / period, adjust=False).mean(), atr)
    dx = 100 * _safe_divide((plus_di - minus_di).abs(), (plus_di + minus_di))
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return pd.DataFrame({"ADX": adx, "+DI": plus_di, "-DI": minus_di})


def _compute_gator(parameters: dict[str, Any], candles: pd.DataFrame) -> pd.DataFrame:
    alligator = _compute_alligator(parameters, candles)
    upper = (alligator["Mandibula"] - alligator["Dente"]).abs()
    lower = -(alligator["Dente"] - alligator["Boca"]).abs()
    return pd.DataFrame({"Superior": upper, "Inferior": lower})


def _compute_williams_r(candles: pd.DataFrame, period: int) -> pd.Series:
    highest_high = candles["high"].rolling(period).max()
    lowest_low = candles["low"].rolling(period).min()
    return -100 * _safe_divide(highest_high - candles["close"], highest_high - lowest_low)


def _compute_market_facilitation_index(candles: pd.DataFrame, volume_type: str | None) -> pd.Series:
    volume = _resolve_volume_series(candles, volume_type)
    return _safe_divide((candles["high"] - candles["low"]).astype(float), volume)


def _compute_momentum(series: pd.Series, period: int) -> pd.Series:
    return 100 * _safe_divide(series, series.shift(period))


def _weighted_4(series: pd.Series) -> pd.Series:
    return (series + (2 * series.shift(1)) + (2 * series.shift(2)) + series.shift(3)) / 6


def _compute_rvi(candles: pd.DataFrame, period: int) -> pd.DataFrame:
    numerator = _weighted_4((candles["close"] - candles["open"]).astype(float))
    denominator = _weighted_4((candles["high"] - candles["low"]).astype(float))
    rvi = _safe_divide(numerator.rolling(period).mean(), denominator.rolling(period).mean())
    signal = (rvi + (2 * rvi.shift(1)) + (2 * rvi.shift(2)) + rvi.shift(3)) / 6
    return pd.DataFrame({"RVI": rvi, "Sinal": signal})


def _indicator_cache_key(source: dict[str, Any]) -> tuple[Any, ...]:
    parameters = source.get("parameters", {})
    return (
        source.get("slot_number"),
        source.get("indicator_name"),
        source.get("indicator_output"),
        tuple(sorted(parameters.items())),
    )


def _compute_indicator_frame(source: dict[str, Any], candles: pd.DataFrame) -> pd.DataFrame:
    indicator_name = source.get("indicator_name") or source.get("value")
    parameters = source.get("parameters", {})
    base_series = _indicator_input_series(candles, parameters)

    if indicator_name in {"SMA", "EMA"}:
        period = _coerce_int(parameters.get("period"), 14)
        values = _moving_average(base_series, period, indicator_name)
        return pd.DataFrame({"Valor": values})

    if indicator_name == "Media Movel":
        period = _coerce_int(parameters.get("period"), 21)
        ma_type = _extract_ma_type(parameters)
        values = _moving_average(base_series, period, ma_type)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": values.shift(displacement)})

    if indicator_name == "Keltner":
        return _compute_keltner(candles, parameters)

    if indicator_name == "Donchian":
        period = _coerce_int(parameters.get("period"), 21)
        return _compute_donchian(candles, period)

    if indicator_name == "Regressao":
        period = _coerce_int(parameters.get("period"), 18)
        return pd.DataFrame({"Valor": _compute_regression(base_series, period)})

    if indicator_name == "Afastamento da media":
        period = _coerce_int(parameters.get("period"), 14)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        ma_type = _extract_ma_type(parameters)
        moving_average = _moving_average(base_series, period, ma_type).shift(displacement)
        return pd.DataFrame({"Valor": base_series - moving_average})

    if indicator_name == "Desvio Medio":
        period = _coerce_int(parameters.get("period"), 14)
        ma_type = _extract_ma_type(parameters)
        return pd.DataFrame({"Valor": _compute_mean_deviation(base_series, period, ma_type)})

    if indicator_name == "Canal ATR":
        period = _coerce_int(parameters.get("period"), 14)
        deviation = _coerce_float(parameters.get("deviation"), 2.0)
        middle = _moving_average(base_series, period, "EMA")
        atr = _compute_atr(candles, period)
        return pd.DataFrame(
            {
                "Superior": middle + (atr * deviation),
                "Media": middle,
                "Inferior": middle - (atr * deviation),
            }
        )

    if indicator_name in {"BBANDS", "Bandas de Bollinger"}:
        period = _coerce_int(parameters.get("period"), 20)
        deviation = _coerce_float(parameters.get("deviation"), 2.0)
        frame = _compute_bbands(base_series, period, deviation)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return frame.shift(displacement)

    if indicator_name == "MACD":
        fast_period = _coerce_int(parameters.get("fast_ema"), 12)
        slow_period = _coerce_int(parameters.get("slow_ema"), 26)
        signal_period = _coerce_int(parameters.get("signal"), 9)
        return _compute_macd(base_series, fast_period, slow_period, signal_period)

    if indicator_name == "Envelopes":
        period = _coerce_int(parameters.get("period"), 14)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        ma_type = _extract_ma_type(parameters)
        deviation = _coerce_float(parameters.get("deviation"), 1.0)
        return _compute_envelopes(base_series, period, ma_type, deviation).shift(displacement)

    if indicator_name == "Estocastico":
        return _compute_stochastic(candles, parameters)

    if indicator_name in {"RSI", "RSI (Relative Strength Index)"}:
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_rsi(base_series, period)})

    if indicator_name == "Desvio Padrao":
        period = _coerce_int(parameters.get("period"), 2)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": _compute_stddev(base_series, period).shift(displacement)})

    if indicator_name == "Volume":
        return pd.DataFrame({"Valor": _resolve_volume_series(candles, parameters.get("type"))})

    if indicator_name == "ATR (Average True Range)":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_atr(candles, period)})

    if indicator_name == "Parabolic SAR":
        return pd.DataFrame(
            {
                "Valor": _compute_parabolic_sar(
                    candles,
                    _coerce_float(parameters.get("step"), 0.02),
                    _coerce_float(parameters.get("maximum"), 0.2),
                )
            }
        )

    if indicator_name == "Fractal":
        return _compute_fractal(candles)

    if indicator_name == "OBV (On Balance Volume)":
        return pd.DataFrame({"Valor": _compute_obv(candles, parameters.get("volume_type"))})

    if indicator_name == "Acumulacao/Distribuicao (A/D)":
        return pd.DataFrame({"Valor": _compute_accumulation_distribution(candles, parameters.get("volume_type"))})

    if indicator_name == "MFI (Money Flow Index)":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_mfi(candles, period, parameters.get("volume_type"))})

    if indicator_name == "Vidya":
        cmo_period = _coerce_int(parameters.get("cmo_period"), 9)
        ema_period = _coerce_int(parameters.get("ema_period"), 12)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": _compute_vidya(base_series, cmo_period, ema_period).shift(displacement)})

    if indicator_name == "DEMA":
        period = _coerce_int(parameters.get("period"), 14)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": _compute_dema(base_series, period).shift(displacement)})

    if indicator_name == "TEMA":
        period = _coerce_int(parameters.get("period"), 14)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": _compute_tema(base_series, period).shift(displacement)})

    if indicator_name == "FRAMA":
        period = _coerce_int(parameters.get("period"), 14)
        displacement = _coerce_int(parameters.get("displacement"), 0)
        return pd.DataFrame({"Valor": _compute_frama(base_series, period).shift(displacement)})

    if indicator_name == "TRIX":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_trix(base_series, period)})

    if indicator_name == "Bears Power":
        period = _coerce_int(parameters.get("period"), 13)
        return pd.DataFrame({"Valor": _compute_bears_power(candles, period)})

    if indicator_name == "Bulls Power":
        period = _coerce_int(parameters.get("period"), 13)
        return pd.DataFrame({"Valor": _compute_bulls_power(candles, period)})

    if indicator_name == "Chaikin Oscilador":
        return pd.DataFrame({"Valor": _compute_chaikin_oscillator(candles, parameters)})

    if indicator_name == "Accelerator Oscillator":
        awesome = _compute_awesome_oscillator(candles)
        return pd.DataFrame({"Valor": awesome - awesome.rolling(5).mean()})

    if indicator_name == "Awesome Oscillator":
        return pd.DataFrame({"Valor": _compute_awesome_oscillator(candles)})

    if indicator_name in {"CCI", "CCI (Commodity Channel Index)"}:
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_cci(candles, period)})

    if indicator_name == "DeMarker":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_demarker(candles, period)})

    if indicator_name == "Alligator":
        return _compute_alligator(parameters, candles)

    if indicator_name == "Nuvem de Ichimoku":
        return _compute_ichimoku(candles, parameters)

    if indicator_name in {"ADX (Average Directional Index)", "ADX Welles Wilder"}:
        period = _coerce_int(parameters.get("period"), 14)
        return _compute_adx(candles, period)

    if indicator_name == "Gator Oscillator":
        return _compute_gator(parameters, candles)

    if indicator_name == "Williams %R (WPR)":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_williams_r(candles, period)})

    if indicator_name == "Market Facilitation Index":
        return pd.DataFrame({"Valor": _compute_market_facilitation_index(candles, parameters.get("volume_type"))})

    if indicator_name == "Momentum":
        period = _coerce_int(parameters.get("period"), 14)
        return pd.DataFrame({"Valor": _compute_momentum(base_series, period)})

    if indicator_name == "RVI (Relative Vigor Index)":
        period = _coerce_int(parameters.get("period"), 14)
        return _compute_rvi(candles, period)

    return pd.DataFrame({"Valor": _empty_series(candles)})


def _resolve_indicator_source(
    source: dict[str, Any],
    candles: pd.DataFrame,
    cache: dict[tuple[Any, ...], pd.DataFrame],
) -> pd.Series:
    cache_key = _indicator_cache_key(source)
    if cache_key not in cache:
        cache[cache_key] = _compute_indicator_frame(source, candles)

    indicator_frame = cache[cache_key]
    output_name = source.get("indicator_output", "Valor")
    if output_name not in indicator_frame.columns:
        return _empty_series(candles)
    return _apply_offset(indicator_frame[output_name].astype(float), source.get("candle_offset", 0))


def _resolve_source(
    source: dict[str, Any],
    candles: pd.DataFrame,
    cache: dict[tuple[Any, ...], pd.DataFrame],
) -> pd.Series:
    source_type = source.get("source_type")
    if source_type == "price":
        return _apply_offset(candles[source["value"]].astype(float), source.get("candle_offset", 0))
    if source_type == "fixed":
        return _as_float_series(float(source["value"]), candles)
    if source_type == "indicator":
        return _resolve_indicator_source(source, candles, cache)
    if source_type == "special":
        return _resolve_special_source(source, candles)
    return _empty_series(candles)


def _evaluate_operator(operator: str, left: pd.Series, right: pd.Series) -> pd.Series:
    if operator == "GREATER_THAN":
        return left > right
    if operator == "LESS_THAN":
        return left < right
    if operator == "GREATER_OR_EQUAL":
        return left >= right
    if operator == "LESS_OR_EQUAL":
        return left <= right
    if operator == "EQUAL":
        return left == right
    if operator == "NOT_EQUAL":
        return left != right

    previous_left = left.shift(1)
    previous_right = right.shift(1)
    crossed_up = (previous_left <= previous_right) & (left > right)
    crossed_down = (previous_left >= previous_right) & (left < right)

    if operator == "CROSS_UP":
        return crossed_up
    if operator == "CROSS_DOWN":
        return crossed_down
    if operator == "CROSS_AND_CLOSE_ABOVE":
        return crossed_up & (left > right)
    if operator == "CROSS_AND_CLOSE_BELOW":
        return crossed_down & (left < right)
    return _false_series(pd.DataFrame(index=left.index))


def _group_rules(rules: list[dict[str, Any]]) -> OrderedDict[str, list[dict[str, Any]]]:
    grouped_rules: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for index, rule in enumerate(rules):
        group_id = rule.get("group_id") or f"group_{index}"
        grouped_rules.setdefault(group_id, []).append(rule)
    return grouped_rules


def _evaluate_rule_group(
    group_rules: list[dict[str, Any]],
    candles: pd.DataFrame,
    cache: dict[tuple[Any, ...], pd.DataFrame],
) -> pd.Series:
    group_result: pd.Series | None = None

    for index, rule in enumerate(group_rules):
        left_series = _resolve_source(rule["source_a"], candles, cache)
        right_series = _resolve_source(rule["source_b"], candles, cache)
        current_result = _evaluate_operator(rule["operator"], left_series, right_series).fillna(False)

        if index == 0 or group_result is None:
            group_result = current_result
            continue

        connector = rule.get("connector", "SE")
        if connector in OR_CONNECTORS:
            group_result = group_result | current_result
        else:
            group_result = group_result & current_result

    return group_result if group_result is not None else _false_series(candles)


def evaluate_rule_set(
    rules: list[dict[str, Any]],
    candles: pd.DataFrame,
) -> dict[str, Any]:
    indicator_cache: dict[tuple[Any, ...], pd.DataFrame] = {}
    grouped_rules = _group_rules(rules)
    group_evaluations: list[dict[str, Any]] = []

    for group_id, group_rules in grouped_rules.items():
        result = _evaluate_rule_group(group_rules, candles, indicator_cache)
        group_evaluations.append(
            {
                "group_id": group_id,
                "result": result,
                "metadata": group_rules[0].get("metadata", {}),
            }
        )

    combined = _false_series(candles)
    for evaluation in group_evaluations:
        combined = combined | evaluation["result"]

    return {
        "combined": combined.fillna(False),
        "groups": group_evaluations,
    }


def _collect_signals(
    signal_type: str,
    candles: pd.DataFrame,
    evaluations: dict[str, Any],
    default_side: str,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for evaluation in evaluations["groups"]:
        group_result = evaluation["result"]
        metadata = evaluation["metadata"]
        side = metadata.get("side", default_side)

        for index in candles.index[group_result]:
            candle = candles.loc[index]
            signals.append(
                {
                    "type": signal_type,
                    "group_id": evaluation["group_id"],
                    "index": int(index),
                    "time": candle["time"],
                    "price": float(candle["close"]),
                    "side": side,
                    "metadata": metadata,
                }
            )
    return signals


def evaluate_strategy(
    strategy: dict[str, Any],
    candles: pd.DataFrame,
) -> dict[str, Any]:
    entry_evaluations = evaluate_rule_set(strategy.get("entry_rules", []), candles)
    exit_evaluations = evaluate_rule_set(strategy.get("exit_rules", []), candles)
    direction = strategy.get("direction", "NONE")

    evaluation_frame = candles.loc[:, ["time", "close"]].copy()
    evaluation_frame["entry_signal"] = entry_evaluations["combined"].astype(bool)
    evaluation_frame["exit_signal"] = exit_evaluations["combined"].astype(bool)

    return {
        "entry_signals": _collect_signals("entry", candles, entry_evaluations, direction),
        "exit_signals": _collect_signals("exit", candles, exit_evaluations, direction),
        "evaluation": evaluation_frame,
    }
