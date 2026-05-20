const state = {
  payload: null,
  archive: { latest: null, dates: [] },
  activeTicker: "",
  priceChart: null,
  scoreChart: null,
  sentimentChart: null,
};

const numberFmt = new Intl.NumberFormat("ko-KR");
const compactFmt = new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 });

function $(selector) {
  return document.querySelector(selector);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatPct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${(Number(value) * 100).toFixed(digits)}%`;
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return numberFmt.format(Number(value).toFixed(digits));
}

function formatPrice(value, market) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const digits = market === "KR" || Number(value) >= 1000 ? 0 : 2;
  return formatNumber(value, digits);
}

function dateLabel(value) {
  if (!value) return "-";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric", weekday: "short" });
}

function relevanceClass(level) {
  if (level === "direct") return "good";
  if (level === "partial" || level === "theme") return "warn";
  return "bad";
}

function stanceClass(candidate) {
  if (candidate.agentView === "after_move_watch" || candidate.risk.chasePenalty >= 0.2) return "bad";
  if (candidate.agentView === "watch_with_chase_risk" || candidate.risk.chasePenalty > 0) return "warn";
  return "good";
}

function setupClass(setup) {
  if (!setup) return "warn";
  if (setup.action === "avoid_chase" || setup.action === "risk_watch" || setup.score < 0.35) return "bad";
  if (setup.score >= 0.65 || setup.action === "breakout_watch" || setup.action === "pullback_watch") return "good";
  return "warn";
}

function candidateLabel(candidate) {
  return candidate.name ? `${candidate.ticker} · ${candidate.name}` : candidate.ticker;
}

function renderArchiveControls(activeDate) {
  const dates = state.archive.dates || [];
  $("#dateScroller").innerHTML = dates.length
    ? dates
        .map(
          (item) => `
            <button type="button" class="${item.date === activeDate ? "active" : ""}" data-date="${escapeHtml(item.date)}">
              <strong>${escapeHtml(dateLabel(item.date))}</strong>
              <span>${escapeHtml(item.candidateCount || 0)} 후보 · ${escapeHtml(item.avgScore ?? "-")}</span>
            </button>
          `,
        )
        .join("")
    : `<button type="button" class="active"><strong>Latest</strong><span>로컬 스냅샷</span></button>`;
  $("#dateScroller").querySelectorAll("[data-date]").forEach((button) => {
    button.addEventListener("click", () => loadPayloadForDate(button.dataset.date));
  });
}

function renderKpis(payload) {
  const summary = payload.summary;
  const items = [
    ["후보 수", `${summary.candidateCount}`, `${summary.availableSeriesCount || 0}개 후보는 가격 시계열 포함`],
    ["평균 점수", summary.avgScore.toFixed(3), "뉴스, 차트, 수급, 추격 리스크 조정"],
    ["트레이딩 셋업", `${summary.actionableSetupCount || 0}`, `${summary.highQualitySetupCount || 0}개는 점수 0.65 이상`],
    ["추격 리스크", `${summary.chaseRiskCount}`, "급등/선반영 가능성을 별도 감점"],
  ];
  $("#kpiGrid").innerHTML = items
    .map(
      ([label, value, note]) => `
        <article class="kpi">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
          <em>${escapeHtml(note)}</em>
        </article>
      `,
    )
    .join("");
}

function renderThesis(payload) {
  const summary = payload.summary;
  let thesis = "뉴스 촉매와 차트 구조를 함께 검증합니다.";
  if ((summary.themeNewsCount || 0) + summary.weakNewsCount > summary.directNewsCount + (summary.partialNewsCount || 0)) {
    thesis = "오늘의 핵심은 뉴스 직접성 필터입니다.";
  } else if (summary.chaseRiskCount >= Math.ceil(summary.candidateCount / 3)) {
    thesis = "후보는 많지만 가격 선반영 리스크가 높습니다.";
  } else if (payload.themes[0]) {
    thesis = `${payload.themes[0].name} 테마가 가장 강하게 포착됩니다.`;
  }
  $("#marketThesis").textContent = thesis;
  $("#reportSubtitle").textContent = payload.reportSubtitle;
  $("#generatedAt").textContent = `${payload.archive?.date || "Latest"} · Generated ${new Date(payload.generatedAt).toLocaleString("ko-KR")}`;
  $("#sourceDiscovery").textContent = `Source discovery: ${payload.sourceDiscovery}`;
}

function renderTickerSwitcher(payload) {
  $("#tickerSwitcher").innerHTML = payload.candidates
    .filter((candidate) => candidate.series.length)
    .slice(0, 8)
    .map((candidate) => `<button type="button" data-ticker="${escapeHtml(candidate.ticker)}">${escapeHtml(candidate.ticker)}</button>`)
    .join("");
  $("#tickerSwitcher").querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => setActiveTicker(button.dataset.ticker));
  });
}

function renderMemo(candidate) {
  const setup = candidate.setup || {};
  const reaction = candidate.marketReaction || {};
  const primaryEvent = candidate.catalyst?.events?.[0] || {};
  const entry =
    setup.entry?.low !== null && setup.entry?.low !== undefined && setup.entry?.high !== null && setup.entry?.high !== undefined
      ? `${formatPrice(setup.entry.low, candidate.market)}~${formatPrice(setup.entry.high, candidate.market)}`
      : "-";
  $("#focusTitle").textContent = candidateLabel(candidate);
  $("#memoHeadline").textContent = setup.thesis || candidate.catalyst.claim || candidate.news.read || "촉매 확인 필요";
  $("#memoStats").innerHTML = `
    <div><dt>Score</dt><dd>${candidate.score.toFixed(3)}</dd></div>
    <div><dt>Setup</dt><dd>${escapeHtml(setup.label || "-")}</dd></div>
    <div><dt>Entry</dt><dd>${escapeHtml(entry)}</dd></div>
    <div><dt>Stop</dt><dd>${formatPrice(setup.stopLoss, candidate.market)}</dd></div>
    <div><dt>Target</dt><dd>${formatPrice(setup.target1, candidate.market)}</dd></div>
    <div><dt>R/R</dt><dd>${setup.riskReward ? setup.riskReward.toFixed(2) : "-"}</dd></div>
    <div><dt>MR</dt><dd>${reaction.reactionScore === null || reaction.reactionScore === undefined ? "-" : Number(reaction.reactionScore).toFixed(2)}</dd></div>
    <div><dt>Vol Z</dt><dd>${reaction.volumeZscore === null || reaction.volumeZscore === undefined ? "-" : Number(reaction.volumeZscore).toFixed(1)}</dd></div>
  `;
  $("#memoRead").textContent =
    [setup.invalidation, candidate.news.read].filter(Boolean).join(" · ") ||
    "뉴스 촉매가 충분하지 않아 가격 구조, 지지/저항, 거래량 확인을 먼저 해야 합니다.";
  $("#qualityStrip").innerHTML = [
    `<span class="quality-pill ${setupClass(setup)}">Setup ${Number(setup.score || 0).toFixed(2)}</span>`,
    `<span class="quality-pill ${relevanceClass(candidate.news.relevance.level)}">${escapeHtml(candidate.news.relevance.label)}</span>`,
    `<span class="quality-pill ${stanceClass(candidate)}">${escapeHtml(candidate.stance)}</span>`,
    `<span class="quality-pill">RS ${escapeHtml(candidate.technical.momentum || "-")}</span>`,
    `<span class="quality-pill">Priced ${escapeHtml(primaryEvent.priced_in_risk || "-")}</span>`,
  ].join("");
}

function priceDatasets(candidate) {
  const series = candidate.series;
  const volumeScale = Math.max(...series.map((item) => Number(item.volume || 0)), 1);
  const volumeUnit = volumeScale >= 1_000_000 ? 1_000_000 : 1;
  return [
    {
      type: "bar",
      label: volumeUnit === 1_000_000 ? "Volume (M)" : "Volume",
      data: series.map((item) => (Number(item.volume || 0) / volumeUnit).toFixed(2)),
      yAxisID: "volume",
      backgroundColor: "rgba(49, 91, 157, 0.16)",
      borderColor: "rgba(49, 91, 157, 0)",
      borderRadius: 3,
      order: 4,
    },
    {
      type: "line",
      label: "Close",
      data: series.map((item) => item.close),
      borderColor: "#111918",
      backgroundColor: "rgba(17, 25, 24, 0.06)",
      borderWidth: 2.2,
      tension: 0.22,
      pointRadius: 0,
      order: 1,
    },
    {
      type: "line",
      label: "SMA20",
      data: series.map((item) => item.sma20),
      borderColor: "#0f766e",
      borderWidth: 1.5,
      tension: 0.18,
      pointRadius: 0,
      order: 2,
    },
    {
      type: "line",
      label: "SMA50",
      data: series.map((item) => item.sma50),
      borderColor: "#c47a11",
      borderWidth: 1.4,
      borderDash: [5, 4],
      tension: 0.18,
      pointRadius: 0,
      order: 3,
    },
  ];
}

function renderPriceChart(candidate) {
  const chartEmpty = $("#chartEmpty");
  const ctx = $("#priceChart");
  const hasSeries = candidate.series.length > 2;
  chartEmpty.hidden = hasSeries;
  ctx.hidden = !hasSeries;
  if (state.priceChart) state.priceChart.destroy();
  if (!hasSeries) return;

  state.priceChart = new Chart(ctx, {
    data: {
      labels: candidate.series.map((item) => String(item.date).slice(0, 10)),
      datasets: priceDatasets(candidate),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          position: "top",
          align: "end",
          labels: { boxWidth: 10, boxHeight: 10, color: "#344047", font: { size: 11, weight: "700" } },
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed.y;
              if (context.dataset.yAxisID === "volume") return `${context.dataset.label}: ${compactFmt.format(value)}`;
              return `${context.dataset.label}: ${formatPrice(value, candidate.market)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#68717a", maxTicksLimit: 9, font: { size: 11 } },
        },
        y: {
          position: "left",
          grid: { color: "rgba(23, 27, 31, 0.08)" },
          ticks: {
            color: "#68717a",
            callback: (value) => formatPrice(value, candidate.market),
            font: { size: 11 },
          },
        },
        volume: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#68717a", callback: (value) => compactFmt.format(value), font: { size: 11 } },
        },
      },
    },
  });
}

function renderCandidateRows(payload) {
  $("#candidateRows").innerHTML = payload.candidates
    .map(
      (candidate) => `
        <tr data-ticker="${escapeHtml(candidate.ticker)}">
          <td>${candidate.rank}</td>
          <td class="ticker-cell">
            <strong>${escapeHtml(candidate.ticker)}</strong>
            <span>${escapeHtml(candidate.name || candidate.market)}</span>
          </td>
          <td class="score">${candidate.score.toFixed(3)}</td>
          <td><span class="quality-pill ${stanceClass(candidate)}">${escapeHtml(candidate.stance)}</span></td>
          <td><span class="quality-pill ${relevanceClass(candidate.news.relevance.level)}">${escapeHtml(candidate.news.relevance.label)}</span></td>
          <td><span class="quality-pill ${setupClass(candidate.setup)}">${escapeHtml(candidate.setup?.label || "-")}</span></td>
          <td>${formatPct(candidate.price.recentReturn20d)}</td>
          <td>${candidate.marketReaction?.reactionScore === null || candidate.marketReaction?.reactionScore === undefined ? "-" : Number(candidate.marketReaction.reactionScore).toFixed(2)}</td>
          <td>${escapeHtml(candidate.technical.structure || "-")}</td>
          <td>${escapeHtml(candidate.catalyst.claim || candidate.news.read || "-")}</td>
        </tr>
      `,
    )
    .join("");
  $("#candidateRows").querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => setActiveTicker(row.dataset.ticker));
  });
}

function renderOutcomes(payload) {
  const outcomes = payload.outcomes || {};
  const summary = outcomes.summary || {};
  const previousDate = outcomes.previousDate;
  $("#outcomeCaption").textContent = previousDate
    ? `${dateLabel(previousDate)} 후보를 ${dateLabel(outcomes.currentDate)} 기준으로 점검`
    : "다음 날짜 스냅샷이 쌓이면 자동으로 전일 후보 성과를 계산합니다.";
  const avg = summary.averageReturn === null || summary.averageReturn === undefined ? "-" : formatPct(summary.averageReturn);
  const hitRate =
    summary.withPriceCount > 0 ? `${Math.round((summary.positiveCount / summary.withPriceCount) * 100)}%` : "-";
  const boxes = [
    ["추적 후보", summary.trackedCount || 0, `${summary.withPriceCount || 0}개 가격 확인`],
    ["상승 후보", summary.positiveCount || 0, `하락 ${summary.negativeCount || 0}`],
    ["평균 수익률", avg, "전일 스냅샷 기준"],
    ["Hit Rate", hitRate, "단순 익일 양수 비율"],
  ];
  $("#outcomeSummary").innerHTML = boxes
    .map(
      ([label, value, note]) => `
        <article class="outcome-kpi">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
          <em>${escapeHtml(note)}</em>
        </article>
      `,
    )
    .join("");

  const rows = outcomes.rows || [];
  $("#outcomeList").innerHTML = rows.length
    ? rows
        .slice(0, 12)
        .map((row) => {
          const cls = row.outcome === "up" ? "good" : row.outcome === "down" ? "bad" : "warn";
          return `
            <article class="outcome-card">
              <header>
                <span class="tag">${escapeHtml(row.ticker)}</span>
                <span class="quality-pill ${cls}">${formatPct(row.nextReturn)}</span>
              </header>
              <strong>${escapeHtml(row.name || row.ticker)}</strong>
              <p>${escapeHtml(row.previousStance || "-")} · ${escapeHtml(row.newsQuality || "-")}</p>
              <dl>
                <div><dt>전일 종가</dt><dd>${formatPrice(row.previousClose, row.ticker?.includes(".K") ? "KR" : "")}</dd></div>
                <div><dt>현재 종가</dt><dd>${formatPrice(row.currentClose, row.ticker?.includes(".K") ? "KR" : "")}</dd></div>
              </dl>
              <p>${escapeHtml(row.catalyst || "전일 촉매 없음")}</p>
            </article>
          `;
        })
        .join("")
    : `<article class="outcome-empty">${escapeHtml(outcomes.note || "아직 비교 가능한 이전 스냅샷이 없습니다.")}</article>`;
}

function renderThemes(payload) {
  $("#themeGrid").innerHTML = payload.themes
    .slice(0, 8)
    .map(
      (theme) => `
        <article class="theme-card">
          <span class="tag">${theme.heat}</span>
          <h3>${escapeHtml(theme.name)}</h3>
          <div class="heat-track"><div class="heat-bar" style="width:${theme.heat}%"></div></div>
          <p>${escapeHtml(theme.tickers.slice(0, 5).join(" · ") || "후보 없음")}</p>
          <p>긍정 ${theme.sentiment.positive} / 부정 ${theme.sentiment.negative} / 혼재 ${theme.sentiment.mixed}</p>
        </article>
      `,
    )
    .join("");
}

function renderNews(payload) {
  const cards = [];
  payload.candidates.slice(0, 8).forEach((candidate) => {
    const primary = candidate.news.headlines[0];
    const event = candidate.catalyst.events?.[0] || {};
    const evidence = event.evidence_spans?.[0]?.quote || "";
    cards.push({
      ticker: candidate.ticker,
      stance: primary?.stance || "mixed",
      source: primary?.source || candidate.catalyst.events?.[0]?.evidence_sources?.[0] || "source",
      title: primary?.title || candidate.catalyst.claim || candidate.news.read,
      relevance: candidate.news.relevance.label,
      read: candidate.news.read,
      evidence,
      eventType: [event.event_type, event.event_subtype].filter(Boolean).join(" / "),
    });
  });
  $("#newsGrid").innerHTML = cards
    .map(
      (card) => `
        <article class="news-card">
          <header>
            <span class="tag">${escapeHtml(card.ticker)}</span>
            <span class="quality-pill ${card.stance === "negative" ? "bad" : card.stance === "positive" ? "good" : "warn"}">${escapeHtml(card.stance)}</span>
          </header>
          <h3>${escapeHtml(card.title || "-")}</h3>
          <p>${escapeHtml(card.read || "추가 원문 확인 필요")}</p>
          <p>${escapeHtml(card.evidence || "원문 evidence span 없음")}</p>
          <p>${escapeHtml(card.relevance)} · ${escapeHtml(card.eventType || "event")} · ${escapeHtml(card.source)}</p>
        </article>
      `,
    )
    .join("");
}

function renderRisk(payload) {
  const notes = [
    {
      title: "트레이딩 셋업",
      body: `${payload.summary.actionableSetupCount || 0}개 후보는 돌파/눌림/롱 감시 셋업이 잡혔고, ${payload.summary.highQualitySetupCount || 0}개는 셋업 점수 0.65 이상입니다.`,
    },
    {
      title: "뉴스 직접성",
      body: `${payload.summary.partialNewsCount || 0}개는 부분 직접, ${payload.summary.themeNewsCount || 0}개는 테마 관련입니다. 핵심 촉매 원문을 먼저 확인해야 합니다.`,
    },
    {
      title: "가격 선반영",
      body: `${payload.summary.chaseRiskCount}개 후보는 급등/상한가/추격 리스크 감점이 적용됐습니다.`,
    },
    {
      title: "무효화 기준",
      body: "각 후보의 지지선 하향 이탈, 거래량 없는 돌파, 부정 공시를 우선 리스크로 봅니다.",
    },
  ];
  $("#riskGrid").innerHTML = notes
    .map(
      (note) => `
        <article class="risk-item">
          <strong>${escapeHtml(note.title)}</strong>
          <p>${escapeHtml(note.body)}</p>
        </article>
      `,
    )
    .join("");
}

function renderScoreChart(payload) {
  if (state.scoreChart) state.scoreChart.destroy();
  const top = payload.candidates.slice(0, 10).reverse();
  state.scoreChart = new Chart($("#scoreChart"), {
    type: "bar",
    data: {
      labels: top.map((candidate) => candidate.ticker),
      datasets: [
        {
          label: "Score",
          data: top.map((candidate) => candidate.score),
          backgroundColor: top.map((candidate) =>
            candidate.news.relevance.level === "weak" ? "rgba(189, 61, 53, 0.72)" : "rgba(15, 118, 110, 0.78)",
          ),
          borderRadius: 5,
          borderSkipped: false,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "rgba(23, 27, 31, 0.08)" }, ticks: { color: "#68717a" } },
        y: { grid: { display: false }, ticks: { color: "#344047", font: { weight: "700" } } },
      },
    },
  });
}

function renderSentimentChart(payload) {
  if (state.sentimentChart) state.sentimentChart.destroy();
  const sentiment = payload.summary.sentiment;
  state.sentimentChart = new Chart($("#sentimentChart"), {
    type: "doughnut",
    data: {
      labels: ["긍정", "부정", "혼재"],
      datasets: [
        {
          data: [sentiment.positive, sentiment.negative, sentiment.mixed],
          backgroundColor: ["#0f766e", "#bd3d35", "#c47a11"],
          borderColor: "#ffffff",
          borderWidth: 4,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "66%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#344047", font: { weight: "700" } },
        },
      },
    },
  });
}

function setActiveTicker(ticker) {
  const payload = state.payload;
  const candidate = payload.candidates.find((item) => item.ticker === ticker) || payload.candidates[0];
  if (!candidate) return;
  state.activeTicker = candidate.ticker;
  renderMemo(candidate);
  renderPriceChart(candidate);
  document.querySelectorAll("[data-ticker]").forEach((node) => {
    node.classList.toggle("active", node.dataset.ticker === candidate.ticker);
  });
}

function renderAll(payload) {
  state.payload = payload;
  renderArchiveControls(payload.archive?.date);
  renderThesis(payload);
  renderKpis(payload);
  renderOutcomes(payload);
  renderTickerSwitcher(payload);
  renderCandidateRows(payload);
  renderThemes(payload);
  renderNews(payload);
  renderRisk(payload);
  renderScoreChart(payload);
  renderSentimentChart(payload);
  setActiveTicker(payload.focusTicker || payload.candidates[0]?.ticker);
}

async function loadPayloadForDate(date) {
  const item = state.archive.dates.find((entry) => entry.date === date);
  if (!item) return;
  const response = await fetch(`./${item.path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Failed to load report-data.json: ${response.status}`);
  const payload = await response.json();
  renderAll(payload);
}

async function init() {
  let payload;
  try {
    const indexResponse = await fetch("./data/index.json", { cache: "no-store" });
    if (indexResponse.ok) {
      state.archive = await indexResponse.json();
    }
  } catch {
    state.archive = { latest: null, dates: [] };
  }

  if (state.archive.latest) {
    const latest = state.archive.dates.find((entry) => entry.date === state.archive.latest) || state.archive.dates[0];
    const response = await fetch(`./${latest.path}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load ${latest.path}: ${response.status}`);
    payload = await response.json();
  } else {
    const response = await fetch("./report-data.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Failed to load report-data.json: ${response.status}`);
    payload = await response.json();
  }
  renderAll(payload);
}

init().catch((error) => {
  console.error(error);
  $("#marketThesis").textContent = "리포트 데이터를 불러오지 못했습니다.";
  $("#reportSubtitle").textContent = String(error);
});
