from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from flask import Blueprint, render_template, request

from builders.rules_builder import build_entry_rules, build_exit_rules
from builders.settings_builder import build_settings
from builders.strategy_builder import (
    PERIOD_LABELS,
    build_strategy_payload,
    derive_direction,
    format_timeframe_label,
    resolve_market_timeframe,
)
from config import (
    DISTANCE_CALCULATION_OPTIONS,
    MARKET_PERIOD_OPTIONS,
    OPERATIONAL_TYPE_OPTIONS,
    ORDER_EXECUTION_OPTIONS,
    PENDING_CANDLE_REFERENCE_OPTIONS,
    PENDING_EXPIRATION_OPTIONS,
    PENDING_POSITION_OPTIONS,
    PENDING_PRICE_REFERENCE_OPTIONS,
    PRIMARY_TIMEFRAME_OPTIONS,
    PROCESSING_MODE_OPTIONS,
    STOP_CALCULATION_OPTIONS,
    STOP_MOVEL_MODE_OPTIONS,
    STOP_TYPES,
    TARGET_MARKET_OPTIONS,
    YES_NO_OPTIONS,
)
from core.backtest_engine import run_backtest
from services.mt5_service import connect_terminal, load_market_data, load_terminal_symbols
from webapp.backend import get_web_backend_context
from webapp.routes.shared import build_performance_chart, frame_columns, frame_to_records, json_pretty
from webapp.runtime_state import get_runtime_state


bp = Blueprint("builder", __name__)

BUILDER_TABS = [
    ("connection", "1. Conexao MT5"),
    ("market", "2. Dados de mercado"),
    ("basics", "3. Informacoes basicas"),
    ("schedule", "4. Horario"),
    ("setup", "5. Configuracao inicial"),
    ("stop_loss", "6. Stop loss"),
    ("soft_stop", "7. Stop movel"),
    ("take_profit", "8. Take profit"),
    ("trailing_stop", "9. Trailing stop"),
    ("partial_exits", "10. Saidas parciais"),
    ("signals", "11. Sinais"),
    ("final_adjustments", "12. Ajustes finais"),
]

STOP_PRICE_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento"]
STOP_CANDLE_REFERENCE_OPTIONS = ["Ultimo", "Penultimo", "Antepenultimo"]
STOP_MEDIA_REFERENCE_OPTIONS = ["Maxima", "Minima", "Abertura", "Fechamento"]
BAND_CHANNEL_INDICATOR_OPTIONS = [
    "Bandas de Bollinger",
    "Envelopes",
    "Keltner",
    "Donchian",
    "Canal ATR",
]
BAND_CHANNEL_SIGNAL_OPTIONS = [
    "Fechou fora",
    "Fechou dentro e saiu",
    "Fechou dentro e fechou fora",
    "Fechou fora e voltou",
    "Fechou fora e fechou dentro",
    "Estando fora",
]
CROSSOVER_SOURCE_OPTIONS = [
    "Nao usar",
    "Fechamento da vela",
    "Abertura da vela",
    "Maxima da vela",
    "Minima da vela",
    "Media Movel",
    "Vidya",
    "Dema",
    "Tema",
    "Frama",
]
OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS = [
    "MACD",
    "Estocastico",
    "RSI (Relative Strength Index)",
    "MFI (Money Flow Index)",
    "Bears Power",
    "Bulls Power",
    "Chaikin Oscilador",
    "Accelerator Oscillator",
    "Awesome Oscillator",
    "CCI (Commodity Channel Index)",
    "DeMarker",
    "Regressao",
    "Afastamento da media",
    "Desvio Medio",
]
READY_SIGNAL_INDICATOR_OPTIONS = [
    "Nao usar",
    "Externo",
    "Keltner",
    "Donchian",
    "Regressao",
    "Afastamento da media",
    "Desvio Medio",
    "Canal ATR",
    "Media Movel",
    "Bandas de Bollinger",
    "MACD",
    "Envelopes",
    "Estocastico",
    "RSI (Relative Strength Index)",
    "Desvio Padrao",
    "Volume",
    "ATR (Average True Range)",
    "Parabolic SAR",
    "Fractal",
    "OBV (On Balance Volume)",
    "Acumulacao/Distribuicao (A/D)",
    "MFI (Money Flow Index)",
    "Vidya",
    "DEMA",
    "TEMA",
    "FRAMA",
    "TRIX",
    "Bears Power",
    "Bulls Power",
    "Chaikin Oscilador",
    "Accelerator Oscillator",
    "Awesome Oscillator",
    "CCI (Commodity Channel Index)",
    "DeMarker",
    "Alligator",
    "Nuvem de Ichimoku",
    "ADX (Average Directional Index)",
    "ADX Welles Wilder",
    "Gator Oscillator",
    "Williams %R (WPR)",
    "Market Facilitation Index",
    "Momentum",
    "RVI (Relative Vigor Index)",
]
SIGNAL_INDICATOR_OUTPUT_LABELS = {
    "Keltner": ["Superior", "Media", "Inferior"],
    "Donchian": ["Superior", "Meio", "Inferior"],
    "Regressao": ["Valor"],
    "Afastamento da media": ["Valor"],
    "Desvio Medio": ["Valor"],
    "Canal ATR": ["Superior", "Media", "Inferior"],
    "Media Movel": ["Valor"],
    "Bandas de Bollinger": ["Superior", "Media", "Inferior"],
    "MACD": ["Linha MACD", "Linha de sinal", "Histograma"],
    "Envelopes": ["Superior", "Media", "Inferior"],
    "Estocastico": ["%K", "%D"],
    "RSI (Relative Strength Index)": ["Valor"],
    "Desvio Padrao": ["Valor"],
    "Volume": ["Valor"],
    "ATR (Average True Range)": ["Valor"],
    "Parabolic SAR": ["Valor"],
    "Fractal": ["Superior", "Inferior"],
    "OBV (On Balance Volume)": ["Valor"],
    "Acumulacao/Distribuicao (A/D)": ["Valor"],
    "MFI (Money Flow Index)": ["Valor"],
    "Vidya": ["Valor"],
    "DEMA": ["Valor"],
    "TEMA": ["Valor"],
    "FRAMA": ["Valor"],
    "TRIX": ["Valor"],
    "Bears Power": ["Valor"],
    "Bulls Power": ["Valor"],
    "Chaikin Oscilador": ["Valor"],
    "Accelerator Oscillator": ["Valor"],
    "Awesome Oscillator": ["Valor"],
    "CCI (Commodity Channel Index)": ["Valor"],
    "DeMarker": ["Valor"],
    "Alligator": ["Mandibula", "Dente", "Boca"],
    "Nuvem de Ichimoku": ["Tenkan-sen", "Kijun-sen", "Senkou Span A", "Senkou Span B", "Chikou Span"],
    "ADX (Average Directional Index)": ["ADX", "+DI", "-DI"],
    "ADX Welles Wilder": ["ADX", "+DI", "-DI"],
    "Gator Oscillator": ["Superior", "Inferior"],
    "Williams %R (WPR)": ["Valor"],
    "Market Facilitation Index": ["Valor"],
    "Momentum": ["Valor"],
    "RVI (Relative Vigor Index)": ["RVI", "Sinal"],
}
SIGNAL_LOGICAL_COMMAND_OPTIONS = ["SE", "E", "OU", "E SE", "OU SE", "E Tambem", "OU Tambem"]
SIGNAL_RULE_OPERATOR_LABELS = {
    "GREATER_THAN": "Maior que",
    "LESS_THAN": "Menor que",
    "GREATER_OR_EQUAL": "Maior ou igual",
    "LESS_OR_EQUAL": "Menor ou igual",
    "EQUAL": "Igual",
    "NOT_EQUAL": "Diferente",
    "CROSS_UP": "Cruzar p/ cima",
    "CROSS_DOWN": "Cruzar p/ baixo",
    "CROSS_AND_CLOSE_ABOVE": "Cruzar e fechar acima",
    "CROSS_AND_CLOSE_BELOW": "Cruzar e fechar abaixo",
}
SIGNAL_RULE_CANDLE_LABELS = {
    "0": "Vela atual (0)",
    "1": "Vela anterior (1)",
    "2": "Penultima vela (2)",
    "3": "Anti penultima (3)",
}
SIGNAL_RULE_SOURCE_LABELS = {
    "NONE": "Nao usar",
    "ABSOLUTE_VALUE": "Valor absoluto",
    "POINT_VALUE": "Valor em pontos",
    "ENTRY_PRICE": "Preco de entrada",
    "AVERAGE_PRICE": "Preco medio",
    "CURRENT_PRICE": "Preco atual",
    "CANDLE_CLOSE": "Fechamento da vela",
    "CANDLE_OPEN": "Abertura da vela",
    "CANDLE_HIGH": "Maxima da vela",
    "CANDLE_LOW": "Minima da vela",
    "DAY_CLOSE": "Fechamento do dia",
    "DAY_OPEN": "Abertura do dia",
    "DAY_HIGH": "Maxima do dia",
    "DAY_LOW": "Minima do dia",
    "CANDLE_SIZE": "Tamanho da vela",
    "CANDLE_BODY": "Corpo da vela",
}
FINAL_ADJUSTMENT_FIELDS = [
    ("cancel_pending_on_opposite_signal", "Cancelar pendente de entrada se aparecer sinal oposto", "Sim"),
    ("reposition_stop_loss_on_favorable_move", "Reposicionar stoploss no aumento a favor da operacao", "Sim"),
    ("reposition_take_profit_on_adverse_move", "Reposicionar takeprofit no aumento contra a operacao", "Sim"),
    ("move_stop_loss_based_on_average_price", "Movimentar stoploss com base no preco medio", "Sim"),
    ("move_take_profit_based_on_average_price", "Movimentar takeprofit com base no preco medio", "Sim"),
    ("use_average_price_for_partial_exits", "Usar preco medio como referencia das parciais", "Sim"),
    ("block_exit_signal_on_entry_candle", "Impedir sinal de saida na vela que gerou entrada", "Sim"),
    ("block_entry_signal_on_exit_candle", "Impedir sinal de entrada na vela que gerou saida", "Sim"),
    ("recalculate_average_price_from_partial_exits", "Recalcular o preco medio com base nas saidas parciais", "Nao"),
]
DEFAULT_OPEN_ACCORDIONS = ",".join(
    [
        "builder-connection-main",
        "builder-market-main",
        "builder-basics-main",
        "builder-schedule-main",
        "builder-setup-main",
        "builder-stop-loss-main",
        "builder-soft-stop-main",
        "builder-take-profit-main",
        "builder-trailing-stop-main",
        "builder-partial-exits-main",
        "builder-signals-filter",
        "builder-final-adjustments-main",
    ]
)


@bp.get("/builder")
def builder_page() -> Any:
    state = get_runtime_state()
    form_values = _load_builder_form(state)
    active_tab = request.args.get("tab") or str(form_values.get("active_tab") or "connection")
    form_values["active_tab"] = active_tab
    state["builder_form"] = form_values
    return render_template("builder/index.html", **_build_builder_context(state, form_values, []))


@bp.post("/builder/sync")
def sync_builder_form() -> Any:
    state = get_runtime_state()
    form_values = _collect_builder_form(request.form)
    state["builder_form"] = form_values
    if state.get("builder_payload") is not None or state.get("builder_backtest") is not None:
        state["builder_dirty"] = True
    return render_template("builder/_workspace.html", **_build_builder_context(state, form_values, []))


@bp.post("/builder/actions/<action>")
def run_builder_action(action: str) -> Any:
    backend = get_web_backend_context()
    state = get_runtime_state()
    form_values = _collect_builder_form(request.form)
    state["builder_form"] = form_values

    messages: list[dict[str, str]] = []
    if action == "connect_mt5":
        messages.extend(_handle_mt5_connection(state))
    elif action == "load_symbols":
        messages.extend(_handle_symbols_load(state))
    elif action == "load_market_data":
        messages.extend(_handle_market_data_load(state, form_values))
    elif action in {"save_strategy", "persist_strategy", "persist_backtest", "show_json"}:
        messages.extend(
            _handle_builder_actions(
                backend=backend,
                state=state,
                form_values=form_values,
                action=action,
            )
        )
    else:
        messages.append({"category": "warning", "text": f"Acao nao suportada: {action}."})

    return render_template("builder/_workspace.html", **_build_builder_context(state, form_values, messages))


def _build_builder_context(
    state: dict[str, Any],
    form_values: dict[str, Any],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    ui_options = _build_builder_ui_options(form_values, state)
    market_data = state.get("market_data")
    backtest_view = _build_backtest_view(state.get("builder_backtest"), market_data)
    partial_exit_count = min(max(_int(form_values.get("partial_exits_count"), 1), 1), 3)

    return {
        "page_title": "Strategy Builder",
        "active_page": "builder.builder_page",
        "builder_tabs": BUILDER_TABS,
        "active_tab": str(form_values.get("active_tab") or "connection"),
        "form_values": form_values,
        "state": state,
        "messages": messages,
        "ui_options": ui_options,
        "view_state": {
            "has_market_data": isinstance(market_data, pd.DataFrame) and not market_data.empty,
            "market_data_count": len(market_data) if isinstance(market_data, pd.DataFrame) else 0,
            "show_custom_dates": str(form_values.get("period_mode")) == "CUSTOM",
            "show_close_schedule": str(form_values.get("close_by_schedule")) == "Sim",
            "partial_exit_count": partial_exit_count,
            "entry_is_pending": str(form_values.get("entry_order_type")) == "Pendente",
            "exit_is_pending": str(form_values.get("exit_order_type")) == "Pendente",
            "show_json": bool(state.get("builder_payload")),
            "has_backtest": backtest_view is not None,
            "builder_dirty": bool(state.get("builder_dirty")),
            "open_accordions": str(form_values.get("open_accordions") or DEFAULT_OPEN_ACCORDIONS),
            "selected_backtest_run_id": state.get("selected_backtest_run_id"),
            "selected_strategy_version_id": state.get("selected_strategy_version_id"),
        },
        "market_data_rows": frame_to_records(market_data),
        "market_data_columns": frame_columns(market_data),
        "payload_json": json_pretty(state.get("builder_payload")),
        "backtest_view": backtest_view,
        "timeframe_label": format_timeframe_label,
        "period_labels": PERIOD_LABELS,
    }


def _load_builder_form(state: dict[str, Any]) -> dict[str, Any]:
    form_values = _default_builder_form()
    form_values.update(state.get("builder_form") or {})
    if not form_values.get("open_accordions"):
        form_values["open_accordions"] = DEFAULT_OPEN_ACCORDIONS
    return form_values


def _default_builder_form() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "active_tab": "connection",
        "open_accordions": DEFAULT_OPEN_ACCORDIONS,
        "selected_symbol": "",
        "selected_timeframe": "M5",
        "period_mode": "LAST_MONTH",
        "custom_start_date": (date.today() - timedelta(days=30)).isoformat(),
        "custom_end_date": date.today().isoformat(),
        "strategy_name": "Minha Estrategia",
        "desired_market": TARGET_MARKET_OPTIONS[0],
        "operational_type": OPERATIONAL_TYPE_OPTIONS[0],
        "processing_mode": PROCESSING_MODE_OPTIONS[0],
        "operate_buy": "Sim",
        "operate_sell": "Nao",
        "close_by_schedule": "Nao",
        "close_operations_hour": "23",
        "close_operations_minute": "00",
        "operation_start_hour": "00",
        "operation_start_minute": "00",
        "operation_end_hour": "22",
        "operation_end_minute": "00",
        "primary_timeframe": "M5",
        "initial_volume": "1.0",
        "max_spread": "10.0",
        "stop_loss_enabled": "Nao",
        "stop_loss_type": "points",
        "stop_loss_mode": "Calculo",
        "stop_loss_calculation_type": "Referencia de preco",
        "stop_loss_calculation_method": "Media",
        "stop_loss_reference": STOP_PRICE_REFERENCE_OPTIONS[0],
        "stop_loss_candle": STOP_CANDLE_REFERENCE_OPTIONS[0],
        "stop_loss_candle_period": "3",
        "stop_loss_candle_reference": STOP_MEDIA_REFERENCE_OPTIONS[0],
        "stop_loss_multiplier": "1.0",
        "stop_loss_value": "100.0",
        "soft_stop_enabled": "Nao",
        "soft_stop_calculation_type": "points",
        "soft_stop_type": "padrao",
        "soft_stop_acionar_a_favor": "0.0",
        "soft_stop_passe": "0.0",
        "soft_stop_candles_basis": "distance",
        "soft_stop_distance": "0.0",
        "soft_stop_candle_count": "1",
        "soft_stop_reference": STOP_PRICE_REFERENCE_OPTIONS[0],
        "soft_stop_indicator": "SMA",
        "take_profit_enabled": "Nao",
        "take_profit_type": "points",
        "take_profit_value": "100.0",
        "trailing_stop_enabled": "Nao",
        "trailing_stop_calculation_type": "points",
        "trailing_stop_type": "padrao",
        "trailing_stop_acionar_a_favor": "0.0",
        "trailing_stop_passe": "0.0",
        "trailing_stop_candles_basis": "distance",
        "trailing_stop_distance": "0.0",
        "trailing_stop_candle_count": "1",
        "trailing_stop_reference": STOP_PRICE_REFERENCE_OPTIONS[0],
        "trailing_stop_indicator": "SMA",
        "partial_exits_enabled": "Nao",
        "partial_exits_calculation_type": "points",
        "partial_exits_count": "1",
        "candle_filter_measure_type": DISTANCE_CALCULATION_OPTIONS[0],
        "candle_filter_timeframe": "M5",
        "candle_filter_min_size": "0.0",
        "candle_filter_max_size": "0.0",
        "candle_filter_min_body": "0.0",
        "candle_filter_max_body": "0.0",
        "distance_calculation_type": DISTANCE_CALCULATION_OPTIONS[0],
        "entry_order_type": ORDER_EXECUTION_OPTIONS[0],
        "entry_pending_positioning": PENDING_POSITION_OPTIONS[0],
        "entry_pending_average_candles": "3",
        "entry_pending_price_reference": PENDING_PRICE_REFERENCE_OPTIONS[0],
        "entry_pending_candle_reference": PENDING_CANDLE_REFERENCE_OPTIONS[0],
        "entry_pending_order_distance": "0.0",
        "entry_pending_expiration": "Nao expirar",
        "exit_order_type": ORDER_EXECUTION_OPTIONS[0],
        "exit_pending_positioning": PENDING_POSITION_OPTIONS[0],
        "exit_pending_average_candles": "3",
        "exit_pending_price_reference": PENDING_PRICE_REFERENCE_OPTIONS[0],
        "exit_pending_candle_reference": PENDING_CANDLE_REFERENCE_OPTIONS[0],
        "exit_pending_order_distance": "0.0",
        "exit_pending_expiration": "Nao expirar",
        "band_channels_enabled": "Nao",
        "band_channels_signal": BAND_CHANNEL_SIGNAL_OPTIONS[0],
        "band_channels_indicator": BAND_CHANNEL_INDICATOR_OPTIONS[0],
        "band_channels_period": "20",
        "band_channels_deviation": "2.0",
        "band_channels_displacement": "0",
        "band_channels_ma_type": "Simples (SMA)",
        "band_channels_price_mode": "Fechamento",
        "crossover_enabled": "Nao",
        "crossover_fast_source": CROSSOVER_SOURCE_OPTIONS[0],
        "crossover_fast_period": "21",
        "crossover_slow_source": CROSSOVER_SOURCE_OPTIONS[0],
        "crossover_slow_period": "21",
        "crossover_signal": "Cruzamento para compra",
        "overbought_oversold_signal": "Nao usar",
        "overbought_oversold_indicator": OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS[0],
        "overbought_oversold_period": "14",
        "overbought_oversold_output": "Linha MACD",
        "overbought_level": "70",
        "oversold_level": "30",
    }

    for index in range(3):
        defaults[f"partial_exit_target_{index}"] = str((index + 1) * 100)
        defaults[f"partial_exit_percent_{index}"] = "50.0" if index == 0 else "25.0"

    source_defaults = ["NONE", "PRICE:close", "PRICE:open", "CURRENT_PRICE", "CANDLE_BODY"]
    for slot_number in range(1, 5):
        defaults[f"signal_indicator_{slot_number}"] = READY_SIGNAL_INDICATOR_OPTIONS[0]
        defaults[f"signal_indicator_output_{slot_number}"] = "Valor"
        defaults[f"signal_indicator_period_{slot_number}"] = "14"
        defaults[f"signal_indicator_price_mode_{slot_number}"] = "Fechamento"

    for rule_index in range(5):
        defaults[f"signal_rule_{rule_index}_logical_command"] = SIGNAL_LOGICAL_COMMAND_OPTIONS[min(rule_index, 1)]
        defaults[f"signal_rule_{rule_index}_source_a"] = source_defaults[min(rule_index, len(source_defaults) - 1)]
        defaults[f"signal_rule_{rule_index}_candle_a"] = "0"
        defaults[f"signal_rule_{rule_index}_operator"] = "GREATER_THAN"
        defaults[f"signal_rule_{rule_index}_source_b"] = "NONE"
        defaults[f"signal_rule_{rule_index}_candle_b"] = "0"

    for field_key, _label, default_value in FINAL_ADJUSTMENT_FIELDS:
        defaults[f"final_adjustment_{field_key}"] = default_value

    return defaults


def _collect_builder_form(form: Any) -> dict[str, Any]:
    collected = _default_builder_form()
    for key in collected:
        if key in form:
            collected[key] = form.get(key)
    return collected


def _handle_mt5_connection(state: dict[str, Any]) -> list[dict[str, str]]:
    connection_result = connect_terminal()
    state["mt5_connected"] = connection_result["connected"]
    state["mt5_status"] = connection_result["status"]
    if connection_result["connected"]:
        symbols_result = load_terminal_symbols()
        state["symbols"] = symbols_result["symbols"]
        state["symbols_status"] = symbols_result["status"]
        return [{"category": "success", "text": connection_result["status"]}]
    state["symbols"] = []
    state["symbols_status"] = ""
    return [{"category": "danger", "text": connection_result["status"]}]


def _handle_symbols_load(state: dict[str, Any]) -> list[dict[str, str]]:
    if not state["mt5_connected"]:
        return [{"category": "warning", "text": "Conecte ao MT5 antes de carregar simbolos."}]
    symbols_result = load_terminal_symbols()
    state["symbols"] = symbols_result["symbols"]
    state["symbols_status"] = symbols_result["status"]
    return [
        {
            "category": "success" if symbols_result["success"] else "warning",
            "text": symbols_result["status"],
        }
    ]


def _handle_market_data_load(state: dict[str, Any], form_values: dict[str, Any]) -> list[dict[str, str]]:
    if not state["mt5_connected"]:
        return [{"category": "danger", "text": "Conecte ao MT5 antes de carregar os dados."}]

    if not state["symbols"]:
        return [{"category": "danger", "text": "Nenhum simbolo disponivel para consulta."}]

    effective_market_timeframe = resolve_market_timeframe(
        str(form_values["selected_timeframe"]),
        str(form_values["primary_timeframe"]),
    )
    if effective_market_timeframe is None:
        return [
            {
                "category": "warning",
                "text": "Selecione um tempo grafico principal diferente de Corrente para carregar os dados.",
            }
        ]

    market_result = load_market_data(
        str(form_values["selected_symbol"]),
        effective_market_timeframe,
        str(form_values["period_mode"]),
        _parse_date(form_values.get("custom_start_date")),
        _parse_date(form_values.get("custom_end_date")),
    )
    if market_result["query"] is None and market_result["error"]:
        return [{"category": "danger", "text": str(market_result["error"])}]

    state["market_data"] = market_result["data"]
    state["market_query"] = market_result["query"]
    state["builder_backtest"] = None
    state["builder_dirty"] = bool(state.get("builder_payload"))
    if state["market_data"].empty:
        return [{"category": "warning", "text": market_result["error"] or "Nenhum dado retornado."}]
    return [{"category": "success", "text": f"{len(state['market_data'])} candles carregados."}]


def _handle_builder_actions(
    *,
    backend: Any,
    state: dict[str, Any],
    form_values: dict[str, Any],
    action: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    payload, _configs = _build_builder_payload(form_values)
    state["builder_payload"] = payload
    state["builder_dirty"] = False

    if action == "save_strategy":
        state["saved_strategy"] = payload
        messages.append({"category": "success", "text": "Estrutura da estrategia salva na sessao atual."})

    persisted_strategy: dict[str, Any] | None = None
    if action in {"persist_strategy", "persist_backtest"}:
        persisted_strategy = backend.strategy_service.ensure_strategy(payload, origin="manual")
        state["selected_strategy_version_id"] = persisted_strategy["strategy_version"]["id"]
        messages.append(
            {
                "category": "success",
                "text": (
                    "Estrategia ja existia no backend; referencia carregada com sucesso."
                    if persisted_strategy.get("deduplicated")
                    else "Estrategia persistida no backend."
                ),
            }
        )
        messages.append(
            {
                "category": "info",
                "text": (
                    f"Strategy ID: {persisted_strategy['strategy']['id']} | "
                    f"Version ID: {persisted_strategy['strategy_version']['id']}"
                ),
            }
        )

    if action == "persist_backtest":
        market_data = state.get("market_data")
        if not isinstance(market_data, pd.DataFrame) or market_data.empty:
            messages.append({"category": "warning", "text": "Carregue candles do MT5 antes de persistir backtest."})
        else:
            if persisted_strategy is None:
                persisted_strategy = backend.strategy_service.ensure_strategy(payload, origin="manual")
            execution = backend.backtest_service.run_and_persist_backtest(
                strategy_version=persisted_strategy["strategy_version"],
                strategy=persisted_strategy["strategy_spec"],
                candles=market_data,
                execution_parameters={
                    "fill_policy": "next_candle_open",
                    "evaluation_mode": "manual_builder",
                    "dataset_role": "full",
                    "dataset_id": "builder",
                    "partition_origin": "builder",
                    "window_index": 0,
                    "window_label": "builder",
                },
            )
            run_row = execution["persistence"]["backtest_run"]
            state["selected_backtest_run_id"] = run_row["id"]
            state["selected_strategy_run_ids"] = [run_row["id"]]
            state["selected_strategy_position"] = 0
            messages.append(
                {
                    "category": "success",
                    "text": (
                        "Backtest ja existia no backend; referencia carregada."
                        if execution["persistence"].get("deduplicated")
                        else "Backtest persistido com sucesso."
                    ),
                }
            )
            messages.append({"category": "info", "text": f"Run ID: {run_row['id']}"})

    market_data = state.get("market_data")
    state["builder_backtest"] = (
        run_backtest(payload, market_data)
        if isinstance(market_data, pd.DataFrame) and not market_data.empty
        else None
    )

    if action == "show_json":
        messages.append({"category": "info", "text": "JSON da estrategia atualizado."})

    return messages


def _build_builder_payload(form_values: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    operation_config = {
        "strategy_name": str(form_values["strategy_name"]),
        "desired_market": str(form_values["desired_market"]),
        "operational_type": str(form_values["operational_type"]),
        "processing_mode": str(form_values["processing_mode"]),
        "operate_buy": str(form_values["operate_buy"]) == "Sim",
        "operate_sell": str(form_values["operate_sell"]) == "Sim",
        "direction": derive_direction(str(form_values["operate_buy"]), str(form_values["operate_sell"])),
    }
    time_config = {
        "close_by_schedule": str(form_values["close_by_schedule"]) == "Sim",
        "operation_start_time": f"{_pad(form_values['operation_start_hour'])}:{_pad(form_values['operation_start_minute'])}",
        "operation_end_time": f"{_pad(form_values['operation_end_hour'])}:{_pad(form_values['operation_end_minute'])}",
        "close_operations_time": f"{_pad(form_values['close_operations_hour'])}:{_pad(form_values['close_operations_minute'])}",
    }
    initial_setup_config = {
        "primary_timeframe": str(form_values["primary_timeframe"]),
        "initial_volume": _float(form_values["initial_volume"], 1.0),
        "max_spread": _float(form_values["max_spread"], 10.0),
    }
    stop_loss_config = {
        "enabled": str(form_values["stop_loss_enabled"]) == "Sim",
        "mode": str(form_values["stop_loss_mode"]),
        "calculation_type": str(form_values["stop_loss_calculation_type"]),
        "calculation_method": str(form_values["stop_loss_calculation_method"]),
        "reference": str(form_values["stop_loss_reference"]),
        "candle": str(form_values["stop_loss_candle"]),
        "candle_period": _int(form_values["stop_loss_candle_period"], 3),
        "candle_reference": str(form_values["stop_loss_candle_reference"]),
        "multiplier": _float(form_values["stop_loss_multiplier"], 1.0),
        "target": {
            "type": str(form_values["stop_loss_type"]),
            "value": _float(form_values["stop_loss_value"], 100.0),
        },
    }
    take_profit_config = {
        "enabled": str(form_values["take_profit_enabled"]) == "Sim",
        "target": {
            "type": str(form_values["take_profit_type"]),
            "value": _float(form_values["take_profit_value"], 100.0),
        },
    }
    soft_trailing_stop_config = _build_moving_stop_config(form_values, prefix="soft_stop")
    trailing_stop_config = _build_moving_stop_config(form_values, prefix="trailing_stop")

    partial_exits_config = {
        "enabled": str(form_values["partial_exits_enabled"]) == "Sim",
        "calculation_type": str(form_values["partial_exits_calculation_type"]),
        "levels": [],
    }
    partial_count = min(max(_int(form_values["partial_exits_count"], 1), 1), 3)
    for index in range(partial_count):
        partial_exits_config["levels"].append(
            {
                "target_distance": _float(form_values[f"partial_exit_target_{index}"], 0.0),
                "exit_percent": _float(form_values[f"partial_exit_percent_{index}"], 0.0),
            }
        )

    execution_config = {
        "distance_calculation_type": str(form_values["distance_calculation_type"]),
        "entry": _build_order_config_from_form(form_values, prefix="entry"),
        "exit": _build_order_config_from_form(form_values, prefix="exit"),
    }
    filter_config = {
        "candle_constraints": {
            "measure_type": str(form_values["candle_filter_measure_type"]),
            "timeframe": str(form_values["candle_filter_timeframe"]),
            "min_size": _float(form_values["candle_filter_min_size"], 0.0),
            "max_size": _float(form_values["candle_filter_max_size"], 0.0),
            "min_body": _float(form_values["candle_filter_min_body"], 0.0),
            "max_body": _float(form_values["candle_filter_max_body"], 0.0),
        }
    }
    signal_config = _build_signal_config(form_values)
    final_adjustments = {
        field_key: str(form_values[f"final_adjustment_{field_key}"]) == "Sim"
        for field_key, _label, _default in FINAL_ADJUSTMENT_FIELDS
    }

    settings = build_settings(
        operation_config=operation_config,
        time_config=time_config,
        risk_config={
            "stop_loss": stop_loss_config,
            "soft_trailing_stop": soft_trailing_stop_config,
            "take_profit": take_profit_config,
            "trailing_stop": trailing_stop_config,
            "partial_exits": partial_exits_config,
        },
        execution_config=execution_config,
        filter_config=filter_config,
        ready_signals=signal_config["ready_signals"],
        final_adjustments=final_adjustments,
        initial_setup_config=initial_setup_config,
    )
    payload = build_strategy_payload(
        strategy_name=operation_config["strategy_name"],
        direction=operation_config["direction"],
        settings=settings,
        symbol=str(form_values["selected_symbol"]) or None,
        timeframe=str(form_values["selected_timeframe"]),
        period_mode=str(form_values["period_mode"]),
        custom_start_date=_parse_date(form_values.get("custom_start_date")),
        custom_end_date=_parse_date(form_values.get("custom_end_date")),
        entry_rules=build_entry_rules(signal_config["ready_signals"]),
        exit_rules=build_exit_rules(signal_config["ready_signals"]),
        risk_management={
            "stop": stop_loss_config["target"],
            "take": take_profit_config["target"],
        },
    )
    return payload, {
        "operation_config": operation_config,
        "time_config": time_config,
        "signal_config": signal_config,
    }


def _build_moving_stop_config(form_values: dict[str, Any], *, prefix: str) -> dict[str, Any]:
    return {
        "enabled": str(form_values[f"{prefix}_enabled"]) == "Sim",
        "calculation_type": str(form_values[f"{prefix}_calculation_type"]),
        "type": str(form_values[f"{prefix}_type"]),
        "acionar_a_favor": _float(form_values[f"{prefix}_acionar_a_favor"], 0.0),
        "passe": _float(form_values[f"{prefix}_passe"], 0.0),
        "candles_basis": str(form_values[f"{prefix}_candles_basis"]),
        "distance": _float(form_values[f"{prefix}_distance"], 0.0),
        "candle_count": _int(form_values[f"{prefix}_candle_count"], 1),
        "reference": str(form_values[f"{prefix}_reference"]),
        "indicator": str(form_values[f"{prefix}_indicator"]),
    }


def _build_order_config_from_form(form_values: dict[str, Any], *, prefix: str) -> dict[str, Any]:
    order_type = str(form_values[f"{prefix}_order_type"])
    pending_config = {
        "positioning": str(form_values[f"{prefix}_pending_positioning"]),
        "average_candles": _int(form_values[f"{prefix}_pending_average_candles"], 3),
        "price_reference": str(form_values[f"{prefix}_pending_price_reference"]),
        "candle_reference": str(form_values[f"{prefix}_pending_candle_reference"]),
        "distance": _float(form_values[f"{prefix}_pending_order_distance"], 0.0),
        "expiration": _parse_expiration(form_values[f"{prefix}_pending_expiration"]),
    }
    return {
        "order_type": order_type,
        "pending": pending_config if order_type == "Pendente" else {},
    }


def _build_signal_config(form_values: dict[str, Any]) -> dict[str, Any]:
    signal_settings: dict[str, Any] = {"rules": []}
    for slot_number in range(1, 5):
        indicator_name = str(form_values[f"signal_indicator_{slot_number}"])
        signal_settings[f"indicator_{slot_number}"] = indicator_name
        signal_settings[f"indicator_{slot_number}_parameters"] = (
            {}
            if indicator_name == "Nao usar"
            else {
                "period": _int(form_values[f"signal_indicator_period_{slot_number}"], 14),
                "price_mode": str(form_values[f"signal_indicator_price_mode_{slot_number}"]),
            }
        )

    for rule_index in range(5):
        signal_settings["rules"].append(
            {
                "logical_command": str(form_values[f"signal_rule_{rule_index}_logical_command"]),
                "source_a": _source_payload(form_values[f"signal_rule_{rule_index}_source_a"]),
                "candle_a": _candle_payload(form_values[f"signal_rule_{rule_index}_candle_a"]),
                "operator": {
                    "value": str(form_values[f"signal_rule_{rule_index}_operator"]),
                    "label": SIGNAL_RULE_OPERATOR_LABELS.get(
                        str(form_values[f"signal_rule_{rule_index}_operator"]),
                        str(form_values[f"signal_rule_{rule_index}_operator"]),
                    ),
                },
                "source_b": _source_payload(form_values[f"signal_rule_{rule_index}_source_b"]),
                "candle_b": _candle_payload(form_values[f"signal_rule_{rule_index}_candle_b"]),
            }
        )

    band_parameters = {
        "period": _int(form_values["band_channels_period"], 20),
        "deviation": _float(form_values["band_channels_deviation"], 2.0),
        "displacement": _int(form_values["band_channels_displacement"], 0),
        "ma_type": str(form_values["band_channels_ma_type"]),
        "price_mode": str(form_values["band_channels_price_mode"]),
    }
    crossover_fast_source = str(form_values["crossover_fast_source"])
    crossover_slow_source = str(form_values["crossover_slow_source"])
    overbought_indicator = str(form_values["overbought_oversold_indicator"])

    return {
        "ready_signals": {
            "signal_settings": signal_settings,
            "band_channels": {
                "enabled": str(form_values["band_channels_enabled"]) == "Sim",
                "indicator": str(form_values["band_channels_indicator"]),
                "parameters": band_parameters,
                "period": band_parameters["period"],
                "deviation": band_parameters["deviation"],
                "signal": str(form_values["band_channels_signal"]),
            },
            "crossovers": {
                "enabled": str(form_values["crossover_enabled"]) == "Sim",
                "fast_source": crossover_fast_source,
                "fast_parameters": _simple_indicator_parameters(
                    crossover_fast_source,
                    _int(form_values["crossover_fast_period"], 21),
                ),
                "slow_source": crossover_slow_source,
                "slow_parameters": _simple_indicator_parameters(
                    crossover_slow_source,
                    _int(form_values["crossover_slow_period"], 21),
                ),
                "fast_indicator": crossover_fast_source,
                "fast_period": _int(form_values["crossover_fast_period"], 21),
                "slow_indicator": crossover_slow_source,
                "slow_period": _int(form_values["crossover_slow_period"], 21),
                "signal": str(form_values["crossover_signal"]),
            },
            "overbought_oversold": {
                "enabled": str(form_values["overbought_oversold_signal"]) != "Nao usar",
                "indicator": overbought_indicator,
                "indicator_output": str(form_values["overbought_oversold_output"]),
                "parameters": _simple_indicator_parameters(
                    overbought_indicator,
                    _int(form_values["overbought_oversold_period"], 14),
                ),
                "period": _int(form_values["overbought_oversold_period"], 14),
                "overbought_level": _float(form_values["overbought_level"], 70.0),
                "oversold_level": _float(form_values["oversold_level"], 30.0),
                "signal": str(form_values["overbought_oversold_signal"]),
            },
        }
    }


def _source_payload(raw_value: Any) -> dict[str, Any]:
    value = str(raw_value)
    return {
        "value": value,
        "label": SIGNAL_RULE_SOURCE_LABELS.get(value, value.replace("PRICE:", "price:")),
    }


def _candle_payload(raw_value: Any) -> dict[str, Any]:
    value = str(raw_value)
    return {
        "value": int(value),
        "label": SIGNAL_RULE_CANDLE_LABELS.get(value, value),
    }


def _simple_indicator_parameters(indicator_name: str, period: int) -> dict[str, Any]:
    if indicator_name in {"Nao usar", "Fechamento da vela", "Abertura da vela", "Maxima da vela", "Minima da vela"}:
        return {}
    return {"period": period}


def _build_builder_ui_options(form_values: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    signal_output_options: dict[int, list[str]] = {}
    current_signal_outputs: dict[int, str] = {}
    for slot_number in range(1, 5):
        indicator_name = str(form_values[f"signal_indicator_{slot_number}"])
        outputs = SIGNAL_INDICATOR_OUTPUT_LABELS.get(indicator_name, ["Valor"])
        signal_output_options[slot_number] = outputs
        current_output = str(form_values[f"signal_indicator_output_{slot_number}"])
        current_signal_outputs[slot_number] = current_output if current_output in outputs else outputs[0]
        form_values[f"signal_indicator_output_{slot_number}"] = current_signal_outputs[slot_number]

    rule_source_options = [{"value": "NONE", "label": SIGNAL_RULE_SOURCE_LABELS["NONE"]}]
    for special_key, label in SIGNAL_RULE_SOURCE_LABELS.items():
        if special_key == "NONE":
            continue
        rule_source_options.append({"value": special_key, "label": label})
    for price_field in ["close", "open", "high", "low"]:
        rule_source_options.append({"value": f"PRICE:{price_field}", "label": f"Preco: {price_field}"})
    for slot_number in range(1, 5):
        indicator_name = str(form_values[f"signal_indicator_{slot_number}"])
        if indicator_name == "Nao usar":
            continue
        output_name = current_signal_outputs[slot_number]
        rule_source_options.append(
            {
                "value": f"INDICATOR_{slot_number}:{output_name}",
                "label": f"Indicador {slot_number}: {indicator_name} / {output_name}",
            }
        )

    selected_symbol = str(form_values.get("selected_symbol") or "")
    if not selected_symbol and state.get("symbols"):
        selected_symbol = str(state["symbols"][0])
        form_values["selected_symbol"] = selected_symbol

    return {
        "yes_no_options": YES_NO_OPTIONS,
        "symbols": state.get("symbols") or [],
        "selected_symbol": selected_symbol,
        "primary_timeframe_options": PRIMARY_TIMEFRAME_OPTIONS,
        "market_period_options": MARKET_PERIOD_OPTIONS,
        "target_market_options": TARGET_MARKET_OPTIONS,
        "operational_type_options": OPERATIONAL_TYPE_OPTIONS,
        "processing_mode_options": PROCESSING_MODE_OPTIONS,
        "stop_types": STOP_TYPES,
        "stop_calculation_options": STOP_CALCULATION_OPTIONS,
        "stop_price_reference_options": STOP_PRICE_REFERENCE_OPTIONS,
        "stop_candle_reference_options": STOP_CANDLE_REFERENCE_OPTIONS,
        "stop_media_reference_options": STOP_MEDIA_REFERENCE_OPTIONS,
        "stop_movel_mode_options": STOP_MOVEL_MODE_OPTIONS,
        "distance_calculation_options": DISTANCE_CALCULATION_OPTIONS,
        "order_execution_options": ORDER_EXECUTION_OPTIONS,
        "pending_position_options": PENDING_POSITION_OPTIONS,
        "pending_price_reference_options": PENDING_PRICE_REFERENCE_OPTIONS,
        "pending_candle_reference_options": PENDING_CANDLE_REFERENCE_OPTIONS,
        "pending_expiration_options": PENDING_EXPIRATION_OPTIONS,
        "signal_indicator_options": READY_SIGNAL_INDICATOR_OPTIONS,
        "signal_indicator_output_options": signal_output_options,
        "signal_logical_command_options": SIGNAL_LOGICAL_COMMAND_OPTIONS,
        "signal_rule_operator_options": list(SIGNAL_RULE_OPERATOR_LABELS.items()),
        "signal_rule_candle_options": list(SIGNAL_RULE_CANDLE_LABELS.items()),
        "signal_rule_source_options": rule_source_options,
        "band_channel_indicator_options": BAND_CHANNEL_INDICATOR_OPTIONS,
        "band_channel_signal_options": BAND_CHANNEL_SIGNAL_OPTIONS,
        "crossover_source_options": CROSSOVER_SOURCE_OPTIONS,
        "overbought_indicator_options": OVERBOUGHT_OVERSOLD_INDICATOR_OPTIONS,
        "overbought_signal_options": ["Nao usar", *BAND_CHANNEL_SIGNAL_OPTIONS],
        "final_adjustment_fields": FINAL_ADJUSTMENT_FIELDS,
    }


def _build_backtest_view(backtest_result: Any, market_data: Any) -> dict[str, Any] | None:
    if not isinstance(backtest_result, dict):
        return None

    trades = backtest_result.get("trades")
    performance_curve = backtest_result.get("performance_curve")
    return {
        "summary": backtest_result.get("summary") or {},
        "ambiguous_entries": backtest_result.get("ambiguous_entries", 0),
        "trades_rows": frame_to_records(trades),
        "trades_columns": frame_columns(trades),
        "performance_chart": build_performance_chart(performance_curve),
        "price_chart": _build_price_chart(market_data, trades),
    }


def _build_price_chart(market_data: Any, trades: Any) -> dict[str, Any] | None:
    if not isinstance(market_data, pd.DataFrame) or market_data.empty:
        return None

    price_data = market_data.loc[:, ["time", "close"]].copy()
    price_data["time"] = price_data["time"].astype(str)
    chart: dict[str, Any] = {
        "prices": [
            {"time": row["time"], "close": float(row["close"])}
            for row in price_data.to_dict(orient="records")
        ],
        "entries": [],
        "exits": [],
    }

    if not isinstance(trades, pd.DataFrame) or trades.empty:
        return chart

    entry_points = trades.loc[:, ["entry_time", "entry_price", "side", "pnl"]].copy()
    entry_points["entry_time"] = entry_points["entry_time"].astype(str)
    chart["entries"] = [
        {
            "value": [row["entry_time"], float(row["entry_price"])],
            "side": str(row["side"]),
            "pnl": float(row["pnl"]),
        }
        for row in entry_points.to_dict(orient="records")
    ]

    exit_points = trades.loc[:, ["exit_time", "exit_price", "side", "pnl"]].copy()
    exit_points["exit_time"] = exit_points["exit_time"].astype(str)
    chart["exits"] = [
        {
            "value": [row["exit_time"], float(row["exit_price"])],
            "side": str(row["side"]),
            "pnl": float(row["pnl"]),
        }
        for row in exit_points.to_dict(orient="records")
    ]
    return chart


def _parse_date(raw_value: Any) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value))
    except ValueError:
        return None


def _parse_expiration(raw_value: Any) -> str | int:
    value = str(raw_value)
    if value == "Nao expirar":
        return value
    return _int(value, 1)


def _int(raw_value: Any, default: int) -> int:
    try:
        return int(str(raw_value))
    except (TypeError, ValueError):
        return default


def _float(raw_value: Any, default: float) -> float:
    try:
        return float(str(raw_value))
    except (TypeError, ValueError):
        return default


def _pad(raw_value: Any) -> str:
    return f"{_int(raw_value, 0):02d}"
