(function () {
  function parseConfig(node) {
    const raw = node.getAttribute("data-chart-config");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return null;
    }
  }

  function chartInstance(node) {
    return echarts.getInstanceByDom(node) || echarts.init(node);
  }

  function renderBuilderPrice(node, data) {
    const instance = chartInstance(node);
    instance.setOption({
      animationDuration: 350,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
      },
      legend: { top: 0 },
      grid: { left: 48, right: 24, top: 36, bottom: 40 },
      xAxis: { type: "category", boundaryGap: false, data: data.prices.map((item) => item.time) },
      yAxis: { type: "value", scale: true },
      series: [
        {
          name: "Preco",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: data.prices.map((item) => item.close),
          lineStyle: { color: "#0d5c91", width: 2 },
          areaStyle: { color: "rgba(13,92,145,0.10)" },
        },
        {
          name: "Entradas",
          type: "scatter",
          symbol: "triangle",
          symbolRotate: 0,
          symbolSize: 14,
          itemStyle: { color: "#12715b" },
          data: data.entries.map((item) => ({ value: item.value })),
        },
        {
          name: "Saidas",
          type: "scatter",
          symbol: "triangle",
          symbolRotate: 180,
          symbolSize: 14,
          itemStyle: { color: "#b54646" },
          data: data.exits.map((item) => ({ value: item.value })),
        },
      ],
    });
  }

  function renderBuilderEquity(node, data) {
    const instance = chartInstance(node);
    instance.setOption({
      animationDuration: 350,
      tooltip: { trigger: "axis" },
      grid: { left: 48, right: 24, top: 24, bottom: 40 },
      xAxis: { type: "category", boundaryGap: false, data: data.labels },
      yAxis: { type: "value", scale: true },
      series: [
        {
          type: "line",
          smooth: true,
          showSymbol: false,
          data: data.equity,
          lineStyle: { color: "#0d5c91", width: 2 },
          areaStyle: { color: "rgba(13,92,145,0.14)" },
        },
      ],
    });
  }

  function renderBuilderDrawdown(node, data) {
    const instance = chartInstance(node);
    instance.setOption({
      animationDuration: 350,
      tooltip: { trigger: "axis" },
      grid: { left: 48, right: 24, top: 24, bottom: 40 },
      xAxis: { type: "category", data: data.labels },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          data: data.drawdown,
          itemStyle: { color: "#c77d24", borderRadius: [6, 6, 0, 0] },
        },
      ],
    });
  }

  function renderWalkForward(node, data) {
    const instance = chartInstance(node);
    instance.setOption({
      animationDuration: 350,
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 48, right: 24, top: 36, bottom: 40 },
      xAxis: { type: "category", data: data.labels },
      yAxis: [
        { type: "value", name: "Score" },
        { type: "value", name: "Pass %" },
      ],
      series: [
        {
          name: "Score",
          type: "bar",
          data: data.scores,
          itemStyle: { color: "#0d5c91", borderRadius: [6, 6, 0, 0] },
        },
        {
          name: "Estabilidade",
          type: "line",
          smooth: true,
          yAxisIndex: 0,
          data: data.stability,
          lineStyle: { color: "#12715b", width: 2 },
        },
        {
          name: "Pass rate %",
          type: "line",
          smooth: true,
          yAxisIndex: 1,
          data: data.pass_rate,
          lineStyle: { color: "#c77d24", width: 2 },
        },
      ],
    });
  }

  function renderStrategyPerformance(node, data) {
    const instance = chartInstance(node);
    instance.setOption({
      animationDuration: 350,
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      grid: { left: 48, right: 24, top: 36, bottom: 40 },
      xAxis: { type: "category", data: data.labels },
      yAxis: [
        { type: "value", name: "Equity" },
        { type: "value", name: "PnL" },
      ],
      series: [
        {
          name: "Equity",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: data.equity,
          lineStyle: { color: "#0d5c91", width: 2 },
        },
        {
          name: "Drawdown",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: data.drawdown,
          lineStyle: { color: "#c77d24", width: 2 },
        },
        {
          name: "PnL",
          type: "bar",
          yAxisIndex: 1,
          data: data.pnl,
          itemStyle: { color: "#12715b", borderRadius: [6, 6, 0, 0] },
        },
      ],
    });
  }

  function initCharts(root) {
    root.querySelectorAll("[data-chart-config]").forEach((node) => {
      const config = parseConfig(node);
      if (!config) return;
      if (config.type === "builder-price") renderBuilderPrice(node, config.data);
      if (config.type === "builder-equity") renderBuilderEquity(node, config.data);
      if (config.type === "builder-drawdown") renderBuilderDrawdown(node, config.data);
      if (config.type === "walkforward") renderWalkForward(node, config.data);
      if (config.type === "strategy-performance") renderStrategyPerformance(node, config.data);
    });
  }

  function syncAccordionState(root) {
    const input = root.querySelector("#open-accordions-input");
    if (!input) return;
    const values = Array.from(root.querySelectorAll(".accordion-collapse.show[data-accordion-id]")).map((node) => node.dataset.accordionId);
    input.value = values.join(",");
  }

  function initBuilder(root) {
    const form = root.querySelector("#builder-form");
    if (!form) return;

    const activeInput = form.querySelector("#active-tab-input");
    if (activeInput) {
      const trigger = form.querySelector(`[data-builder-tab="${activeInput.value}"]`);
      if (trigger) bootstrap.Tab.getOrCreateInstance(trigger).show();
      form.querySelectorAll("[data-builder-tab]").forEach((element) => {
        element.addEventListener("shown.bs.tab", (event) => {
          activeInput.value = event.target.dataset.builderTab || "connection";
        });
      });
    }

    form.querySelectorAll(".accordion-collapse[data-accordion-id]").forEach((collapseNode) => {
      collapseNode.addEventListener("shown.bs.collapse", function () {
        syncAccordionState(root);
      });
      collapseNode.addEventListener("hidden.bs.collapse", function () {
        syncAccordionState(root);
      });
    });
    syncAccordionState(root);
  }

  function init(root) {
    initBuilder(root);
    initCharts(root);
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });

  document.body.addEventListener("htmx:afterSwap", function (event) {
    init(event.target);
  });

  window.addEventListener("resize", function () {
    document.querySelectorAll(".af-echart").forEach((node) => {
      const instance = echarts.getInstanceByDom(node);
      if (instance) instance.resize();
    });
  });
})();
