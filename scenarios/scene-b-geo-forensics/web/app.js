/* GEO 伪造信源核验 Agent · 控制台交互 */
(function () {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const NODES = [
    { id: 's0', title: 'S0 受理', desc: '图片 / 文案 / 来源' },
    { id: 's1', title: 'S1 要素抽取', desc: 'OCR + 主张与实体' },
    { id: 's2', title: 'S2 技术取证', desc: '本期占位' },
    { id: 's3', title: 'S3 信源交叉核验', desc: '并行工具' },
    { id: 's4', title: 'S4 一致性 / 合规', desc: '主体 · 时间 · 语义' },
    { id: 's5', title: 'S5 证据融合', desc: '权重 + 红线' },
    { id: 's6', title: 'S6 处置与报告', desc: '分级 + 举证' },
  ];
  const NODE_Y = [30, 110, 190, 270, 350, 430, 510];
  const CHIP_MAX = 6;

  const $ = (id) => document.getElementById(id);
  const state = { es: null, caseId: null, result: null, files: [], sampleImages: [], chipIndex: 0 };

  function svg(name, attrs) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const clip = (s, n) => (String(s || '').length > n ? String(s).slice(0, n) + '…' : String(s || ''));

  /* ---------- 工作流图 ---------- */
  function buildFlow() {
    const g = $('nodes');
    g.innerHTML = '';
    NODES.forEach((n, i) => {
      const y = NODE_Y[i];
      const node = svg('g', { class: 'node pending', id: 'node-' + n.id });
      node.appendChild(svg('rect', { x: 40, y: y, width: 180, height: 40, rx: 10 }));
      node.appendChild(svg('circle', { class: 'n-led', cx: 56, cy: y + 20, r: 4 }));
      const t1 = svg('text', { class: 'n-title', x: 68, y: y + 17 });
      t1.textContent = n.title;
      const t2 = svg('text', { class: 'n-desc', x: 68, y: y + 31 });
      t2.textContent = n.desc;
      node.appendChild(t1);
      node.appendChild(t2);
      g.appendChild(node);
    });

    const hitl = svg('g', { class: 'node pending', id: 'node-hitl' });
    hitl.appendChild(svg('rect', { x: 40, y: 560, width: 180, height: 36, rx: 10 }));
    hitl.appendChild(svg('circle', { class: 'n-led', cx: 56, cy: 578, r: 4 }));
    const ht = svg('text', { class: 'n-title', x: 68, y: 583 });
    ht.textContent = '人工复核 HITL';
    hitl.appendChild(ht);
    g.appendChild(hitl);

    const c = $('chips');
    c.innerHTML = '';
    for (let i = 0; i < CHIP_MAX; i++) {
      const chip = svg('g', { class: 'chip', id: 'chip-' + i, style: 'display:none' });
      chip.appendChild(svg('rect', { x: 250, y: 196 + i * 32, width: 176, height: 26, rx: 8 }));
      const t = svg('text', { x: 260, y: 213 + i * 32 });
      chip.appendChild(t);
      c.appendChild(chip);
    }
  }

  function setNode(step, status, detail) {
    const node = document.getElementById('node-' + step);
    if (!node) return;
    node.setAttribute('class', 'node ' + status);
    if (detail) {
      const t = node.querySelector('.n-desc');
      if (t) t.textContent = clip(detail, 26);
    }
  }

  function resetFlow() {
    NODES.forEach((n) => setNode(n.id, 'pending', null));
    setNode('hitl', 'pending', null);
    NODES.forEach((n, i) => {
      const t = document.querySelector('#node-' + n.id + ' .n-desc');
      if (t) t.textContent = NODES[i].desc;
    });
    for (let i = 0; i < CHIP_MAX; i++) {
      const chip = $('chip-' + i);
      chip.style.display = 'none';
      chip.setAttribute('class', 'chip');
    }
    state.chipIndex = 0;
  }

  function addChip(label, status) {
    if (state.chipIndex >= CHIP_MAX) return;
    const chip = $('chip-' + state.chipIndex++);
    chip.querySelector('text').textContent = clip(label, 24);
    chip.setAttribute('class', 'chip ' + status);
    chip.style.display = '';
  }

  /* ---------- 面板渲染 ---------- */
  function tagClass(polarity) {
    return polarity === 'up' ? 'up' : (polarity === 'down' ? 'down' : 'note');
  }

  function renderEvidence(list) {
    const ul = $('evidenceList');
    ul.innerHTML = '';
    $('evCount').textContent = list.length;
    if (!list.length) {
      ul.innerHTML = '<li class="empty">暂无证据</li>';
      return;
    }
    list.forEach((e) => {
      const li = document.createElement('li');
      const w = Number(e.weight || 0);
      li.innerHTML =
        '<div class="ev-head"><span class="ev-tool">' + esc(e.tool_cn || e.tool) + '</span>' +
        '<span class="ev-tag ' + tagClass(e.polarity) + '">' + esc(e.status_cn || e.status) + ' ' + (w >= 0 ? '+' : '') + w.toFixed(0) + '</span></div>' +
        '<div class="ev-body">' + esc(clip(e.query, 60)) + '：' + esc(e.summary) + '</div>' +
        '<div class="ev-meta">' + (e.source_url ? '来源：<a href="' + esc(e.source_url) + '" target="_blank" rel="noreferrer">链接</a> · ' : '') +
        '耗时 ' + (e.elapsed_ms || 0) + 'ms' + (e.degraded ? ' · 已降级' : '') + (e.needs_human_review ? ' · 需人工复核' : '') + '</div>';
      ul.appendChild(li);
    });
  }

  function renderFindings(list) {
    const ul = $('findingList');
    ul.innerHTML = '';
    if (!list.length) { ul.innerHTML = '<li class="empty">暂无判定</li>'; return; }
    list.forEach((f) => {
      const li = document.createElement('li');
      li.className = f.ok ? 'ok' : (f.severity === 'high' ? 'bad' : 'warn');
      li.innerHTML = '<b>' + esc(f.dimension) + '</b> · ' + (f.ok ? '通过' : '不通过') + '　' + esc(f.detail);
      ul.appendChild(li);
    });
  }

  function renderMissing(list) {
    const ul = $('missingList');
    ul.innerHTML = '';
    if (!list.length) { ul.innerHTML = '<li class="empty">暂无</li>'; return; }
    list.forEach((m) => {
      const li = document.createElement('li');
      li.textContent = m;
      ul.appendChild(li);
    });
  }

  function renderResult(r) {
    state.result = r;
    const v = r.verdict || {};
    $('scoreNum').textContent = v.risk_score != null ? v.risk_score : '–';
    const badge = $('levelBadge');
    badge.textContent = v.level_cn || '待核验';
    const map = { verifiable: 'ok', doubtful: 'warn', highly_suspected: 'danger', insufficient: 'info' };
    badge.className = 'badge ' + (map[v.level] || '');
    const conf = Math.round((v.confidence || 0) * 100);
    $('confText').textContent = conf ? conf + '%' : '–';
    $('confBar').style.width = conf + '%';
    $('verdictReason').textContent = v.reason || '—';

    renderEvidence(r.evidences || []);
    renderFindings(r.findings || []);
    renderMissing(r.missing_materials || []);

    const box = $('scriptBox');
    box.hidden = !r.script;
    box.textContent = r.script || '';

    const sel = $('overrideEv');
    sel.innerHTML = '<option value="">选择证据条目…</option>';
    (r.evidences || []).forEach((e, i) => {
      const op = document.createElement('option');
      op.value = i;
      op.textContent = '[' + (e.tool_cn || e.tool) + '] ' + clip(e.query, 22);
      sel.appendChild(op);
    });
    setNode('hitl', 'done', r.action_cn || '待复核');
  }

  /* ---------- 核验流程 ---------- */
  function stopStream() {
    if (state.es) { state.es.close(); state.es = null; }
  }

  function listen(caseId) {
    stopStream();
    resetFlow();
    renderEvidence([]);
    renderFindings([]);
    renderMissing([]);
    $('scoreNum').textContent = '–';
    $('levelBadge').textContent = '核验中…';
    $('levelBadge').className = 'badge';
    $('verdictReason').textContent = '正在执行核验流程…';

    const es = new EventSource('/api/cases/' + caseId + '/stream');
    state.es = es;

    es.addEventListener('event', (ev) => {
      const d = JSON.parse(ev.data);
      if (!d.step) return;
      if (d.step.indexOf('tool_') === 0) {
        addChip(d.title || d.step, d.status === 'error' ? 'error' : 'done');
        const e = (d.data || {}).evidence;
        if (e) {
          const cur = Array.from(document.querySelectorAll('#evidenceList li')).length;
          renderEvidence((state.result ? state.result.evidences : []).concat(e));
          void cur;
        }
      } else {
        setNode(d.step, d.status || 'done', d.detail);
      }
    });

    es.addEventListener('result', (ev) => {
      renderResult(JSON.parse(ev.data));
      stopStream();
      $('startBtn').disabled = false;
      $('startBtn').textContent = '开始核验';
    });

    es.addEventListener('error', (ev) => {
      if (ev.data) {
        const d = JSON.parse(ev.data);
        $('verdictReason').textContent = '核验失败：' + (d.message || '未知错误');
      }
      stopStream();
      $('startBtn').disabled = false;
      $('startBtn').textContent = '开始核验';
    });

    es.addEventListener('end', () => {
      stopStream();
      $('startBtn').disabled = false;
      $('startBtn').textContent = '开始核验';
    });
  }

  async function start() {
    const text = $('textInput').value.trim();
    if (!text && !state.files.length && !state.sampleImages.length) {
      alert('请上传图片或填写文案后再开始核验。');
      return;
    }
    $('startBtn').disabled = true;
    $('startBtn').textContent = '核验中…';

    const fd = new FormData();
    fd.append('text', text);
    fd.append('brand', $('brandInput').value.trim());
    fd.append('product', $('productInput').value.trim());
    fd.append('source_url', $('urlInput').value.trim());
    fd.append('image_names', (state.sampleImages || []).join(','));
    state.files.forEach((f) => fd.append('images', f, f.name));

    try {
      const res = await fetch('/api/cases', { method: 'POST', body: fd });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      state.caseId = data.case_id;
      state.result = null;
      listen(data.case_id);
    } catch (err) {
      $('verdictReason').textContent = '提交失败：' + err.message;
      $('startBtn').disabled = false;
      $('startBtn').textContent = '开始核验';
    }
  }

  /* ---------- 输入区 ---------- */
  function renderThumbs() {
    const box = $('thumbs');
    box.innerHTML = '';
    state.files.forEach((f) => {
      const div = document.createElement('div');
      div.className = 'thumb';
      const url = URL.createObjectURL(f);
      div.innerHTML = '<img src="' + url + '" alt="' + esc(f.name) + '" onerror="this.style.display=\'none\'" />' +
        '<span>' + esc(clip(f.name, 14)) + '</span>';
      box.appendChild(div);
    });
    (state.sampleImages || []).forEach((n) => {
      const div = document.createElement('div');
      div.className = 'thumb';
      div.innerHTML = '<span style="bottom:auto;top:0">' + esc(clip(n, 14)) + '</span>';
      box.appendChild(div);
    });
  }

  function bindInput() {
    const input = $('fileInput');
    const zone = $('dropZone');
    input.addEventListener('change', () => {
      state.files = Array.from(input.files || []).slice(0, 6);
      renderThumbs();
    });
    ['dragenter', 'dragover'].forEach((t) => zone.addEventListener(t, (e) => {
      e.preventDefault();
      zone.classList.add('drag');
    }));
    ['dragleave', 'drop'].forEach((t) => zone.addEventListener(t, (e) => {
      e.preventDefault();
      zone.classList.remove('drag');
    }));
    zone.addEventListener('drop', (e) => {
      state.files = Array.from((e.dataTransfer || {}).files || []).slice(0, 6);
      renderThumbs();
    });
  }

  /* ---------- 初始化 ---------- */
  async function init() {
    buildFlow();
    bindInput();

    try {
      const h = await (await fetch('/api/health')).json();
      const real = h.mode === 'real';
      $('modeText').textContent = real ? '真实 API' : 'Mock 演示';
      $('modeBadge').classList.toggle('real', real);
      $('modeHint').textContent = real
        ? '已检测到 API Key：视觉 ' + h.vision_model + ' · 超时 ' + h.timeout + 's'
        : '未配置 API Key，使用本地虚构信源库回放，流程完整可跑。';
    } catch (e) {
      $('modeText').textContent = '服务未连接';
    }

    try {
      const list = await (await fetch('/api/samples')).json();
      const sel = $('sampleSelect');
      list.forEach((c) => {
        const op = document.createElement('option');
        op.value = c.id;
        op.textContent = c.title;
        sel.appendChild(op);
      });
      sel.addEventListener('change', () => {
        const c = list.find((x) => x.id === sel.value);
        if (!c) return;
        $('textInput').value = (c.text || '').trim();
        $('brandInput').value = c.brand || '';
        $('productInput').value = c.product || '';
        $('urlInput').value = c.source_url || '';
        state.sampleImages = c.images || [];
        renderThumbs();
      });
    } catch (e) { /* 忽略 */ }

    $('startBtn').addEventListener('click', start);

    $('overrideBtn').addEventListener('click', async () => {
      const idx = $('overrideEv').value;
      if (idx === '' || !state.caseId) { alert('请先完成一次核验并选择证据条目。'); return; }
      const e = (state.result.evidences || [])[Number(idx)];
      if (!e) return;
      const res = await fetch('/api/cases/' + state.caseId + '/override', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: e.kind, value: e.query, status: $('overrideStatus').value }),
      });
      if (res.ok) renderResult(await res.json());
    });

    $('exportMd').addEventListener('click', () => {
      if (state.caseId) window.open('/api/cases/' + state.caseId + '/export?format=md', '_blank');
    });
    $('exportJson').addEventListener('click', () => {
      if (state.caseId) window.open('/api/cases/' + state.caseId + '/export?format=json', '_blank');
    });

    $('aboutBtn').addEventListener('click', () => { $('aboutModal').hidden = false; });
    $('closeModal').addEventListener('click', () => { $('aboutModal').hidden = true; });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
