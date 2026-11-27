// Painel de Receita · Hotéis de Port Alder
// Lê window.DADOS (gerado por scripts/gerar_dados_dashboard.py), aplica os
// filtros e redesenha KPIs, gráficos e tabela ao mesmo tempo.

const D = window.DADOS || { hoteis: [], cenarios_info: [], mensal: [], avaliacoes: [], cenarios: [], decisoes: [], relacoes: [], tabelas: [], interativo: {} };
const ANALISES = window.ANALISES || [];

const TIERS = ["luxury", "upscale", "boutique", "midscale", "economy"];
const NOME_TIER = { luxury: "Luxo", upscale: "Superior", boutique: "Boutique", midscale: "Intermediário", economy: "Econômico" };
const NOME_ACAO = { raise: "Aumentar", hold: "Manter", lower: "Reduzir" };
const RESULTADOS = [["better", "Melhor"], ["in line", "Estável"], ["worse", "Pior"]];
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

const hotelPorId = Object.fromEntries(D.hoteis.map(h => [h.id, h]));
const cenarioPorId = Object.fromEntries(D.cenarios_info.map(c => [c.id, c]));
// Nomes dos cenários e ações traduzidos (o dataset vem em inglês)
const CENARIO_PT = {
  delight: ["Superou expectativas", "agradecer o hóspede e registrar o funcionário"],
  location: ["Localização e acesso", "nenhuma ação necessária"],
  breakfast: ["Café da manhã e comida", "convidar o hóspede a voltar e revisar o bufê"],
  service_recovery: ["Problema resolvido bem", "registrar a solução e orientar o turno"],
  room_condition: ["Estado do quarto", "bloquear o quarto e abrir ordem de manutenção"],
  noise: ["Barulho e sono", "oferecer troca de quarto e kit de sono"],
  checkin_wait: ["Fila no check-in", "reforçar a recepção nos horários de pico"],
  billing: ["Cobrança e tarifas", "auditar a conta e reembolsar se devido"],
  wifi: ["Wi-Fi e conexão", "enviar o log do ponto de acesso para a TI"],
  cleanliness: ["Limpeza", "limpar de novo, inspecionar e orientar a equipe"],
  group_trip: ["Grupo ou família", "confirmar a distribuição dos quartos antes da chegada"],
};
for (const [id, [nome, acao]] of Object.entries(CENARIO_PT)) {
  if (cenarioPorId[id]) Object.assign(cenarioPorId[id], { nome, acao });
}

// ---------- Formatação ----------
const fmtNum = (v, casas = 0) => v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const fmtPct = (v, casas = 1) => fmtNum(v * 100, casas) + "%";
const fmtUSD = v => "US$ " + fmtNum(v, 0);
function fmtMilhoes(v) {
  return v >= 1e6 ? "US$ " + fmtNum(v / 1e6, 1) + " mi" : "US$ " + fmtNum(v / 1e3, 0) + " mil";
}

// ---------- Estado dos filtros ----------
const estado = { ano: "todos", tier: "todos", hotel: "todos", busca: "", aba: "geral", grupo: "Todos", metrica: "ocup", sazMetrica: "ocup", ordem: { col: "receita", asc: false } };

function passaFiltro(linha) {
  const h = hotelPorId[linha.h];
  if (estado.ano !== "todos" && String(linha.a) !== estado.ano) return false;
  if (estado.tier !== "todos" && h.tier !== estado.tier) return false;
  if (estado.hotel !== "todos" && linha.h !== estado.hotel) return false;
  return true;
}

// ---------- Cálculos (sempre a partir de somas, nunca média de médias) ----------
function somar(linhas) {
  const t = { disp: 0, vend: 0, rec_q: 0, rec_t: 0, gop: 0, cs_rev: 0, cs_vend: 0, cs_rec: 0, mars: 0, noites_evento: 0, noites: 0, abaixo: 0, acima: 0, mars_soma: 0 };
  for (const l of linhas) for (const k in t) t[k] += l[k];
  return t;
}
function indicadores(t) {
  return {
    receita: t.rec_t,
    ocup: t.vend / t.disp,
    adr: t.rec_q / t.vend,
    revpar: t.rec_q / t.disp,
    rgi: (t.rec_q / t.cs_rev) * 100,
    ari: ((t.rec_q / t.vend) / (t.cs_rec / t.cs_vend)) * 100,
    mpi: (t.vend / t.cs_vend) * 100,
    cs_ocup: t.cs_vend / t.disp,
    cs_adr: t.cs_rec / t.cs_vend,
    cs_revpar: t.cs_rev / t.disp,
    mars: t.mars / t.vend,                       // MARS ponderado pelos quartos vendidos
    dif_mars: (t.rec_q / t.mars - 1) * 100,      // % do ADR acima (+) ou abaixo (−) do MARS
  };
}
function agruparPor(linhas, chave) {
  const g = new Map();
  for (const l of linhas) {
    const k = chave(l);
    if (!g.has(k)) g.set(k, []);
    g.get(k).push(l);
  }
  return g;
}

// ---------- Cores lidas do CSS (mudam com o tema) ----------
function cor(nome) { return getComputedStyle(document.documentElement).getPropertyValue(nome).trim(); }
function corTier(tier) { return cor("--serie-" + (TIERS.indexOf(tier) + 1)); }
const FORMA_TIER = { luxury: "circle", upscale: "rect", boutique: "triangle", midscale: "rectRot", economy: "crossRot" };

function configurarChartJs() {
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = cor("--texto-2");
  Chart.defaults.borderColor = cor("--grade");
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.tooltip.backgroundColor = cor("--superficie");
  Chart.defaults.plugins.tooltip.titleColor = cor("--texto");
  Chart.defaults.plugins.tooltip.bodyColor = cor("--texto");
  Chart.defaults.plugins.tooltip.borderColor = cor("--borda");
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.maintainAspectRatio = false;
  // Acabamento comum (guia de visualização): marcas finas, linhas de 2px,
  // pontas de barra arredondadas, grade discreta e dica com respiro.
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.line.borderCapStyle = "round";
  Chart.defaults.elements.line.borderJoinStyle = "round";
  Chart.defaults.elements.point.hoverRadius = 6;
  Chart.defaults.elements.point.hitRadius = 8;
  Chart.defaults.elements.bar.borderRadius = 4;
  Chart.defaults.datasets.bar.maxBarThickness = 24;
  Chart.defaults.scale.border = { display: false };
  Chart.defaults.scale.grid.drawTicks = false;
  Chart.defaults.scale.ticks.padding = 8;
  Chart.defaults.plugins.legend.labels.padding = 16;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 6;
  Chart.defaults.plugins.tooltip.boxPadding = 4;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "600" };
}

const graficos = {};
// Interatividade comum: gráficos de linha e dispersão ganham zoom (arrastar
// um retângulo ou pinça no celular) e duplo clique volta ao normal.
function desenhar(id, config) {
  const el = document.getElementById(id);
  if (!el) return;
  if (graficos[id]) graficos[id].destroy();
  const tipo = config.type;
  if ((tipo === "scatter" || tipo === "line") && window.ChartZoom !== undefined) {
    config.options = config.options || {};
    config.options.plugins = config.options.plugins || {};
    config.options.plugins.zoom = {
      zoom: { drag: { enabled: true, backgroundColor: "rgba(155,45,58,0.12)" }, pinch: { enabled: true }, mode: "xy" },
      pan: { enabled: true, mode: "xy", modifierKey: "shift" },
    };
  }
  graficos[id] = new Chart(el, config);
  if (config.options?.plugins?.zoom) {
    el.ondblclick = () => graficos[id].resetZoom();
    el.title = "Arraste para dar zoom · duplo clique para voltar · Shift + arrastar para mover";
  }
}
function cursorMao(evento, itens) {
  evento.native.target.style.cursor = itens.length ? "pointer" : "default";
}
function filtrarHotel(id) {
  estado.hotel = id;
  document.getElementById("f-hotel").value = id;
  atualizar();
}

// ---------- KPIs ----------
function atualizarKpis(mensal, aval) {
  const k = indicadores(somar(mensal));
  document.getElementById("k-receita").textContent = fmtMilhoes(k.receita);
  document.getElementById("k-ocup").textContent = fmtPct(k.ocup);
  document.getElementById("k-adr").textContent = fmtUSD(k.adr);
  document.getElementById("k-revpar").textContent = fmtUSD(k.revpar);
  document.getElementById("k-rgi").textContent = fmtNum(k.rgi, 1);
  const difRgi = k.rgi - 100;
  const subRgi = document.getElementById("k-rgi-sub");
  subRgi.textContent = Math.abs(difRgi) < 0.05 ? "empate com os concorrentes"
    : `${difRgi > 0 ? "▲" : "▼"} ${fmtNum(Math.abs(difRgi), 1)}% ${difRgi > 0 ? "acima" : "abaixo"} dos concorrentes`;
  subRgi.className = difRgi > 0 ? "sobe" : difRgi < 0 ? "desce" : "";

  const n = aval.reduce((s, l) => s + l.n, 0);
  const soma = aval.reduce((s, l) => s + l.n * l.nota, 0);
  const ruins = aval.filter(l => l.nota <= 2).reduce((s, l) => s + l.n, 0);
  document.getElementById("k-nota").textContent = n ? fmtNum(soma / n, 2) + " ★" : "–";
  document.getElementById("k-nota-sub").textContent = n
    ? `${fmtNum(n)} avaliações · ${fmtPct(ruins / n)} com 1–2★`
    : "sem avaliações";
}

// ---------- Gráfico 1: evolução mensal ----------
const METRICAS = {
  ocup: { titulo: "Ocupação mensal", campo: "ocup", cs: "cs_ocup", fmt: v => fmtPct(v), eixo: v => fmtPct(v, 0) },
  adr: { titulo: "Diária média (ADR) mensal, US$", campo: "adr", cs: "cs_adr", fmt: v => fmtUSD(v), eixo: v => "$" + fmtNum(v) },
  revpar: { titulo: "RevPAR mensal, US$", campo: "revpar", cs: "cs_revpar", fmt: v => fmtUSD(v), eixo: v => "$" + fmtNum(v) },
};

function graficoEvolucao(mensal) {
  const M = METRICAS[estado.metrica];
  const chaves = [...new Set(mensal.map(l => l.a * 100 + l.m))].sort((a, b) => a - b);
  const rotulos = chaves.map(k => `${MESES[(k % 100) - 1]}/${String(Math.floor(k / 100)).slice(2)}`);
  const mesesEvento = new Set(mensal.filter(l => l.noites_evento > 0).map(l => l.a * 100 + l.m));
  const raio = chaves.map(k => (mesesEvento.has(k) ? 5 : 0));

  function serie(linhas) {
    const porMes = agruparPor(linhas, l => l.a * 100 + l.m);
    return chaves.map(k => (porMes.has(k) ? indicadores(somar(porMes.get(k))) : null));
  }

  let datasets;
  if (estado.hotel !== "todos") {
    const s = serie(mensal);
    const h = hotelPorId[estado.hotel];
    datasets = [
      { label: h.nome, data: s.map(x => x && x[M.campo]), borderColor: corTier(h.tier), backgroundColor: corTier(h.tier), pointRadius: raio },
      { label: "Concorrentes", data: s.map(x => x && x[M.cs]), borderColor: cor("--neutro"), backgroundColor: cor("--neutro"), borderDash: [5, 4], pointRadius: 0 },
    ];
    document.getElementById("t-evolucao").textContent = `${M.titulo}: ${h.nome} × concorrentes`;
  } else {
    const porTier = agruparPor(mensal, l => hotelPorId[l.h].tier);
    datasets = TIERS.filter(t => porTier.has(t)).map(t => {
      const s = serie(porTier.get(t));
      return { label: NOME_TIER[t], data: s.map(x => x && x[M.campo]), borderColor: corTier(t), backgroundColor: corTier(t), pointRadius: raio };
    });
    document.getElementById("t-evolucao").textContent = `${M.titulo} por categoria`;
  }
  datasets.forEach(d => Object.assign(d, { borderWidth: 2, tension: 0.25, pointHoverRadius: 6 }));

  desenhar("g-evolucao", {
    type: "line",
    data: { labels: rotulos, datasets },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: { y: { ticks: { callback: M.eixo } }, x: { grid: { display: false } } },
      plugins: {
        tooltip: {
          callbacks: {
            title: itens => rotulos[itens[0].dataIndex] + (mesesEvento.has(chaves[itens[0].dataIndex]) ? " · mês com evento" : ""),
            label: c => `${c.dataset.label}: ${M.fmt(c.parsed.y)}`,
          },
        },
      },
    },
  });
}

// ---------- Por hotel (usado no RGI, no quadrante e na tabela) ----------
function resumoPorHotel(mensal, aval) {
  const porHotel = agruparPor(mensal, l => l.h);
  const avalHotel = agruparPor(aval, l => l.h);
  return [...porHotel.entries()].map(([id, linhas]) => {
    const k = indicadores(somar(linhas));
    const av = avalHotel.get(id) || [];
    const n = av.reduce((s, l) => s + l.n, 0);
    return {
      id, nome: hotelPorId[id].nome, tier: hotelPorId[id].tier, ...k,
      nota: n ? av.reduce((s, l) => s + l.n * l.nota, 0) / n : null,
      ruins: n ? av.filter(l => l.nota <= 2).reduce((s, l) => s + l.n, 0) / n : null,
    };
  });
}

// ---------- Gráfico 2: RGI por hotel ----------
const linhaReferencia = {
  id: "linhaReferencia",
  afterDraw(chart, _args, opts) {
    if (!opts || !opts.eixos) return;
    const { ctx, chartArea: a } = chart;
    ctx.save();
    ctx.strokeStyle = cor("--texto-2");
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    for (const [eixo, valor] of opts.eixos) {
      const s = chart.scales[eixo];
      const p = s.getPixelForValue(valor);
      ctx.beginPath();
      if (eixo === "x") { ctx.moveTo(p, a.top); ctx.lineTo(p, a.bottom); }
      else { ctx.moveTo(a.left, p); ctx.lineTo(a.right, p); }
      ctx.stroke();
    }
    ctx.restore();
  },
};

function graficoRgi(hoteis, id = "g-rgi") {
  const ord = [...hoteis].sort((a, b) => b.rgi - a.rgi);
  desenhar(id, {
    type: "bar",
    data: {
      labels: ord.map(h => h.nome),
      datasets: [{
        label: "RGI",
        data: ord.map(h => h.rgi),
        backgroundColor: ord.map(h => corTier(h.tier)),
        borderRadius: 4, borderSkipped: "start", barPercentage: 0.75,
      }],
    },
    options: {
      onClick: (_e, itens) => itens.length && filtrarHotel(ord[itens[0].index].id),
      onHover: cursorMao,
      indexAxis: "y",
      scales: {
        x: { min: Math.min(80, ...ord.map(h => Math.floor(h.rgi / 5) * 5)), title: { display: true, text: "RGI (100 = igual aos concorrentes)" } },
        y: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        linhaReferencia: { eixos: [["x", 100]] },
        tooltip: { callbacks: { label: c => `RGI ${fmtNum(c.parsed.x, 1)} · ${NOME_TIER[ord[c.dataIndex].tier]}` } },
      },
    },
    plugins: [linhaReferencia],
  });
}

// ---------- Gráfico 3: quadrante preço × ocupação ----------
function graficoQuadrante(hoteis, id = "g-quadrante") {
  const porTier = agruparPor(hoteis, h => h.tier);
  const datasets = TIERS.filter(t => porTier.has(t)).map(t => ({
    label: NOME_TIER[t],
    data: porTier.get(t).map(h => ({ x: h.ari, y: h.mpi, nome: h.nome, id: h.id })),
    backgroundColor: corTier(t),
    // a forma "x" não tem preenchimento: precisa de contorno colorido
    borderColor: FORMA_TIER[t] === "crossRot" ? corTier(t) : cor("--superficie"),
    borderWidth: FORMA_TIER[t] === "crossRot" ? 3 : 2,
    pointStyle: FORMA_TIER[t], pointRadius: 8, pointHoverRadius: 10,
  }));
  const xs = hoteis.map(h => h.ari), ys = hoteis.map(h => h.mpi);
  const folga = 3;
  const arred = (v, f) => f(v / 5) * 5; // limites em múltiplos de 5
  desenhar(id, {
    type: "scatter",
    data: { datasets },
    options: {
      onClick: (_e, itens, chart) => itens.length && filtrarHotel(chart.data.datasets[itens[0].datasetIndex].data[itens[0].index].id),
      onHover: cursorMao,
      layout: { padding: { right: 50 } },
      scales: {
        x: { min: arred(Math.min(95, ...xs) - folga, Math.floor), max: arred(Math.max(105, ...xs) + folga, Math.ceil), title: { display: true, text: "ARI: preço vs. concorrentes (100 = igual)" } },
        y: { min: arred(Math.min(95, ...ys) - folga, Math.floor), max: arred(Math.max(105, ...ys) + folga, Math.ceil), title: { display: true, text: "MPI: ocupação vs. concorrentes" } },
      },
      plugins: {
        linhaReferencia: { eixos: [["x", 100], ["y", 100]] },
        tooltip: {
          callbacks: {
            label: c => {
              const p = c.raw;
              const q = (p.x >= 100 ? "cobra mais" : "cobra menos") + " e " + (p.y >= 100 ? "enche mais" : "enche menos");
              return `${p.nome}: ARI ${fmtNum(p.x, 1)}, MPI ${fmtNum(p.y, 1)} (${q})`;
            },
          },
        },
      },
    },
    plugins: [linhaReferencia, rotulosPontos],
  });
}
// Rótulo com o nome curto de cada hotel ao lado do ponto
const rotulosPontos = {
  id: "rotulosPontos",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    ctx.save();
    ctx.font = "11px " + Chart.defaults.font.family;
    ctx.fillStyle = cor("--texto-2");
    chart.data.datasets.forEach((ds, i) => {
      chart.getDatasetMeta(i).data.forEach((pt, j) => {
        const nome = ds.data[j].nome.replace(/^The /, "").split(" ")[0];
        ctx.fillText(nome, pt.x + 10, pt.y + 4);
      });
    });
    ctx.restore();
  },
};

// ---------- Gráfico 4: decisões de preço ----------
function graficoDecisoes(dec, id = "g-decisoes") {
  const acoes = ["raise", "hold", "lower"];
  const tot = Object.fromEntries(acoes.map(a => [a, dec.filter(l => l.acao === a).reduce((s, l) => s + l.n, 0)]));
  const cores = { better: cor("--bom"), "in line": cor("--neutro"), worse: cor("--ruim") };
  const datasets = RESULTADOS.map(([r, nome]) => ({
    label: nome,
    data: acoes.map(a => {
      const n = dec.filter(l => l.acao === a && l.res === r).reduce((s, l) => s + l.n, 0);
      return tot[a] ? (n / tot[a]) * 100 : 0;
    }),
    contagem: acoes.map(a => dec.filter(l => l.acao === a && l.res === r).reduce((s, l) => s + l.n, 0)),
    backgroundColor: cores[r], borderColor: cor("--superficie"), borderWidth: { right: 2 }, borderSkipped: false,
  }));
  desenhar(id, {
    type: "bar",
    data: { labels: acoes.map(a => `${NOME_ACAO[a]} (${fmtNum(tot[a])})`), datasets },
    options: {
      indexAxis: "y",
      scales: {
        x: { stacked: true, max: 100, ticks: { callback: v => v + "%" } },
        y: { stacked: true, grid: { display: false } },
      },
      plugins: {
        tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtNum(c.parsed.x, 1)}% (${c.dataset.contagem[c.dataIndex]} semanas)` } },
      },
    },
  });
}

// ---------- Gráfico 5: distribuição das notas ----------
function graficoNotas(aval, id = "g-notas") {
  const n = aval.reduce((s, l) => s + l.n, 0);
  const cont = [1, 2, 3, 4, 5].map(nota => aval.filter(l => l.nota === nota).reduce((s, l) => s + l.n, 0));
  const ruimClaro = "#d98a93", bomClaro = "#d9b56a";
  desenhar(id, {
    type: "bar",
    data: {
      labels: ["1★", "2★", "3★", "4★", "5★"],
      datasets: [{
        label: "Avaliações",
        data: cont.map(c => (n ? (c / n) * 100 : 0)),
        backgroundColor: [cor("--ruim"), ruimClaro, cor("--neutro"), bomClaro, cor("--bom")],
        borderRadius: 4, borderSkipped: "start", barPercentage: 0.7, order: 2,
      }, {
        // Frequência acumulada no MESMO eixo (0–100%)
        type: "line", label: "% acumulado",
        data: cont.map((_, i) => (n ? cont.slice(0, i + 1).reduce((a, b) => a + b, 0) / n * 100 : 0)),
        borderColor: cor("--texto-2"), backgroundColor: cor("--texto-2"), borderWidth: 2, pointRadius: 3, order: 1,
      }],
    },
    options: {
      scales: { y: { max: 100, ticks: { callback: v => v + "%" } }, x: { grid: { display: false } } },
      plugins: {
        legend: { display: true, labels: { filter: i => i.datasetIndex === 1 } },
        tooltip: { callbacks: { label: c => c.datasetIndex === 1
          ? `Acumulado até ${c.label}: ${fmtNum(c.parsed.y, 1)}%`
          : `${fmtNum(c.parsed.y, 1)}% (${fmtNum(cont[c.dataIndex])} avaliações)` } },
      },
    },
  });
}

// ---------- Gráfico 6: cenários das avaliações ----------
function graficoCenarios(cen, id = "g-cenarios") {
  const porC = agruparPor(cen, l => l.c);
  const linhas = [...porC.entries()].map(([id, ls]) => {
    const n = ls.reduce((s, l) => s + l.n, 0);
    return { id, n, media: ls.reduce((s, l) => s + l.soma, 0) / n };
  }).sort((a, b) => b.n - a.n);
  // Cor pela nota média: abaixo de 3 = vermelho, acima = azul (polaridade)
  desenhar(id, {
    type: "bar",
    data: {
      labels: linhas.map(l => cenarioPorId[l.id].nome),
      datasets: [{
        label: "Avaliações",
        data: linhas.map(l => l.n),
        backgroundColor: linhas.map(l => (l.media >= 3.5 ? cor("--bom") : l.media <= 2.5 ? cor("--ruim") : cor("--neutro"))),
        borderRadius: 4, borderSkipped: "start", barPercentage: 0.75,
      }],
    },
    options: {
      indexAxis: "y",
      scales: { x: { title: { display: true, text: "Número de avaliações" } }, y: { grid: { display: false } } },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: c => `${fmtNum(linhas[c.dataIndex].n)} avaliações · nota média ${fmtNum(linhas[c.dataIndex].media, 2)}★`,
            afterLabel: c => "Ação: " + cenarioPorId[linhas[c.dataIndex].id].acao,
          },
        },
      },
    },
  });
}

// ---------- Tabela ----------
function atualizarTabela(hoteis) {
  const { col, asc } = estado.ordem;
  const ord = [...hoteis].sort((a, b) => {
    const va = a[col], vb = b[col];
    const r = typeof va === "string" ? va.localeCompare(vb) : (va ?? -1) - (vb ?? -1);
    return asc ? r : -r;
  });
  document.querySelector("#tabela tbody").innerHTML = ord.map(h => `
    <tr>
      <td>${h.nome}</td>
      <td>${NOME_TIER[h.tier]}</td>
      <td class="num">${fmtNum(h.receita)}</td>
      <td class="num">${fmtPct(h.ocup)}</td>
      <td class="num">${fmtUSD(h.adr)}</td>
      <td class="num">${fmtUSD(h.revpar)}</td>
      <td class="num ${h.rgi >= 100 ? "acima" : "abaixo"}">${fmtNum(h.rgi, 1)}</td>
      <td class="num">${h.nota == null ? "–" : fmtNum(h.nota, 2)}</td>
      <td class="num">${h.ruins == null ? "–" : fmtPct(h.ruins)}</td>
    </tr>`).join("");
  document.querySelectorAll("#tabela th").forEach(th => {
    th.classList.toggle("ordenado", th.dataset.col === col);
    th.classList.toggle("asc", th.dataset.col === col && asc);
  });
}

// =====================================================================
// Aba "Diária adequada" (MARS)
// =====================================================================
function recomendacao(h) {
  // Mesma regra de analise_hoteis.py: cruza preço (contra o MARS) com ocupação (MPI)
  const dif = h.dif_mars, mpi = h.mpi;
  if (dif >= -2 && dif <= 2) return ["ok", "Dentro da faixa do MARS: manter"];
  if (dif < -2 && mpi > 101) return ["subir", "Barato e mais cheio que os concorrentes: há espaço para subir a diária"];
  if (dif < -2) return ["subir", "Barato sem ganhar ocupação: subir rumo ao MARS e rever a qualidade"];
  if (mpi >= 98) return ["ok", "Acima do MARS sem perder ocupação: o mercado aceita, manter e vigiar o MPI"];
  return ["baixar", "Acima do MARS e perdendo ocupação: reduzir rumo ao MARS"];
}

function resumoMarsPorHotel(mensal) {
  const porHotel = agruparPor(mensal, l => l.h);
  return [...porHotel.entries()].map(([id, linhas]) => {
    const t = somar(linhas);
    const k = indicadores(t);
    const h = { id, nome: hotelPorId[id].nome, tier: hotelPorId[id].tier, ...k, noites: t.noites, abaixo: t.abaixo, acima: t.acima };
    h.rec = recomendacao(h);
    return h;
  }).sort((a, b) => a.dif_mars - b.dif_mars);
}

const faixaMars = {
  id: "faixaMars",
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea: a, scales: { x } } = chart;
    ctx.save();
    ctx.fillStyle = "rgba(127,127,127,0.12)";
    const x1 = x.getPixelForValue(-2), x2 = x.getPixelForValue(2);
    ctx.fillRect(x1, a.top, x2 - x1, a.bottom - a.top);
    ctx.restore();
  },
};

function atualizarMars(mensal) {
  const hs = resumoMarsPorHotel(mensal);
  const n = c => hs.filter(h => c(h.dif_mars)).length;
  document.getElementById("m-abaixo").textContent = n(d => d < -2);
  document.getElementById("m-dentro").textContent = n(d => d >= -2 && d <= 2);
  document.getElementById("m-acima").textContent = n(d => d > 2);
  const t = somar(mensal);
  document.getElementById("m-fora").textContent = fmtPct((t.abaixo + t.acima) / t.noites);
  document.getElementById("m-fora-sub").textContent = `${fmtNum(t.abaixo + t.acima)} de ${fmtNum(t.noites)} noites`;

  desenhar("g-mars", {
    type: "bar",
    data: {
      labels: hs.map(h => h.nome),
      datasets: [{
        label: "Diferença para o MARS (%)",
        data: hs.map(h => h.dif_mars),
        backgroundColor: hs.map(h => (h.dif_mars < -2 ? cor("--ruim") : h.dif_mars > 2 ? cor("--bom") : cor("--neutro"))),
        borderRadius: 4, borderSkipped: false, barPercentage: 0.75,
      }],
    },
    options: {
      indexAxis: "y",
      onClick: (_e, itens) => itens.length && filtrarHotel(hs[itens[0].index].id),
      onHover: cursorMao,
      scales: {
        x: { title: { display: true, text: "ADR cobrado em relação ao MARS (%)" }, ticks: { callback: v => (v > 0 ? "+" : "") + v + "%" } },
        y: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: itens => hs[itens[0].dataIndex].nome + " (clique para filtrar)",
            label: c => {
              const h = hs[c.dataIndex];
              return [`ADR cobrado: ${fmtUSD(h.adr)} · MARS: ${fmtUSD(h.mars)}`,
                      `Diferença: ${h.dif_mars > 0 ? "+" : ""}${fmtNum(h.dif_mars, 1)}% · MPI ${fmtNum(h.mpi, 1)}`,
                      h.rec[1]];
            },
          },
        },
      },
    },
    plugins: [faixaMars],
  });

  document.getElementById("t-mars").innerHTML = hs.map(h => `
    <tr>
      <td>${h.nome}</td><td>${NOME_TIER[h.tier]}</td>
      <td class="num">${fmtUSD(h.adr)}</td><td class="num"><strong>${fmtUSD(h.mars)}</strong></td>
      <td class="num ${h.dif_mars < -2 ? "abaixo" : h.dif_mars > 2 ? "acima" : ""}">${h.dif_mars > 0 ? "+" : ""}${fmtNum(h.dif_mars, 1)}%</td>
      <td class="num">${fmtNum(h.mpi, 1)}</td>
      <td class="num">${fmtPct(h.abaixo / h.noites, 0)} / ${fmtPct(h.acima / h.noites, 0)}</td>
      <td class="quebra"><span class="selo ${h.rec[0]}">${h.rec[0] === "subir" ? "▲ subir" : h.rec[0] === "baixar" ? "▼ baixar" : "● manter"}</span> ${h.rec[1]}</td>
    </tr>`).join("");

  // Tabela por estação: MARS médio das noites (mars_soma / noites)
  const ESTACAO = { 12: "inverno", 1: "inverno", 2: "inverno", 3: "primavera", 4: "primavera", 5: "primavera",
                    6: "verao", 7: "verao", 8: "verao", 9: "outono", 10: "outono", 11: "outono" };
  const porHotel = agruparPor(mensal, l => l.h);
  const linhas = [...porHotel.entries()].map(([id, ls]) => {
    const e = {};
    for (const est of ["inverno", "primavera", "verao", "outono"]) {
      const sel = ls.filter(l => ESTACAO[l.m] === est);
      const noites = sel.reduce((s, l) => s + l.noites, 0);
      e[est] = noites ? sel.reduce((s, l) => s + l.mars_soma, 0) / noites : null;
    }
    return { nome: hotelPorId[id].nome, ...e };
  }).sort((a, b) => a.nome.localeCompare(b.nome));
  document.getElementById("t-estacao").innerHTML = linhas.map(l => `
    <tr><td>${l.nome}</td>${["inverno", "primavera", "verao", "outono"].map(e => `<td class="num">${l[e] == null ? "–" : fmtUSD(l[e])}</td>`).join("")}</tr>`).join("");
}

function montarExemploMars() {
  const e = D.exemplo_mars;
  if (!e) return;
  const pos = (e.adr / e.mars - 1) * 100;
  document.getElementById("exemplo-mars").innerHTML = `
    <h3>Como a diária adequada é calculada: exemplo passo a passo</h3>
    <p class="nota-grafico">${e.hotel}, noite de ${e.data.split("-").reverse().join("/")}, grupo de concorrentes <strong>${e.grupo}</strong>.</p>
    <div class="formula">MARS = mediana(ADR dos concorrentes na noite) × posicionamento do hotel ÷ mediana(posicionamento dos concorrentes)</div>
    <div class="tabela-rolagem"><table>
      <thead><tr><th>Concorrente</th><th class="num">ADR na noite</th><th class="num">Posicionamento</th></tr></thead>
      <tbody>${e.concorrentes.map(c => `<tr><td>${c.nome}</td><td class="num">US$ ${fmtNum(c.adr, 2)}</td><td class="num">${fmtNum(c.pos, 2)}</td></tr>`).join("")}</tbody>
    </table></div>
    <ol class="passos">
      <li>Mediana do ADR dos concorrentes = <strong>US$ ${fmtNum(e.med_adr, 2)}</strong></li>
      <li>Posicionamento do hotel = ${fmtNum(e.pos_hotel, 2)} · mediana dos concorrentes = ${fmtNum(e.med_pos, 2)}</li>
      <li>MARS = ${fmtNum(e.med_adr, 2)} × ${fmtNum(e.pos_hotel, 2)} ÷ ${fmtNum(e.med_pos, 2)} = <strong>US$ ${fmtNum(e.mars, 2)}</strong> (no dataset: US$ ${fmtNum(e.mars_dataset, 2)} ✔)</li>
      <li>Faixa aceitável (±6%): US$ ${fmtNum(e.mars * 0.94, 2)} a US$ ${fmtNum(e.mars * 1.06, 2)}</li>
      <li>O hotel cobrou US$ ${fmtNum(e.adr, 2)}, ou seja, <strong>${pos > 0 ? "+" : ""}${fmtNum(pos, 1)}%</strong> em relação ao MARS${Math.abs(pos) > 6 ? ", fora da faixa" : ""}.</li>
    </ol>`;
}

// =====================================================================
// Aba "Dados e relações"
// =====================================================================
function montarRelacoes() {
  document.getElementById("t-tabelas").innerHTML = (D.tabelas || []).map(t => `
    <tr><td><code>${t.nome}</code></td><td class="num">${fmtNum(t.linhas)}</td><td class="num">${t.colunas}</td><td>${t.grao}</td><td class="quebra">${t.ausentes}</td></tr>`).join("");
  document.getElementById("t-relacoes").innerHTML = (D.relacoes || []).map(r => `
    <tr><td><code>${r.pai}</code></td><td><code>${r.filha}</code></td><td><code>${r.chave}</code></td><td>${r.card}</td>
        <td class="num">${fmtNum(r.max)}</td><td class="num ${r.orfaos ? "abaixo" : "acima"}">${r.orfaos}</td></tr>`).join("");
}

// =====================================================================
// Aba "Gráficos e análises": versões interativas dos gráficos do Python
// =====================================================================
const I = D.interativo || {};

function passaFiltroPonto(p) {
  return passaFiltro({ h: p.h, a: p.a });
}

function heatmapCorrelacao(cont) {
  const { vars = [], m = [] } = I.corr || {};
  const corCelula = r => {
    // divergente: vermelho (−1) · cinza claro (0) · azul (+1)
    const a = Math.min(Math.abs(r), 1);
    const base = r >= 0 ? [0, 140, 128] : [155, 45, 58];
    return `rgba(${base.join(",")},${(0.08 + a * 0.85).toFixed(2)})`;
  };
  cont.innerHTML = `<div class="tabela-rolagem"><table class="heatmap">
    <thead><tr><th></th>${vars.map(v => `<th><span>${v}</span></th>`).join("")}</tr></thead>
    <tbody>${m.map((linha, i) => `<tr><th>${vars[i]}</th>${linha.map((r, j) =>
      `<td data-i="${i}" data-j="${j}" style="background:${corCelula(r)};color:${Math.abs(r) > 0.6 ? "#fff" : "inherit"}"
           title="${vars[i]} × ${vars[j]}: r = ${fmtNum(r, 2)}">${fmtNum(r, 2)}</td>`).join("")}</tr>`).join("")}</tbody>
  </table></div><p class="nota-grafico" data-info>Passe o mouse (ou toque) numa célula para ver o par de variáveis.</p>`;
  const info = cont.querySelector("[data-info]");
  cont.querySelectorAll("td[data-i]").forEach(td => {
    const destacar = () => {
      cont.querySelectorAll(".marcada").forEach(x => x.classList.remove("marcada"));
      const i = +td.dataset.i, j = +td.dataset.j;
      cont.querySelectorAll(`td[data-i="${i}"], td[data-j="${j}"]`).forEach(x => x.classList.add("marcada"));
      const r = m[i][j];
      const forca = Math.abs(r) >= 0.7 ? "forte" : Math.abs(r) >= 0.3 ? "moderada" : "fraca";
      info.textContent = `${vars[i]} × ${vars[j]}: r = ${fmtNum(r, 2)} (relação ${forca}${r < 0 ? " e negativa" : r > 0 ? " e positiva" : ""}).`;
    };
    td.addEventListener("mouseenter", destacar);
    td.addEventListener("click", destacar);
  });
}

function dispersaoPorTier(id, pontos, x, y, rotX, rotY, fmtX, fmtY, linhaY) {
  const porTier = agruparPor(pontos, p => hotelPorId[p.h].tier);
  desenhar(id, {
    type: "scatter",
    data: {
      datasets: TIERS.filter(t => porTier.has(t)).map(t => ({
        label: NOME_TIER[t],
        data: porTier.get(t).map(p => ({ x: x(p), y: y(p), h: p.h })),
        backgroundColor: corTier(t) + "99", borderColor: corTier(t), pointRadius: 3, pointHoverRadius: 6,
        pointStyle: FORMA_TIER[t],
      })),
    },
    options: {
      scales: { x: { title: { display: true, text: rotX }, ticks: { callback: fmtX } },
                y: { title: { display: true, text: rotY }, ticks: { callback: fmtY } } },
      plugins: {
        linhaReferencia: linhaY ? { eixos: [["y", linhaY]] } : undefined,
        tooltip: { callbacks: { label: c => `${hotelPorId[c.raw.h].nome}: ${fmtX(c.raw.x)} · ${fmtY(c.raw.y)}` } },
      },
    },
    plugins: linhaY ? [linhaReferencia] : [],
  });
}

function correlacao(xs, ys) {
  const n = xs.length;
  if (n < 3) return NaN;
  const mx = xs.reduce((a, b) => a + b, 0) / n, my = ys.reduce((a, b) => a + b, 0) / n;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) ** 2; syy += (ys[i] - my) ** 2; }
  return sxy / Math.sqrt(sxx * syy);
}

function graficoHalteres(id, hs) {
  const ord = [...hs].sort((a, b) => b.dif_mars - a.dif_mars);
  desenhar(id, {
    type: "bar",
    data: {
      labels: ord.map(h => h.nome),
      datasets: [
        { type: "bar", label: "Distância ADR ↔ MARS", data: ord.map(h => [Math.min(h.adr, h.mars), Math.max(h.adr, h.mars)]),
          backgroundColor: cor("--neutro"), barPercentage: 0.2, borderRadius: 3, order: 3 },
        { type: "line", label: "MARS (adequado)", data: ord.map(h => h.mars), indexAxis: "y", showLine: false,
          pointRadius: 7, pointHoverRadius: 9, pointBackgroundColor: cor("--superficie"), pointBorderColor: cor("--texto"), pointBorderWidth: 2, order: 2 },
        { type: "line", label: "ADR cobrado", data: ord.map(h => h.adr), indexAxis: "y", showLine: false,
          pointRadius: 7, pointHoverRadius: 9, pointBackgroundColor: ord.map(h => corTier(h.tier)), pointBorderColor: cor("--superficie"), pointBorderWidth: 2, order: 1 },
      ],
    },
    options: {
      indexAxis: "y",
      onClick: (_e, itens) => itens.length && filtrarHotel(ord[itens[0].index].id),
      onHover: cursorMao,
      interaction: { mode: "index", axis: "y", intersect: false },
      scales: { x: { title: { display: true, text: "US$ por quarto vendido" } }, y: { grid: { display: false }, ticks: { autoSkip: false } } },
      plugins: {
        tooltip: {
          filter: c => c.datasetIndex > 0,
          callbacks: {
            label: c => `${c.dataset.label}: ${fmtUSD(c.parsed.x)}`,
            footer: itens => { const h = ord[itens[0].dataIndex]; return `Diferença: ${h.dif_mars > 0 ? "+" : ""}${fmtNum(h.dif_mars, 1)}%`; },
          },
        },
      },
    },
  });
}

function graficoDesvio(id, hotelIds) {
  const ano = estado.ano === "todos" ? 0 : +estado.ano;
  const linhas = (I.desvio || []).filter(d => d.a === ano && hotelIds.has(d.h))
    .sort((a, b) => b.q[2] - a.q[2]);
  const nomes = linhas.map(d => hotelPorId[d.h].nome);
  desenhar(id, {
    type: "bar",
    data: {
      labels: nomes,
      datasets: [
        { label: "5% a 95% das noites", data: linhas.map(d => [d.q[0], d.q[4]]), backgroundColor: cor("--texto-2"), barPercentage: 0.08, categoryPercentage: 1, grouped: false },
        { label: "Metade central (25% a 75%)", data: linhas.map(d => [d.q[1], d.q[3]]),
          backgroundColor: linhas.map(d => corTier(hotelPorId[d.h].tier)), barPercentage: 0.6, categoryPercentage: 1, grouped: false, borderRadius: 3 },
        { type: "line", label: "Mediana", data: linhas.map(d => d.q[2]), indexAxis: "y", showLine: false,
          pointStyle: "line", pointRadius: 9, pointBorderWidth: 3, pointBorderColor: cor("--texto"), rotation: 90 },
      ],
    },
    options: {
      indexAxis: "y",
      onClick: (_e, itens) => itens.length && filtrarHotel(linhas[itens[0].index].h),
      onHover: cursorMao,
      interaction: { mode: "index", axis: "y", intersect: false },
      scales: { x: { title: { display: true, text: "Diferença entre a diária da noite e o MARS (%)" } }, y: { grid: { display: false }, ticks: { autoSkip: false } } },
      plugins: {
        faixa6: true,
        tooltip: {
          callbacks: {
            label: () => "",
            footer: itens => {
              const q = linhas[itens[0].dataIndex].q;
              return [`Mediana: ${fmtNum(q[2], 1)}%`, `Metade das noites: ${fmtNum(q[1], 1)}% a ${fmtNum(q[3], 1)}%`, `90% das noites: ${fmtNum(q[0], 1)}% a ${fmtNum(q[4], 1)}%`];
            },
          },
        },
      },
    },
    plugins: [{
      id: "faixa6",
      beforeDatasetsDraw(chart) {
        const { ctx, chartArea: a, scales: { x } } = chart;
        ctx.save();
        ctx.fillStyle = "rgba(184,137,58,0.12)";
        const x1 = x.getPixelForValue(-6), x2 = x.getPixelForValue(6);
        ctx.fillRect(x1, a.top, x2 - x1, a.bottom - a.top);
        ctx.restore();
      },
    }],
  });
}

function graficoSazonal(id, mensal) {
  const porTier = agruparPor(mensal, l => hotelPorId[l.h].tier);
  const metr = estado.sazMetrica;
  desenhar(id, {
    type: "line",
    data: {
      labels: MESES,
      datasets: TIERS.filter(t => porTier.has(t)).map(t => {
        const porMes = agruparPor(porTier.get(t), l => l.m);
        return {
          label: NOME_TIER[t],
          data: Array.from({ length: 12 }, (_, i) => {
            const k = porMes.has(i + 1) ? indicadores(somar(porMes.get(i + 1))) : null;
            return k ? (metr === "ocup" ? k.ocup : k.adr) : null;
          }),
          borderColor: corTier(t), backgroundColor: corTier(t), borderWidth: 2, tension: 0.25, pointRadius: 3,
        };
      }),
    },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: { y: { ticks: { callback: v => (metr === "ocup" ? fmtPct(v, 0) : "$" + fmtNum(v)) } } },
      plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${metr === "ocup" ? fmtPct(c.parsed.y) : fmtUSD(c.parsed.y)}` } } },
    },
  });
}

function graficoProjecao(id, cont) {
  const hotel = estado.hotel !== "todos" ? estado.hotel : "H03";
  const linhas = D.mensal.filter(l => l.h === hotel);
  const ano = a => linhas.filter(l => l.a === a).sort((x, y) => x.m - y.m);
  const l27 = ano(2027), l28 = ano(2028);
  const porDia = ls => ls.reduce((s, l) => s + l.rec_t, 0) / ls.reduce((s, l) => s + l.noites, 0);
  const cresc = porDia(l28) / porDia(l27) - 1;
  const dias2029 = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const p29 = l28.map((l, i) => (l.rec_t / l.noites) * (1 + cresc) * dias2029[i]);
  const total29 = p29.reduce((a, b) => a + b, 0);
  const rotulos = [2027, 2028, 2029].flatMap(a => MESES.map(m => `${m}/${String(a).slice(2)}`));
  const vazio = Array(12).fill(null);
  desenhar(id, {
    type: "line",
    data: {
      labels: rotulos,
      datasets: [
        { label: "2027 (real)", data: [...l27.map(l => l.rec_t), ...vazio, ...vazio], borderColor: cor("--bom"), backgroundColor: cor("--bom"), pointRadius: 2 },
        { label: "2028 (real)", data: [...vazio, ...l28.map(l => l.rec_t), ...vazio], borderColor: cor("--serie-3"), backgroundColor: cor("--serie-3"), pointRadius: 2 },
        { label: "2029 (projeção)", data: [...vazio, ...vazio, ...p29], borderColor: cor("--serie-2"), backgroundColor: cor("--serie-2"), borderDash: [6, 4], pointRadius: 2 },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      scales: { y: { ticks: { callback: v => "$" + fmtNum(v / 1e6, 1) + " mi" } }, x: { ticks: { maxTicksLimit: 12 } } },
      plugins: { tooltip: { callbacks: { label: c => c.parsed.y == null ? "" : `${c.dataset.label}: ${fmtMilhoes(c.parsed.y)}` } } },
    },
  });
  cont.textContent = `${hotelPorId[hotel].nome}: projeção 2029 de ${fmtMilhoes(total29)} (crescimento por dia de ${cresc > 0 ? "+" : ""}${fmtNum(cresc * 100, 2)}% ao ano). Escolha outro hotel no filtro para projetar outro.`;
}

// Cada arquivo do relatório Python ganha uma versão interativa (ou fica como imagem)
const INTERATIVOS = {
  "G02_matriz_correlacao.png": { html: true, desenhar: cont => heatmapCorrelacao(cont) },
  "G03_ocupacao_x_adr.png": { dica: "Arraste um retângulo para dar zoom · duplo clique volta · clique na legenda para esconder uma categoria",
    desenhar: (id, f, cont) => {
      const pts = (I.amostra || []).filter(passaFiltroPonto);
      dispersaoPorTier(id, pts, p => p.o, p => p.p, "Ocupação na noite", "Diária (ADR), US$", v => fmtPct(v, 0), v => "$" + fmtNum(v));
      const r = correlacao(pts.map(p => p.o), pts.map(p => p.p));
      cont.textContent = `${fmtNum(pts.length)} noites (amostra de 2.000) · r = ${isNaN(r) ? "–" : fmtNum(r, 2)} com os filtros atuais.`;
    },
  },
  "G04_nota_x_rgi.png": { dica: "Arraste um retângulo para dar zoom · duplo clique volta · clique na legenda para esconder uma categoria",
    desenhar: (id, f, cont) => {
      const pts = (I.semanal || []).filter(passaFiltroPonto);
      dispersaoPorTier(id, pts, p => p.n, p => p.g, "Nota média da semana (1 a 5)", "RGI da semana", v => fmtNum(v, 1), v => fmtNum(v), 100);
      const r = correlacao(pts.map(p => p.n), pts.map(p => p.g));
      cont.textContent = `${fmtNum(pts.length)} semanas · r = ${isNaN(r) ? "–" : fmtNum(r, 2)} com os filtros atuais.`;
    },
  },
  "G05_notas_parciais.png": {
    desenhar: id => {
      const ps = [...(I.parciais || [])].sort((a, b) => b.r - a.r);
      desenhar(id, {
        type: "bar",
        data: { labels: ps.map(p => p.nome), datasets: [{ label: "Correlação com a nota geral", data: ps.map(p => p.r), backgroundColor: cor("--bom"), borderRadius: 4, barPercentage: 0.6 }] },
        options: { indexAxis: "y", scales: { x: { min: 0, max: 1 }, y: { grid: { display: false } } },
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `r = ${fmtNum(c.parsed.x, 2)}` } } } },
      });
    },
  },
  "G07_adr_x_mars.png": { alto: true, dica: "Passe o mouse para ver ADR, MARS e a diferença · clique num hotel para filtrar o painel", desenhar: (id, f) => graficoHalteres(id, resumoMarsPorHotel(f.mensal)) },
  "G08_desvio_mars_por_hotel.png": { alto: true, dica: "Passe o mouse para ver mediana e faixas · clique num hotel para filtrar · o filtro de ano muda as caixas", desenhar: (id, f) => graficoDesvio(id, new Set(f.mensal.map(l => l.h))) },
  "G09_quadrante_ari_mpi.png": { dica: "Arraste para dar zoom · duplo clique volta · clique num hotel para filtrar o painel", desenhar: (id, f) => graficoQuadrante(resumoPorHotel(f.mensal, f.aval), id) },
  "G10_sazonalidade.png": { seletor: true, desenhar: (id, f) => graficoSazonal(id, f.mensal) },
  "G11_decisoes_preco.png": { desenhar: (id, f) => graficoDecisoes(f.dec, id) },
  "G12_distribuicao_notas.png": { desenhar: (id, f) => graficoNotas(f.aval, id) },
  "G13_cenarios.png": { desenhar: (id, f) => graficoCenarios(f.cen, id) },
  "G14_projecao_2029.png": { dica: "Escolha um hotel no filtro para projetar outro · arraste para dar zoom", desenhar: (id, f, cont) => graficoProjecao(id, cont) },
};

function montarGaleria() {
  const grupos = ["Todos", ...new Set(ANALISES.map(a => a.grupo))];
  document.getElementById("grupos").innerHTML = grupos.map(g =>
    `<button type="button" class="chip ${g === estado.grupo ? "ativo" : ""}" data-grupo="${g}">${g}</button>`).join("");
  document.querySelectorAll("#grupos .chip").forEach(b => b.addEventListener("click", () => {
    estado.grupo = b.dataset.grupo;
    document.querySelectorAll("#grupos .chip").forEach(x => x.classList.toggle("ativo", x === b));
    aplicarPesquisa();
  }));
  document.getElementById("galeria").innerHTML = ANALISES.map((a, i) => {
    const it = INTERATIVOS[a.arquivo];
    const visual = !it
      ? `<img src="img/${a.arquivo}" alt="${a.titulo}" loading="lazy">`
      : it.html ? `<div class="heatmap-cont" id="gi-${i}"></div>`
      : `${it.seletor ? `<div class="segmentado pequeno" role="group" aria-label="Métrica"><button type="button" data-saz="ocup" class="ativo">Ocupação</button><button type="button" data-saz="adr">ADR</button></div>` : ""}
         <div class="area-grafico ${it.alto ? "muito-alto" : "alto"}"><canvas id="gi-${i}"></canvas></div>`;
    return `
    <article class="cartao analise buscavel-item" data-grupo="${a.grupo}">
      <h3>${a.titulo}</h3>
      <p class="pergunta">${a.pergunta}</p>
      ${visual}
      <p class="nota-grafico" id="gi-${i}-info"></p>
      ${it && !it.html ? `<p class="dica">${it.dica || "Passe o mouse para ver os valores · clique na legenda para ligar/desligar séries"}</p>` : ""}
      <dl>
        <dt>Por que este gráfico</dt><dd>${a.tipo}</dd>
        <dt>O que mostra</dt><dd>${a.mostra}</dd>
        <dt>O que fazer</dt><dd>${a.fazer}</dd>
      </dl>
      <a class="link-png" href="img/${a.arquivo}" target="_blank" rel="noopener">Ver a versão em imagem do relatório</a>
    </article>`;
  }).join("");
  document.querySelectorAll("[data-saz]").forEach(b => b.addEventListener("click", () => {
    estado.sazMetrica = b.dataset.saz;
    document.querySelectorAll("[data-saz]").forEach(x => x.classList.toggle("ativo", x === b));
    atualizarGaleria(dadosFiltrados());
  }));
}

function atualizarGaleria(f) {
  ANALISES.forEach((a, i) => {
    const it = INTERATIVOS[a.arquivo];
    if (!it) return;
    const info = document.getElementById(`gi-${i}-info`);
    if (it.html) it.desenhar(document.getElementById(`gi-${i}`));
    else it.desenhar(`gi-${i}`, f, info);
  });
}

// =====================================================================
// Pesquisa: esconde linhas e cartões que não contêm o texto digitado
// =====================================================================
function normalizar(t) {
  return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
function aplicarPesquisa() {
  const termo = normalizar(estado.busca.trim());
  const aba = document.querySelector(`.aba[data-aba="${estado.aba}"]`);
  if (!aba) return;
  aba.querySelectorAll("tbody.buscavel").forEach(tb => {
    let visiveis = 0;
    tb.querySelectorAll("tr").forEach(tr => {
      const ok = !termo || normalizar(tr.textContent).includes(termo);
      tr.hidden = !ok;
      if (ok) visiveis++;
    });
    const aviso = tb.closest("section")?.querySelector(".sem-resultado");
    if (aviso) aviso.hidden = visiveis > 0;
  });
  const itens = aba.querySelectorAll(".buscavel-item");
  let visiveis = 0;
  itens.forEach(el => {
    const grupoOk = !el.dataset.grupo || estado.grupo === "Todos" || el.dataset.grupo === estado.grupo;
    const ok = grupoOk && (!termo || normalizar(el.textContent).includes(termo));
    el.hidden = !ok;
    if (ok) visiveis++;
  });
  const avisoItens = aba.querySelector(":scope > .sem-resultado");
  if (avisoItens) avisoItens.hidden = !itens.length || visiveis > 0;
}

// =====================================================================
// Abas
// =====================================================================
function mostrarAba(nome) {
  estado.aba = nome;
  document.querySelectorAll(".abas button").forEach(b => {
    b.classList.toggle("ativa", b.dataset.aba === nome);
    b.setAttribute("aria-selected", b.dataset.aba === nome);
  });
  document.querySelectorAll(".aba").forEach(a => (a.hidden = a.dataset.aba !== nome));
  if (location.hash !== "#" + nome) history.replaceState(null, "", "#" + nome);
  atualizar();
}

// =====================================================================
// Atualização geral: filtros valem para todas as abas
// =====================================================================
function dadosFiltrados() {
  return {
    mensal: D.mensal.filter(passaFiltro),
    aval: D.avaliacoes.filter(passaFiltro),
    cen: D.cenarios.filter(passaFiltro),
    dec: D.decisoes.filter(passaFiltro),
  };
}

function atualizar() {
  document.querySelectorAll(".filtros select").forEach(sel => sel.sincronizar?.());
  const f = dadosFiltrados();
  const semDados = f.mensal.length === 0 && ["geral", "mars", "graficos"].includes(estado.aba);
  const nHoteis = new Set(f.mensal.map(l => l.h)).size;
  const periodo = estado.ano === "todos" ? "2027 e 2028" : estado.ano;
  document.getElementById("contexto").textContent = nHoteis
    ? `Mostrando ${nHoteis} ${nHoteis === 1 ? "hotel" : "hotéis"} em ${periodo}`
    : "Nenhum hotel com esses filtros";
  document.getElementById("vazio").hidden = !semDados;
  document.getElementById("conteudo").hidden = semDados;
  if (semDados) return;

  if (estado.aba === "geral") {
    const hoteis = resumoPorHotel(f.mensal, f.aval);
    atualizarKpis(f.mensal, f.aval);
    graficoEvolucao(f.mensal);
    graficoRgi(hoteis);
    graficoQuadrante(hoteis);
    graficoDecisoes(f.dec);
    graficoNotas(f.aval);
    graficoCenarios(f.cen);
    atualizarTabela(hoteis);
  } else if (estado.aba === "mars") {
    atualizarMars(f.mensal);
  } else if (estado.aba === "graficos") {
    atualizarGaleria(f);
  }
  aplicarPesquisa();
}

// ---------- Inicialização ----------
// ---------- Listas dos filtros no estilo iPhone ----------
// A lista nativa do <select> não aceita cantos arredondados, então cada filtro
// ganha um botão e uma lista desenhados por nós. O <select> original continua
// na página (escondido) e é ele que guarda o valor: o resto do código não muda.
function criarSelectsArredondados() {
  const abertos = new Set();
  document.querySelectorAll(".filtros select").forEach(sel => {
    sel.classList.add("select-escondido");
    sel.tabIndex = -1;
    sel.setAttribute("aria-hidden", "true");
    const caixa = document.createElement("div");
    caixa.className = "seletor";
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "seletor-botao";
    botao.setAttribute("aria-haspopup", "listbox");
    botao.setAttribute("aria-expanded", "false");
    const rotulo = sel.closest("label")?.firstChild?.textContent.trim() || "";
    const lista = document.createElement("div");
    lista.className = "seletor-lista";
    lista.setAttribute("role", "listbox");
    lista.setAttribute("aria-label", rotulo);
    lista.hidden = true;
    caixa.append(botao, lista);
    sel.after(caixa);

    const item = op => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "seletor-item";
      b.setAttribute("role", "option");
      b.dataset.valor = op.value;
      b.textContent = op.text;
      b.addEventListener("click", () => {
        sel.value = op.value;
        sel.dispatchEvent(new Event("change", { bubbles: true }));
        abrir(false);
        botao.focus();
      });
      return b;
    };
    for (const filho of sel.children) {
      if (filho.tagName === "OPTGROUP") {
        const titulo = document.createElement("div");
        titulo.className = "seletor-grupo";
        titulo.textContent = filho.label;
        lista.appendChild(titulo);
        for (const op of filho.children) lista.appendChild(item(op));
      } else lista.appendChild(item(filho));
    }
    const itens = () => [...lista.querySelectorAll(".seletor-item")];

    function abrir(sim) {
      if (sim) abertos.forEach(f => f(false));
      lista.hidden = !sim;
      caixa.classList.toggle("aberto", sim);
      botao.setAttribute("aria-expanded", sim);
      if (sim) {
        abertos.add(abrir);
        const atual = itens().find(b => b.dataset.valor === sel.value) || itens()[0];
        atual.focus();
        atual.scrollIntoView({ block: "nearest" });
      } else abertos.delete(abrir);
    }
    botao.addEventListener("click", () => abrir(lista.hidden));
    botao.addEventListener("keydown", e => {
      if (["ArrowDown", "ArrowUp"].includes(e.key)) { e.preventDefault(); abrir(true); }
    });
    lista.addEventListener("keydown", e => {
      const todos = itens(), i = todos.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); todos[Math.min(i + 1, todos.length - 1)].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); todos[Math.max(i - 1, 0)].focus(); }
      if (e.key === "Escape") { abrir(false); botao.focus(); }
      if (e.key === "Tab") abrir(false);
    });
    document.addEventListener("click", e => { if (!caixa.contains(e.target)) abrir(false); });

    // Chamado depois de cada atualização (o valor pode mudar por "Limpar filtros"
    // ou por um clique num gráfico)
    sel.sincronizar = () => {
      botao.textContent = sel.selectedOptions[0]?.text || "";
      itens().forEach(b => b.setAttribute("aria-selected", b.dataset.valor === sel.value));
    };
    sel.sincronizar();
  });
}

function preencherFiltros() {
  const fTier = document.getElementById("f-tier");
  TIERS.forEach(t => fTier.add(new Option(NOME_TIER[t], t)));
  const fHotel = document.getElementById("f-hotel");
  TIERS.forEach(t => {
    const grupo = document.createElement("optgroup");
    grupo.label = NOME_TIER[t];
    D.hoteis.filter(h => h.tier === t).forEach(h => grupo.appendChild(new Option(h.nome, h.id)));
    fHotel.appendChild(grupo);
  });
}

function ligarEventos() {
  for (const [id, chave] of [["f-ano", "ano"], ["f-tier", "tier"], ["f-hotel", "hotel"]]) {
    document.getElementById(id).addEventListener("change", e => { estado[chave] = e.target.value; atualizar(); });
  }
  let espera;
  document.getElementById("f-busca").addEventListener("input", e => {
    clearTimeout(espera);
    espera = setTimeout(() => { estado.busca = e.target.value; aplicarPesquisa(); }, 150);
  });
  document.getElementById("limpar").addEventListener("click", () => {
    Object.assign(estado, { ano: "todos", tier: "todos", hotel: "todos", busca: "" });
    ["f-ano", "f-tier", "f-hotel"].forEach(id => (document.getElementById(id).value = "todos"));
    document.getElementById("f-busca").value = "";
    atualizar();
  });
  document.querySelectorAll(".abas button").forEach(b => b.addEventListener("click", () => mostrarAba(b.dataset.aba)));
  document.querySelectorAll(".segmentado button[data-metrica]").forEach(b => b.addEventListener("click", () => {
    estado.metrica = b.dataset.metrica;
    document.querySelectorAll(".segmentado button[data-metrica]").forEach(x => x.classList.toggle("ativo", x === b));
    graficoEvolucao(D.mensal.filter(passaFiltro));
  }));
  document.querySelectorAll("#tabela th").forEach(th => th.addEventListener("click", () => {
    const col = th.dataset.col;
    estado.ordem = { col, asc: estado.ordem.col === col ? !estado.ordem.asc : col === "nome" || col === "tier" };
    atualizar();
  }));
  document.getElementById("tema").addEventListener("click", () => {
    const raiz = document.documentElement;
    raiz.dataset.theme = raiz.dataset.theme === "dark" ? "light" : "dark";
    configurarChartJs();
    atualizar();
  });
}

// ---------- Barra lateral (menu sanduíche) ----------
// No computador ela abre sozinha ao passar o mouse (CSS). O botão sanduíche
// fixa o menu aberto; no celular ele abre e fecha a gaveta com um toque.
function ligarMenu() {
  const lateral = document.getElementById("lateral");
  const veu = document.getElementById("veu");
  const botoes = [document.getElementById("sanduiche"), document.querySelector(".sanduiche-movel")];
  const celular = window.matchMedia("(max-width: 760px)");
  function abrir(sim) {
    lateral.classList.toggle("aberta", sim);
    veu.hidden = !(sim && celular.matches);
    botoes.forEach(b => {
      b.setAttribute("aria-expanded", sim);
      b.setAttribute("aria-label", sim ? "Fechar menu" : "Abrir menu");
    });
  }
  botoes.forEach(b => b.addEventListener("click", () => abrir(!lateral.classList.contains("aberta"))));
  veu.addEventListener("click", () => abrir(false));
  document.addEventListener("keydown", e => { if (e.key === "Escape") abrir(false); });
  // Clique com o mouse tira o foco do botão, para a barra recolher quando o mouse sair.
  document.querySelectorAll(".abas button, #tema").forEach(b => b.addEventListener("click", e => {
    if (celular.matches) abrir(false);
    else if (e.detail > 0) b.blur();
  }));
}

function iniciar() {
  if (!window.Chart || !window.DADOS) {
    document.getElementById("vazio").hidden = false;
    document.getElementById("vazio").textContent = !window.DADOS
      ? "Arquivo dados.js não encontrado. Rode scripts/gerar_dados_dashboard.py."
      : "Não foi possível carregar a biblioteca de gráficos (Chart.js). Confira se a pasta lib/ está junto do index.html.";
    return;
  }
  if (window.ChartZoom) Chart.register(window.ChartZoom);
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.dataset.theme = "dark";
  configurarChartJs();
  preencherFiltros();
  criarSelectsArredondados();
  montarExemploMars();
  montarRelacoes();
  montarGaleria();
  ligarEventos();
  ligarMenu();
  document.getElementById("gerado").textContent = `Dados resumidos gerados em ${D.gerado_em}.`;
  const inicial = location.hash.slice(1);
  mostrarAba(["geral", "mars", "relacoes", "graficos", "calculos"].includes(inicial) ? inicial : "geral");
}

iniciar();
