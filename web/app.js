/* OCS 题库 · 管理后台前端（原生 JS，无构建步骤） */
(() => {
  'use strict';

  // ------------------------------------------------------------------------
  // 基础工具
  // ------------------------------------------------------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const esc = (value) =>
    String(value ?? '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));

  const fmtNum = (n) => Number(n || 0).toLocaleString('zh-CN');
  const pct = (n) => `${Math.round(Number(n || 0) * 100)}%`;

  function fmtTime(iso) {
    if (!iso) return '—';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    const diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    const pad = (n) => String(n).padStart(2, '0');
    const hm = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    const today = new Date();
    if (date.toDateString() === today.toDateString()) return `今天 ${hm}`;
    const yesterday = new Date(today.getTime() - 86400000);
    if (date.toDateString() === yesterday.toDateString()) return `昨天 ${hm}`;
    return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${hm}`;
  }

  function debounce(fn, wait = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), wait);
    };
  }

  const TYPE_META = {
    single: { label: '单选', cls: 'badge-single' },
    multiple: { label: '多选', cls: 'badge-multiple' },
    judgement: { label: '判断', cls: 'badge-judgement' },
    completion: { label: '填空', cls: 'badge-completion' },
  };

  const SOURCE_META = {
    ai: { label: 'AI 生成', cls: 'badge-ai' },
    yanxi: { label: '言溪', cls: 'badge-yanxi' },
    bank: { label: '本地', cls: 'badge-bank' },
    import: { label: '导入', cls: 'badge-import' },
    manual: { label: '手动', cls: 'badge-manual' },
  };

  const typeBadge = (type) => {
    const meta = TYPE_META[type] || { label: type || '未知', cls: 'badge-soft' };
    return `<span class="badge ${meta.cls}">${esc(meta.label)}</span>`;
  };

  const sourceBadge = (source) => {
    const meta = SOURCE_META[source] || { label: source || '未知', cls: 'badge-soft' };
    return `<span class="badge ${meta.cls}">${esc(meta.label)}</span>`;
  };

  const displayAnswer = (answer) => String(answer || '').split('#').filter(Boolean).join(' ｜ ') || '—';

  function confBar(value) {
    if (value === null || value === undefined || value === '') return '<span class="muted">—</span>';
    const v = Math.max(0, Math.min(1, Number(value)));
    const level = v >= 0.75 ? 'high' : v >= 0.45 ? 'mid' : 'low';
    return `<span class="conf"><span class="conf-bar ${level}"><i style="width:${Math.round(v * 100)}%"></i></span>${pct(v)}</span>`;
  }

  const icons = {
    copy: '<svg viewBox="0 0 24 24" fill="none"><rect x="9" y="9" width="10" height="11" rx="2" stroke="currentColor" stroke-width="1.6"/><path d="M15 5.5A1.5 1.5 0 0 0 13.5 4h-8A1.5 1.5 0 0 0 4 5.5v10A1.5 1.5 0 0 0 5.5 17" stroke="currentColor" stroke-width="1.6"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none"><path d="m5 12.5 4.2 4.2L19 7" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="6.2" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 3.4 3.4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    upload: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 16V5m0 0L8 9m4-4 4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 16v2.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V16" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 4v11m0 0 4-4m-4 4-4-4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 16v2.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V16" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none"><path d="m14.5 5.5 4 4L8 20H4v-4L14.5 5.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="m13 7 4 4" stroke="currentColor" stroke-width="1.6"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 7h14M10 7V5h4v2M7 7l.8 12.1A1.5 1.5 0 0 0 9.3 20h5.4a1.5 1.5 0 0 0 1.5-1.4L17 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    book: '<svg viewBox="0 0 24 24" fill="none"><path d="M5 5.5A2.5 2.5 0 0 1 7.5 3H19v15H7.5A2.5 2.5 0 0 0 5 20.5v-15Z" stroke="currentColor" stroke-width="1.6"/><path d="M5 20.5A2.5 2.5 0 0 1 7.5 18H19v3H7.5A2.5 2.5 0 0 1 5 20.5Z" stroke="currentColor" stroke-width="1.6"/></svg>',
    layers: '<svg viewBox="0 0 24 24" fill="none"><path d="m12 4 8 4.5-8 4.5-8-4.5L12 4Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="m4 13 8 4.5 8-4.5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    zap: '<svg viewBox="0 0 24 24" fill="none"><path d="M13 3 5 13.5h5L9.8 21 19 9.8h-5.6L13 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="3.2" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r=".8" fill="currentColor"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.4" stroke="currentColor" stroke-width="1.6"/><path d="M12 11v5.2M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 4.5 21 20H3L12 4.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 10v4.2M12 17.4v.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    chevronL: '<svg viewBox="0 0 24 24" fill="none"><path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    chevronR: '<svg viewBox="0 0 24 24" fill="none"><path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    key: '<svg viewBox="0 0 24 24" fill="none"><circle cx="8.5" cy="15.5" r="3.5" stroke="currentColor" stroke-width="1.6"/><path d="m11 13 8-8m-2.5 2.5 2 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none"><path d="M3 12s3.2-6 9-6 9 6 9 6-3.2 6-9 6-9-6-9-6Z" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="2.6" stroke="currentColor" stroke-width="1.6"/></svg>',
    eyeOff: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 5.5 20 19M9.9 6.3A9.9 9.9 0 0 1 12 6c5.8 0 9 6 9 6a15 15 0 0 1-3.2 3.8M6.2 8.1A15 15 0 0 0 3 12s3.2 6 9 6c1 0 1.9-.2 2.7-.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    database: '<svg viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="6" rx="7.5" ry="2.8" stroke="currentColor" stroke-width="1.6"/><path d="M4.5 6v11.5c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8V6" stroke="currentColor" stroke-width="1.6"/><path d="M4.5 11.5c0 1.55 3.36 2.8 7.5 2.8s7.5-1.25 7.5-2.8" stroke="currentColor" stroke-width="1.6"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none"><path d="M19 12a7 7 0 1 1-2.05-4.95" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><path d="M19 4.5V9h-4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  };

  // ------------------------------------------------------------------------
  // 状态 & API
  // ------------------------------------------------------------------------
  const state = {
    view: 'overview',
    config: null,
    stats: null,
    bank: { q: '', type: '', source: '', page: 1, size: 20, total: 0, pages: 1, items: [] },
    bankLoading: false,
    testBusy: false,
    requestSeq: 0,
  };

  async function api(path, options = {}) {
    const opts = { headers: { 'Content-Type': 'application/json' }, ...options };
    let response;
    try {
      response = await fetch(path, opts);
    } catch (err) {
      throw new Error('无法连接本地服务，请确认 app.py 正在运行');
    }
    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      throw new Error(`服务返回异常（HTTP ${response.status}）`);
    }
    if (!response.ok && data && data.msg) throw new Error(data.msg);
    if (!response.ok) throw new Error(`请求失败（HTTP ${response.status}）`);
    return data;
  }

  // ------------------------------------------------------------------------
  // Toast / Modal
  // ------------------------------------------------------------------------
  function toast(message, type = 'info') {
    const wrap = $('#toast-wrap');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icon = type === 'ok' ? icons.check : type === 'err' ? icons.warn : icons.info;
    el.innerHTML = `${icon}<span>${esc(message)}</span>`;
    wrap.appendChild(el);
    setTimeout(() => {
      el.classList.add('out');
      setTimeout(() => el.remove(), 220);
    }, 3200);
  }

  let escHandler = null;
  let modalResolve = null;

  function closeModal() {
    $('#modal-root').innerHTML = '';
    if (escHandler) {
      document.removeEventListener('keydown', escHandler);
      escHandler = null;
    }
    if (modalResolve) {
      modalResolve(false);
      modalResolve = null;
    }
  }

  function mountModal(html) {
    const root = $('#modal-root');
    root.innerHTML = `<div class="modal-mask"><div class="modal">${html}</div></div>`;
    const mask = $('.modal-mask', root);
    mask.addEventListener('mousedown', (event) => {
      if (event.target === mask) closeModal();
    });
    escHandler = (event) => {
      if (event.key === 'Escape') closeModal();
    };
    document.addEventListener('keydown', escHandler);
    return root;
  }

  function confirmDialog({ title, message, confirmText = '确认', danger = false }) {
    return new Promise((resolve) => {
      modalResolve = resolve;
      const root = mountModal(`
        <div class="modal-head">
          <div><h3>${esc(title)}</h3><p>${esc(message)}</p></div>
          <button class="btn icon ghost" data-close>${icons.close}</button>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" data-close>取消</button>
          <button class="btn ${danger ? 'danger' : 'primary'}" data-ok>${esc(confirmText)}</button>
        </div>`);
      $$('[data-close]', root).forEach((btn) => btn.addEventListener('click', () => {
        modalResolve = null;
        closeModal();
        resolve(false);
      }));
      $('[data-ok]', root).addEventListener('click', () => {
        modalResolve = null;
        closeModal();
        resolve(true);
      });
    });
  }

  async function copyText(text, button) {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch (err) {
      const area = document.createElement('textarea');
      area.value = text;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      area.remove();
    }
    if (ok) {
      toast('已复制到剪贴板', 'ok');
      if (button) {
        const old = button.innerHTML;
        button.innerHTML = `${icons.check}<span>已复制</span>`;
        setTimeout(() => { button.innerHTML = old; }, 1600);
      }
    } else {
      toast('复制失败，请手动选择复制', 'err');
    }
    return ok;
  }

  // ------------------------------------------------------------------------
  // OCS 配置
  // ------------------------------------------------------------------------
  function ocsConfigText() {
    const origin = window.location.origin;
    return `[
  {
    "name": "本地题库（言溪 + DeepSeek）",
    "homepage": "${origin}",
    "url": "${origin}/api/search",
    "method": "post",
    "type": "fetch",
    "contentType": "json",
    "headers": { "Content-Type": "application/json" },
    "data": {
      "title": "\${title}",
      "options": "\${options}",
      "type": "\${type}"
    },
    "handler": "return (res) => res.code === 1 ? [res.question, res.answer] : [res.msg, undefined]"
  }
]`;
  }

  // ------------------------------------------------------------------------
  // 侧边栏 / 顶栏
  // ------------------------------------------------------------------------
  function updateChrome() {
    const cfg = state.config;
    const stats = state.stats;
    const configured = !!(cfg && cfg.api_key_set);

    const dot = $('#side-dot');
    const text = $('#side-status');
    const model = $('#side-model');
    const pill = $('#ai-pill');

    if (cfg) {
      dot.className = `dot ${configured ? 'dot-ok' : 'dot-warn'}`;
      text.textContent = configured ? 'DeepSeek 已配置' : '等待配置 API Key';
      model.textContent = `${cfg.model} · 缓存${cfg.cache_enabled ? '开启' : '关闭'}`;
      pill.innerHTML = `<span class="dot ${configured ? 'dot-ok' : 'dot-warn'}"></span>${configured ? 'DeepSeek 已就绪' : '未配置 API Key'}`;
    } else {
      dot.className = 'dot dot-err';
      text.textContent = '服务连接失败';
      model.textContent = '请检查 app.py 是否运行';
      pill.innerHTML = '<span class="dot dot-err"></span>服务未连接';
    }

    if (stats) {
      $('#nav-count').textContent = fmtNum(stats.total_questions);
    }
  }

  // ------------------------------------------------------------------------
  // 概览
  // ------------------------------------------------------------------------
  function renderOverview() {
    const stats = state.stats;
    const cfg = state.config;
    if (!stats) {
      $('#view').innerHTML = '<div class="card"><div class="card-body"><div class="skeleton" style="width:40%"></div></div></div>';
      return;
    }

    const needKey = cfg && !cfg.api_key_set;
    const yanxiReady = !!(cfg && cfg.yanxi_enabled && cfg.yanxi_token_set);
    const types = stats.types || [];
    const maxType = Math.max(1, ...types.map((t) => t.count));
    const typeTotal = types.reduce((sum, t) => sum + t.count, 0);

    $('#view').innerHTML = `
      ${needKey ? `
      <div class="callout warn" style="margin-bottom:16px;align-items:center">
        ${icons.key}
        <div class="grow">
          <strong>${yanxiReady ? '言溪已接管大部分题目，建议再配置 DeepSeek 兜底' : '还差一步：配置 DeepSeek API Key'}</strong>
          <div class="hint" style="margin-top:2px">${yanxiReady
            ? '言溪题库已启用：本地未收录的题会先查言溪，只有言溪也没有时才需要 AI。配置 DeepSeek 后，冷门题也能作答。'
            : '没有 Key 时只能命中本地题库和言溪题库。填入 Key 后，两边都没有的题目会自动交给 DeepSeek，并沉淀进题库。'}</div>
        </div>
        <a class="btn soft sm" href="#/settings">去配置</a>
      </div>` : ''}

      <div class="stat-grid">
        <div class="stat">
          <div class="stat-top"><span class="stat-label">题库总量</span><span class="stat-icon">${icons.book}</span></div>
          <div class="stat-value">${fmtNum(stats.total_questions)}<span class="unit">题</span></div>
          <div class="stat-foot"><strong>+${fmtNum(stats.new_today)}</strong> 今日新增 · 越刷越全</div>
        </div>
        <div class="stat">
          <div class="stat-top"><span class="stat-label">今日答题</span><span class="stat-icon green">${icons.zap}</span></div>
          <div class="stat-value">${fmtNum(stats.today_total)}<span class="unit">次</span></div>
          <div class="stat-foot">失败 <strong>${fmtNum(stats.today_failures)}</strong> 次 · 平均 ${fmtNum(stats.avg_ms)} ms</div>
        </div>
        <div class="stat">
          <div class="stat-top"><span class="stat-label">今日命中率</span><span class="stat-icon purple">${icons.target}</span></div>
          <div class="stat-value">${pct(stats.hit_rate)}</div>
          <div class="stat-foot">本地 <strong>${fmtNum(stats.today_bank_hits)}</strong> 次 · 言溪 <strong>${fmtNum(stats.today_yanxi_hits)}</strong> 次</div>
        </div>
        <div class="stat">
          <div class="stat-top"><span class="stat-label">今日 AI 调用</span><span class="stat-icon amber">${icons.layers}</span></div>
          <div class="stat-value">${fmtNum(stats.today_ai_calls)}<span class="unit">次</span></div>
          <div class="stat-foot">消耗 <strong>${fmtNum(stats.today_tokens)}</strong> tokens</div>
        </div>
      </div>

      <div class="overview-grid">
        <div class="stack">
          <div class="card">
            <div class="card-head">
              <div><h2>快速测试</h2><p>不写入题库，用来验证 Key、题面和答案格式</p></div>
              <button class="btn ghost sm" id="fill-demo">填入示例</button>
            </div>
            <div class="card-body">
              <div class="field">
                <label class="label" for="test-question">题干</label>
                <textarea class="textarea" id="test-question" rows="3" placeholder="粘贴一道题，例如：中国现存规模最大、保存最完整的古代宫殿建筑群是？"></textarea>
              </div>
              <div class="field mt-14">
                <label class="label" for="test-options">选项 <span class="muted" style="font-weight:400">（每行一个，可留空）</span></label>
                <textarea class="textarea" id="test-options" rows="4" placeholder="A. 故宫&#10;B. 颐和园&#10;C. 承德避暑山庄&#10;D. 天坛"></textarea>
              </div>
              <div class="row wrap mt-14" style="gap:10px;align-items:flex-end">
                <div class="field" style="width:160px">
                  <label class="label" for="test-type">题型</label>
                  <select class="select" id="test-type">
                    <option value="single">单选题</option>
                    <option value="multiple">多选题</option>
                    <option value="judgement">判断题</option>
                    <option value="completion">填空题</option>
                  </select>
                </div>
                <button class="btn primary" id="do-test" style="height:39px">${icons.zap}<span>获取答案</span></button>
                <span class="hint" style="margin-left:auto;text-align:right">快速测试只验证 DeepSeek；实际刷题会先查本地和言溪</span>
              </div>
              <div id="test-result"></div>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <div><h2>最近答题</h2><p>最新 10 条请求记录</p></div>
              <a class="btn ghost sm" href="#/bank">查看题库</a>
            </div>
            <div class="card-body tight" id="recent-logs">
              ${renderRecentLogs(stats.recent || [])}
            </div>
          </div>
        </div>

        <div class="stack">
          <div class="card">
            <div class="card-head">
              <div><h2>服务状态</h2><p>本机运行，数据不出本地</p></div>
              <span class="badge ${cfg && cfg.api_key_set ? 'badge-bank' : 'badge-soft'}">${cfg && cfg.api_key_set ? '在线' : '待配置'}</span>
            </div>
            <div class="card-body tight">
              <div class="kv">
                <div class="kv-row"><span class="kv-key">题库接口</span><span class="kv-val mono">${esc(window.location.origin)}/api/search</span></div>
                <div class="kv-row"><span class="kv-key">DeepSeek 模型</span><span class="kv-val mono">${esc(cfg ? cfg.model : '—')}</span></div>
                <div class="kv-row"><span class="kv-key">API Key</span><span class="kv-val">${cfg && cfg.api_key_set ? `<span class="badge badge-bank">已配置</span> <span class="mono small">${esc(cfg.api_key_masked)}</span>` : '<span class="badge badge-soft">未配置</span>'}</span></div>
                <div class="kv-row"><span class="kv-key">言溪题库</span><span class="kv-val">${cfg && cfg.yanxi_enabled
                  ? (cfg.yanxi_token_set ? `<span class="badge badge-yanxi">已启用</span> <span class="small muted">今日 ${fmtNum(stats.today_yanxi_hits)} 次命中</span>` : '<span class="badge badge-soft">缺少 Token</span>')
                  : '<span class="badge badge-soft">未启用</span>'}</span></div>
                <div class="kv-row"><span class="kv-key">本地缓存</span><span class="kv-val">${cfg && cfg.cache_enabled ? '已开启' : '已关闭'}</span></div>
                <div class="kv-row"><span class="kv-key">最低置信度</span><span class="kv-val">${cfg ? cfg.min_confidence : '—'}</span></div>
                <div class="kv-row"><span class="kv-key">今日 Token</span><span class="kv-val mono">${fmtNum(stats.today_tokens)}</span></div>
              </div>
              <div class="btn-row mt-14">
                <a class="btn ghost sm" href="#/guide">接入 OCS</a>
                <button class="btn ghost sm" id="copy-config-2">${icons.copy}复制题库配置</button>
              </div>
            </div>
          </div>

          <div class="card">
            <div class="card-head">
              <div><h2>题型分布</h2><p>共 ${fmtNum(typeTotal)} 道已收录题目</p></div>
            </div>
            <div class="card-body tight">
              ${types.length ? `
                <div class="kv" style="gap:2px">
                  ${types.map((t) => `
                    <div style="padding:9px 0">
                      <div class="row between" style="margin-bottom:6px">
                        ${typeBadge(t.type)}
                        <span class="num small">${fmtNum(t.count)}</span>
                      </div>
                      <div style="height:5px;border-radius:4px;background:#f0f2f9;overflow:hidden">
                        <div style="height:100%;width:${Math.max(4, Math.round((t.count / maxType) * 100))}%;border-radius:4px;background:linear-gradient(90deg,#8b8ff0,#6366f1)"></div>
                      </div>
                    </div>`).join('')}
                </div>` : `
                <div class="empty" style="padding:26px 10px">
                  <div class="empty-icon">${icons.layers}</div>
                  <h3>还没有题目</h3>
                  <p>答对或答错都没关系，第一次答题后会自动收录</p>
                </div>`}
            </div>
          </div>
        </div>
      </div>
    `;

    bindOverview();
  }

  function renderRecentLogs(logs) {
    if (!logs.length) {
      return `<div class="empty" style="padding:34px 10px">
        <div class="empty-icon">${icons.zap}</div>
        <h3>还没有答题记录</h3>
        <p>在 OCS 里刷一道题，或使用上面的快速测试</p>
      </div>`;
    }
    return logs.map((log) => `
      <div class="log-row">
        ${log.success ? sourceBadge(log.source) : '<span class="badge badge-soft">未命中</span>'}
        <div class="log-main">
          <div class="log-q" title="${esc(log.question)}">${esc(log.question)}</div>
          <div class="log-sub">
            <span>${log.success ? esc(displayAnswer(log.answer)) : esc(log.message || '无答案')}</span>
          </div>
        </div>
        <div class="log-time">${fmtTime(log.ts)}</div>
      </div>`).join('');
  }

  function bindOverview() {
    $('#fill-demo')?.addEventListener('click', () => {
      $('#test-question').value = '中国现存规模最大、保存最完整的古代宫殿建筑群是？';
      $('#test-options').value = 'A. 故宫\nB. 颐和园\nC. 承德避暑山庄\nD. 天坛';
      $('#test-type').value = 'single';
    });

    $('#do-test')?.addEventListener('click', runTest);
    $('#copy-config-2')?.addEventListener('click', (event) => copyText(ocsConfigText(), event.currentTarget));
  }

  async function runTest() {
    if (state.testBusy) return;
    const question = $('#test-question').value.trim();
    const options = $('#test-options').value;
    const type = $('#test-type').value;
    const resultBox = $('#test-result');
    const button = $('#do-test');

    if (!question) {
      toast('请先填写题干', 'err');
      $('#test-question').focus();
      return;
    }

    state.testBusy = true;
    button.disabled = true;
    button.innerHTML = '<span class="spin"></span><span>思考中…</span>';
    resultBox.innerHTML = '<div class="result"><div class="result-kicker">正在请求 DeepSeek</div><div class="result-hint">通常需要 1–8 秒，请稍候。</div></div>';

    try {
      const data = await api('/api/test', {
        method: 'POST',
        body: JSON.stringify({ title: question, options, type }),
      });
      if (data.code === 1) {
        const low = data.confidence !== null && data.confidence < (state.config?.min_confidence ?? 0.3);
        resultBox.innerHTML = `
          <div class="result ok">
            <div class="result-head">
              <span class="result-kicker">答案</span>
              <span class="badge ${low ? 'badge-soft' : 'badge-bank'}">${low ? '置信度偏低' : '可用'}</span>
            </div>
            <div class="result-answer">${esc(displayAnswer(data.answer))}</div>
            <div class="result-meta">
              ${typeBadge(type)}
              <span class="badge badge-ai">DeepSeek</span>
              ${confBar(data.confidence)}
              <span class="muted small">${fmtNum(data.elapsed_ms)} ms · ${fmtNum(data.tokens)} tokens</span>
            </div>
            ${data.reason ? `<div class="result-reason">判断依据：${esc(data.reason)}</div>` : ''}
            <div class="result-hint">测试结果不会写入题库。满意的话，直接去 OCS 里答题即可自动收录。</div>
          </div>`;
      } else {
        resultBox.innerHTML = `
          <div class="result err">
            <div class="result-head"><span class="result-kicker">未能作答</span></div>
            <div class="result-answer">${esc(data.msg || '未知错误')}</div>
            <div class="result-hint">检查 API Key、账户余额和网络后重试；也可以换用 deepseek-reasoner 模型。</div>
          </div>`;
      }
    } catch (err) {
      resultBox.innerHTML = `
        <div class="result err">
          <div class="result-head"><span class="result-kicker">请求失败</span></div>
          <div class="result-answer">${esc(err.message)}</div>
        </div>`;
    } finally {
      state.testBusy = false;
      button.disabled = false;
      button.innerHTML = `${icons.zap}<span>获取答案</span>`;
    }
  }

  // ------------------------------------------------------------------------
  // 题库
  // ------------------------------------------------------------------------
  function renderBank() {
    $('#view').innerHTML = `
      <div class="card">
        <div class="toolbar">
          <div class="search">
            ${icons.search}
            <input class="input" id="bank-search" placeholder="搜索题目或答案…" value="${esc(state.bank.q)}">
          </div>
          <select class="select" id="bank-type" style="width:120px">
            <option value="">全部题型</option>
            <option value="single">单选</option>
            <option value="multiple">多选</option>
            <option value="judgement">判断</option>
            <option value="completion">填空</option>
          </select>
          <select class="select" id="bank-source" style="width:120px">
            <option value="">全部来源</option>
            <option value="ai">AI 生成</option>
            <option value="yanxi">言溪题库</option>
            <option value="import">导入</option>
            <option value="manual">手动</option>
          </select>
          <div class="spacer"></div>
          <button class="btn ghost sm" id="bank-import">${icons.upload}<span>导入</span></button>
          <div style="position:relative" id="export-wrap">
            <button class="btn ghost sm" id="bank-export">${icons.download}<span>导出</span></button>
          </div>
          <button class="btn primary sm" id="bank-create">${icons.plus}<span>新增</span></button>
        </div>
        <div id="bank-table"><div class="table-wrap"><div class="empty"><div class="skeleton" style="width:60%;margin:0 auto"></div></div></div></div>
        <div id="bank-pager"></div>
      </div>
      <div class="hint" style="margin-top:12px;line-height:1.8">
        提示：多选题答案用 <span class="inline-code">#</span> 分隔，例如 <span class="inline-code">选项一#选项三</span>；判断题答案写 <span class="inline-code">正确</span> 或 <span class="inline-code">错误</span>。
      </div>
    `;

    $('#bank-type').value = state.bank.type;
    $('#bank-source').value = state.bank.source;

    $('#bank-search').addEventListener('input', debounce((event) => {
      state.bank.q = event.target.value.trim();
      state.bank.page = 1;
      refreshBank();
    }, 320));

    $('#bank-type').addEventListener('change', (event) => {
      state.bank.type = event.target.value;
      state.bank.page = 1;
      refreshBank();
    });
    $('#bank-source').addEventListener('change', (event) => {
      state.bank.source = event.target.value;
      state.bank.page = 1;
      refreshBank();
    });

    $('#bank-import').addEventListener('click', openImportModal);
    $('#bank-create').addEventListener('click', () => openEditModal(null));
    $('#bank-export').addEventListener('click', (event) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const menu = document.createElement('div');
      menu.className = 'card';
      menu.style.cssText = `position:fixed;z-index:70;top:${rect.bottom + 6}px;left:${rect.left - 60}px;padding:6px;min-width:150px;box-shadow:var(--shadow)`;
      menu.innerHTML = `
        <button class="btn ghost sm" style="width:100%;justify-content:flex-start" data-fmt="json">导出 JSON</button>
        <button class="btn ghost sm" style="width:100%;justify-content:flex-start;margin-top:4px" data-fmt="csv">导出 CSV</button>`;
      document.body.appendChild(menu);
      const close = (e) => { if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('mousedown', close); } };
      setTimeout(() => document.addEventListener('mousedown', close), 0);
      $$('[data-fmt]', menu).forEach((btn) => btn.addEventListener('click', () => {
        window.location.href = `/api/bank/export?format=${btn.dataset.fmt}`;
        menu.remove();
      }));
    });

    $('#bank-table').addEventListener('click', async (event) => {
      const editBtn = event.target.closest('[data-edit]');
      const delBtn = event.target.closest('[data-del]');
      if (editBtn) {
        const item = state.bank.items.find((x) => String(x.id) === editBtn.dataset.edit);
        if (item) openEditModal(item);
      }
      if (delBtn) {
        const item = state.bank.items.find((x) => String(x.id) === delBtn.dataset.del);
        if (!item) return;
        const ok = await confirmDialog({
          title: '删除这道题？',
          message: item.question.slice(0, 80),
          confirmText: '删除',
          danger: true,
        });
        if (!ok) return;
        try {
          await api(`/api/bank/${item.id}`, { method: 'DELETE' });
          toast('已删除', 'ok');
          refreshBank();
          loadStats();
        } catch (err) {
          toast(err.message, 'err');
        }
      }
    });

    $('#bank-pager').addEventListener('click', (event) => {
      const btn = event.target.closest('[data-page]');
      if (!btn) return;
      const page = Number(btn.dataset.page);
      if (!page || page === state.bank.page) return;
      state.bank.page = page;
      refreshBank();
    });

    refreshBank();
  }

  async function refreshBank() {
    state.bankLoading = true;
    const seq = ++state.requestSeq;
    const params = new URLSearchParams({
      page: String(state.bank.page),
      page_size: String(state.bank.size),
    });
    if (state.bank.q) params.set('q', state.bank.q);
    if (state.bank.type) params.set('type', state.bank.type);
    if (state.bank.source) params.set('source', state.bank.source);

    try {
      const res = await api(`/api/bank?${params.toString()}`);
      if (seq !== state.requestSeq) return;
      const data = res.data;
      state.bank.items = data.items;
      state.bank.total = data.total;
      state.bank.pages = data.pages;
      state.bank.page = data.page;
      paintBankTable();
    } catch (err) {
      if (seq === state.requestSeq) {
        const container = $('#bank-table');
        if (container) {
          container.innerHTML = `<div class="empty"><div class="empty-icon">${icons.warn}</div><h3>加载失败</h3><p>${esc(err.message)}</p></div>`;
        }
      }
    } finally {
      state.bankLoading = false;
    }
  }

  function paintBankTable() {
    const { items, total, page, pages } = state.bank;
    const container = $('#bank-table');
    if (!container) return;

    if (!items.length) {
      const filtered = state.bank.q || state.bank.type || state.bank.source;
      container.innerHTML = `<div class="empty">
        <div class="empty-icon">${icons.book}</div>
        <h3>${filtered ? '没有符合条件的题目' : '题库还是空的'}</h3>
        <p>${filtered ? '换个关键词或清空筛选试试' : '在 OCS 里答一道题，或手动新增 / 导入题库'}</p>
        ${filtered ? '' : `<div class="btn-row" style="justify-content:center;margin-top:14px"><button class="btn soft sm" id="empty-import">${icons.upload}导入题库</button></div>`}
      </div>`;
      $('#empty-import')?.addEventListener('click', openImportModal);
    } else {
      container.innerHTML = `
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width:48%">题目</th>
                <th style="width:24%">答案</th>
                <th>来源</th>
                <th>置信度</th>
                <th style="text-align:right">命中</th>
                <th>更新时间</th>
                <th style="width:76px"></th>
              </tr>
            </thead>
            <tbody>
              ${items.map((item) => `
                <tr>
                  <td class="q-cell">
                    <div class="q-text" title="${esc(item.question)}">${esc(item.question)}</div>
                    <div class="q-meta">${typeBadge(item.qtype)}<span>#${item.id}</span></div>
                  </td>
                  <td class="a-cell"><div class="a-text" title="${esc(item.answer)}">${esc(displayAnswer(item.answer))}</div></td>
                  <td>${sourceBadge(item.source)}</td>
                  <td>${confBar(item.confidence)}</td>
                  <td style="text-align:right" class="num">${fmtNum(item.hits)}</td>
                  <td class="time">${fmtTime(item.updated_at)}</td>
                  <td>
                    <div class="actions">
                      <button class="btn icon" data-edit="${item.id}" title="编辑">${icons.edit}</button>
                      <button class="btn icon del" data-del="${item.id}" title="删除">${icons.trash}</button>
                    </div>
                  </td>
                </tr>`).join('')}
            </tbody>
          </table>
        </div>`;
    }

    $('#bank-pager').innerHTML = `
      <div class="pager">
        <span>共 <strong style="color:var(--text-2)">${fmtNum(total)}</strong> 题 · 第 ${page} / ${pages} 页</span>
        <div class="pager-btns">
          <button class="btn ghost sm" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>${icons.chevronL}</button>
          ${pagerNumbers(page, pages).map((n) => n === '…'
            ? '<span class="muted" style="padding:0 4px">…</span>'
            : `<button class="btn ghost sm ${n === page ? 'active' : ''}" data-page="${n}">${n}</button>`).join('')}
          <button class="btn ghost sm" data-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>${icons.chevronR}</button>
        </div>
      </div>`;
  }

  function pagerNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = new Set([1, total, current, current - 1, current + 1]);
    const list = Array.from(pages).filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
    const result = [];
    let prev = 0;
    for (const n of list) {
      if (prev && n - prev > 1) result.push('…');
      result.push(n);
      prev = n;
    }
    return result;
  }

  function openEditModal(item) {
    const isEdit = !!item;
    const root = mountModal(`
      <div class="modal-head">
        <div><h3>${isEdit ? '编辑题目' : '新增题目'}</h3><p>${isEdit ? '修改后的答案会立即用于后续答题' : '手动录入的题目会优先命中，不再调用 AI'}</p></div>
        <button class="btn icon ghost" data-close>${icons.close}</button>
      </div>
      <div class="modal-body">
        <div class="field">
          <label class="label">题干</label>
          <textarea class="textarea" id="edit-question" rows="3" placeholder="粘贴完整题干">${isEdit ? esc(item.question) : ''}</textarea>
        </div>
        <div class="field">
          <label class="label">选项 <span class="muted" style="font-weight:400">（每行一个，可留空）</span></label>
          <textarea class="textarea" id="edit-options" rows="3" placeholder="A. …&#10;B. …">${isEdit ? esc(item.options) : ''}</textarea>
        </div>
        <div class="form-grid">
          <div class="field">
            <label class="label">题型</label>
            <select class="select" id="edit-type">
              <option value="single">单选题</option>
              <option value="multiple">多选题</option>
              <option value="judgement">判断题</option>
              <option value="completion">填空题</option>
            </select>
          </div>
          <div class="field">
            <label class="label">答案</label>
            <input class="input" id="edit-answer" placeholder="单选填选项内容；多选用 # 分隔" value="${isEdit ? esc(item.answer) : ''}">
          </div>
        </div>
        <div class="hint" style="margin-top:10px">答案建议直接填选项文本（如「光合作用」）。多选写成 <span class="inline-code">选项一#选项二</span>。</div>
      </div>
      <div class="modal-foot">
        <button class="btn ghost" data-close>取消</button>
        <button class="btn primary" id="edit-save">${isEdit ? '保存修改' : '新增题目'}</button>
      </div>`);

    if (isEdit) $('#edit-type', root).value = item.qtype || 'single';

    $$('[data-close]', root).forEach((btn) => btn.addEventListener('click', closeModal));
    $('#edit-save', root).addEventListener('click', async () => {
      const payload = {
        question: $('#edit-question', root).value.trim(),
        options: $('#edit-options', root).value,
        type: $('#edit-type', root).value,
        answer: $('#edit-answer', root).value.trim(),
      };
      if (!payload.question || !payload.answer) {
        toast('题干和答案不能为空', 'err');
        return;
      }
      const button = $('#edit-save', root);
      button.disabled = true;
      try {
        if (isEdit) {
          await api(`/api/bank/${item.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        } else {
          await api('/api/bank', { method: 'POST', body: JSON.stringify(payload) });
        }
        closeModal();
        toast(isEdit ? '已保存' : '已新增', 'ok');
        refreshBank();
        loadStats();
      } catch (err) {
        toast(err.message, 'err');
      } finally {
        button.disabled = false;
      }
    });
  }

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = '';
    let quoted = false;
    for (let i = 0; i < text.length; i += 1) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i += 1; } else { quoted = false; }
        } else {
          field += ch;
        }
      } else if (ch === '"') {
        quoted = true;
      } else if (ch === ',') {
        row.push(field);
        field = '';
      } else if (ch === '\n') {
        row.push(field);
        rows.push(row);
        row = [];
        field = '';
      } else if (ch !== '\r') {
        field += ch;
      }
    }
    if (field || row.length) {
      row.push(field);
      rows.push(row);
    }
    return rows.filter((r) => r.some((cell) => String(cell).trim()));
  }

  function csvToItems(text) {
    const rows = parseCSV(text);
    if (!rows.length) return [];
    const header = rows[0].map((h) => h.trim().toLowerCase());
    const idx = (names) => names.map((n) => header.indexOf(n)).find((i) => i >= 0);
    const qIdx = idx(['question', '题目', '题干', 'title']);
    const aIdx = idx(['answer', '答案']);
    const oIdx = idx(['options', '选项']);
    const tIdx = idx(['type', 'qtype', '题型']);
    if (qIdx === undefined || aIdx === undefined) {
      throw new Error('CSV 需要包含 question/题目 与 answer/答案 两列');
    }
    return rows.slice(1).map((row) => ({
      question: row[qIdx] || '',
      answer: row[aIdx] || '',
      options: oIdx === undefined ? '' : row[oIdx] || '',
      type: tIdx === undefined ? '' : (row[tIdx] || '').trim(),
    }));
  }

  function openImportModal() {
    const root = mountModal(`
      <div class="modal-head">
        <div><h3>导入题库</h3><p>支持 JSON 数组或 CSV，题目会按归一化文本自动去重</p></div>
        <button class="btn icon ghost" data-close>${icons.close}</button>
      </div>
      <div class="modal-body">
        <label class="drop" id="drop-zone" style="display:block;border:1.5px dashed var(--line-strong);border-radius:12px;padding:22px;text-align:center;cursor:pointer;background:var(--surface-2)">
          <input type="file" id="import-file" accept=".json,.csv,.txt" hidden>
          <div style="font-size:13px;font-weight:600;color:var(--text-2)">点击选择文件</div>
          <div class="hint" style="margin-top:4px">.json / .csv，也可以直接把内容粘贴到下面</div>
        </label>
        <div class="field" style="margin-top:14px">
          <label class="label">或粘贴内容</label>
          <textarea class="textarea" id="import-text" rows="7" placeholder='[{"question": "1+1=?", "answer": "2", "type": "single"}]'></textarea>
        </div>
        <div class="hint" style="margin-top:8px">JSON 字段：question、answer 必填；options、type、confidence 可选。CSV 表头支持 question/题目、answer/答案、options、type。</div>
      </div>
      <div class="modal-foot">
        <button class="btn ghost" data-close>取消</button>
        <button class="btn primary" id="import-go">开始导入</button>
      </div>`);

    $$('[data-close]', root).forEach((btn) => btn.addEventListener('click', closeModal));

    $('#drop-zone', root).addEventListener('click', () => $('#import-file', root).click());
    $('#import-file', root).addEventListener('change', async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      const text = await file.text();
      $('#import-text', root).value = text;
      toast(`已读取 ${file.name}`, 'ok');
    });

    $('#import-go', root).addEventListener('click', async () => {
      const raw = $('#import-text', root).value.trim();
      if (!raw) {
        toast('请先选择文件或粘贴内容', 'err');
        return;
      }
      let items;
      try {
        if (raw.startsWith('[') || raw.startsWith('{')) {
          const parsed = JSON.parse(raw);
          items = Array.isArray(parsed) ? parsed : parsed.items;
        } else {
          items = csvToItems(raw);
        }
      } catch (err) {
        toast(`解析失败：${err.message}`, 'err');
        return;
      }
      if (!Array.isArray(items) || !items.length) {
        toast('没有解析到题目数据', 'err');
        return;
      }
      const button = $('#import-go', root);
      button.disabled = true;
      button.textContent = '导入中…';
      try {
        const res = await api('/api/bank/import', { method: 'POST', body: JSON.stringify({ items }) });
        closeModal();
        toast(res.msg, 'ok');
        state.bank.page = 1;
        refreshBank();
        loadStats();
      } catch (err) {
        toast(err.message, 'err');
        button.disabled = false;
        button.textContent = '开始导入';
      }
    });
  }

  // ------------------------------------------------------------------------
  // 设置
  // ------------------------------------------------------------------------
  function renderSettings() {
    const cfg = state.config;
    if (!cfg) {
      $('#view').innerHTML = `<div class="card"><div class="empty"><div class="empty-icon">${icons.warn}</div><h3>无法读取配置</h3><p>请确认本地服务正在运行，然后刷新页面。</p></div></div>`;
      return;
    }

    $('#view').innerHTML = `
      <div class="row between" style="margin-bottom:14px">
        <div class="hint">配置只保存在本机 <span class="inline-code">data/config.json</span>，不会上传到任何服务器。</div>
        <button class="btn primary" id="save-settings">保存设置</button>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head">
            <div><h2>DeepSeek 连接</h2><p>支持 DeepSeek 官方接口，也兼容任何 OpenAI 格式的接口</p></div>
            <span class="badge ${cfg.api_key_set ? 'badge-bank' : 'badge-soft'}">${cfg.api_key_set ? '已配置' : '未配置'}</span>
          </div>
          <div class="card-body">
            <div class="field">
              <label class="label" for="set-key">API Key</label>
              <div style="position:relative">
                <input class="input" id="set-key" type="password" autocomplete="off" spellcheck="false"
                  placeholder="${cfg.api_key_set ? esc(cfg.api_key_masked) + '（留空则不修改）' : 'sk-… 在 platform.deepseek.com 创建'}"
                  style="padding-right:92px">
                <div style="position:absolute;right:6px;top:5px;display:flex;gap:2px">
                  <button class="btn icon ghost" id="toggle-key" title="显示/隐藏 Key" style="border:none">${icons.eye}</button>
                </div>
              </div>
              <div class="hint">${cfg.api_key_source === 'env' ? '当前 Key 来自环境变量 DEEPSEEK_API_KEY，修改后需取消环境变量才生效。' : '留空保存表示沿用原 Key；如需清空，点下面的「清除 Key」。'}</div>
            </div>

            <div class="form-grid mt-18">
              <div class="field">
                <label class="label" for="set-base">接口地址（Base URL）</label>
                <input class="input" id="set-base" value="${esc(cfg.base_url)}" spellcheck="false">
              </div>
              <div class="field">
                <label class="label" for="set-model">模型</label>
                <input class="input" id="set-model" list="model-list" value="${esc(cfg.model)}" spellcheck="false">
                <datalist id="model-list">
                  <option value="deepseek-chat">deepseek-chat · 快，适合刷题</option>
                  <option value="deepseek-reasoner">deepseek-reasoner · 更准，但更慢</option>
                </datalist>
              </div>
            </div>

            <div class="btn-row mt-18">
              <button class="btn ghost" id="test-conn">测试连接</button>
              <button class="btn ghost" id="clear-key">清除 Key</button>
              <span class="small muted" id="conn-status"></span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <div><h2>言溪题库</h2><p>你原有的题库，作为本地服务的第一上游题源</p></div>
            <span class="badge ${cfg.yanxi_enabled && cfg.yanxi_token_set ? 'badge-yanxi' : 'badge-soft'}">${cfg.yanxi_enabled && cfg.yanxi_token_set ? '已启用' : '未启用'}</span>
          </div>
          <div class="card-body tight">
            <div class="switch">
              <div class="switch-info"><div class="switch-title">启用言溪题库</div><div class="switch-desc">本地未收录时先查言溪，命中后直接返回并缓存，不再调用 DeepSeek</div></div>
              <label class="toggle"><input type="checkbox" id="set-yanxi" ${cfg.yanxi_enabled ? 'checked' : ''}><span></span></label>
            </div>
            <div class="field mt-14">
              <label class="label" for="set-yanxi-token">Token</label>
              <div style="position:relative">
                <input class="input" id="set-yanxi-token" type="password" autocomplete="off" spellcheck="false"
                  placeholder="${cfg.yanxi_token_set ? esc(cfg.yanxi_token_masked) + '（留空则不修改）' : '粘贴言溪题库的 token'}"
                  style="padding-right:44px">
                <button class="btn icon ghost" id="toggle-yanxi-token" title="显示/隐藏 Token" style="border:none;position:absolute;right:4px;top:3px">${icons.eye}</button>
              </div>
              <div class="hint">Token 只保存在本机；接口返回时始终打码。留空保存表示沿用原 Token。</div>
            </div>
            <div class="form-grid mt-14">
              <div class="field">
                <label class="label" for="set-yanxi-url">接口地址</label>
                <input class="input" id="set-yanxi-url" value="${esc(cfg.yanxi_url)}" spellcheck="false">
              </div>
              <div class="field">
                <label class="label" for="set-yanxi-timeout">超时（秒）</label>
                <input class="input" id="set-yanxi-timeout" type="number" min="3" max="120" step="1" value="${cfg.yanxi_timeout}">
              </div>
            </div>
            <div class="btn-row mt-14">
              <button class="btn ghost sm" id="clear-yanxi">清除 Token</button>
              <span class="small muted">${cfg.yanxi_token_set ? `当前：${esc(cfg.yanxi_token_masked)}` : '尚未配置 Token'}</span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><h2>答题策略</h2><p>命中本地题库时不消耗任何 token</p></div></div>
          <div class="card-body tight">
            <div class="switch">
              <div class="switch-info"><div class="switch-title">启用 AI 兜底</div><div class="switch-desc">本地题库没有的题目，自动请求 DeepSeek</div></div>
              <label class="toggle"><input type="checkbox" id="set-ai" ${cfg.ai_enabled ? 'checked' : ''}><span></span></label>
            </div>
            <div class="switch">
              <div class="switch-info"><div class="switch-title">本地题库缓存</div><div class="switch-desc">AI 答过的题自动入库，下次直接命中；建议开启</div></div>
              <label class="toggle"><input type="checkbox" id="set-cache" ${cfg.cache_enabled ? 'checked' : ''}><span></span></label>
            </div>
            <div class="switch">
              <div class="switch-info"><div class="switch-title">相似题模糊匹配</div><div class="switch-desc">题干只差标点/空格时也算命中；开启后可能误匹配，默认关闭</div></div>
              <label class="toggle"><input type="checkbox" id="set-fuzzy" ${cfg.fuzzy_match ? 'checked' : ''}><span></span></label>
            </div>

            <div class="divider"></div>

            <div class="field">
              <label class="label">最低置信度 <span class="hint" style="font-weight:400">低于该值直接返回「未找到」，避免答错并污染题库</span></label>
              <div class="range-row">
                <input type="range" id="set-conf" min="0" max="1" step="0.05" value="${cfg.min_confidence}">
                <span class="range-val" id="conf-val">${Number(cfg.min_confidence).toFixed(2)}</span>
              </div>
            </div>

            <div class="form-grid three mt-18">
              <div class="field">
                <label class="label" for="set-temp">Temperature</label>
                <input class="input" id="set-temp" type="number" min="0" max="2" step="0.1" value="${cfg.temperature}">
              </div>
              <div class="field">
                <label class="label" for="set-tokens">最大 Token</label>
                <input class="input" id="set-tokens" type="number" min="128" max="8000" step="64" value="${cfg.max_tokens}">
              </div>
              <div class="field">
                <label class="label" for="set-timeout">超时（秒）</label>
                <input class="input" id="set-timeout" type="number" min="5" max="300" step="5" value="${cfg.timeout}">
              </div>
            </div>
            <div class="hint mt-8">建议 temperature 保持 0–0.3；reasoner 模型会忽略该参数，但需要把「最大 Token」调到 2000 以上，否则推理过程可能占满额度。</div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><h2>数据管理</h2><p>题库保存在本机 SQLite，可直接备份或迁移</p></div></div>
          <div class="card-body">
            <div class="kv" style="margin-bottom:6px">
              <div class="kv-row"><span class="kv-key">题库文件</span><span class="kv-val mono">data/bank.db</span></div>
              <div class="kv-row"><span class="kv-key">配置文件</span><span class="kv-val mono">data/config.json</span></div>
              <div class="kv-row"><span class="kv-key">当前题量</span><span class="kv-val">${fmtNum(state.stats?.total_questions || 0)} 题</span></div>
            </div>
            <div class="btn-row">
              <button class="btn ghost sm" id="exp-json">${icons.download}导出 JSON</button>
              <button class="btn ghost sm" id="exp-csv">${icons.download}导出 CSV</button>
              <button class="btn ghost sm" id="imp-data">${icons.upload}导入题库</button>
            </div>
          </div>
        </div>
      </div>
    `;

    $('#toggle-key').addEventListener('click', (event) => {
      const input = $('#set-key');
      input.type = input.type === 'password' ? 'text' : 'password';
      event.currentTarget.innerHTML = input.type === 'password' ? icons.eye : icons.eyeOff;
    });

    $('#set-conf').addEventListener('input', (event) => {
      $('#conf-val').textContent = Number(event.target.value).toFixed(2);
    });

    $('#save-settings').addEventListener('click', (event) => saveSettings(event.currentTarget));
    $('#test-conn').addEventListener('click', async () => {
      const status = $('#conn-status');
      status.textContent = '正在保存并测试…';
      const saved = await saveSettings(null, true);
      if (!saved) { status.textContent = '保存失败'; return; }
      try {
        const data = await api('/api/ping', { method: 'POST', body: '{}' });
        if (data.code === 1) {
          status.innerHTML = `<span class="badge badge-bank">连接正常</span> <span class="muted">${fmtNum(data.data.latency_ms)} ms · ${esc(data.data.model)}</span>`;
          toast('DeepSeek 连接正常', 'ok');
        } else {
          status.innerHTML = `<span class="badge badge-soft">失败</span> <span class="muted">${esc(data.msg)}</span>`;
          toast(data.msg, 'err');
        }
      } catch (err) {
        status.innerHTML = `<span class="badge badge-soft">失败</span> <span class="muted">${esc(err.message)}</span>`;
        toast(err.message, 'err');
      }
    });

    $('#clear-key').addEventListener('click', async () => {
      const ok = await confirmDialog({ title: '清除 API Key？', message: '清除后将无法使用 AI 兜底，只能命中已收录题目。', confirmText: '清除', danger: true });
      if (!ok) return;
      try {
        await api('/api/config', { method: 'POST', body: JSON.stringify({ clear_key: true }) });
        state.config = (await api('/api/config')).data;
        toast('已清除 Key', 'ok');
        updateChrome();
        renderSettings();
      } catch (err) {
        toast(err.message, 'err');
      }
    });

    $('#toggle-yanxi-token').addEventListener('click', (event) => {
      const input = $('#set-yanxi-token');
      input.type = input.type === 'password' ? 'text' : 'password';
      event.currentTarget.innerHTML = input.type === 'password' ? icons.eye : icons.eyeOff;
    });

    $('#clear-yanxi').addEventListener('click', async () => {
      const ok = await confirmDialog({
        title: '清除言溪 Token？',
        message: '清除后将不再查询言溪题库，本地未收录的题会直接交给 DeepSeek。',
        confirmText: '清除',
        danger: true,
      });
      if (!ok) return;
      try {
        await api('/api/config', { method: 'POST', body: JSON.stringify({ clear_yanxi_token: true }) });
        state.config = (await api('/api/config')).data;
        toast('已清除言溪 Token', 'ok');
        updateChrome();
        renderSettings();
      } catch (err) {
        toast(err.message, 'err');
      }
    });

    $('#exp-json').addEventListener('click', () => { window.location.href = '/api/bank/export?format=json'; });
    $('#exp-csv').addEventListener('click', () => { window.location.href = '/api/bank/export?format=csv'; });
    $('#imp-data').addEventListener('click', openImportModal);
  }

  async function saveSettings(button, silent = false) {
    const key = $('#set-key').value.trim();
    const yanxiToken = $('#set-yanxi-token').value.trim();
    const payload = {
      base_url: $('#set-base').value.trim() || 'https://api.deepseek.com',
      model: $('#set-model').value.trim() || 'deepseek-chat',
      ai_enabled: $('#set-ai').checked,
      cache_enabled: $('#set-cache').checked,
      fuzzy_match: $('#set-fuzzy').checked,
      min_confidence: Number($('#set-conf').value),
      temperature: Number($('#set-temp').value),
      max_tokens: Number($('#set-tokens').value),
      timeout: Number($('#set-timeout').value),
      yanxi_enabled: $('#set-yanxi').checked,
      yanxi_url: $('#set-yanxi-url').value.trim() || 'https://tk.enncy.cn/query',
      yanxi_timeout: Number($('#set-yanxi-timeout').value),
    };
    if (key) payload.api_key = key;
    if (yanxiToken) payload.yanxi_token = yanxiToken;

    if (button) {
      button.disabled = true;
      button.textContent = '保存中…';
    }
    try {
      const res = await api('/api/config', { method: 'POST', body: JSON.stringify(payload) });
      state.config = res.data;
      if (key) {
        const input = $('#set-key');
        if (input) {
          input.value = '';
          input.type = 'password';
          input.placeholder = `${state.config.api_key_masked}（留空则不修改）`;
        }
        const toggle = $('#toggle-key');
        if (toggle) toggle.innerHTML = icons.eye;
      }
      if (yanxiToken) {
        const input = $('#set-yanxi-token');
        if (input) {
          input.value = '';
          input.type = 'password';
          input.placeholder = `${state.config.yanxi_token_masked}（留空则不修改）`;
        }
        const toggle = $('#toggle-yanxi-token');
        if (toggle) toggle.innerHTML = icons.eye;
      }
      updateChrome();
      await loadStats();
      if (!silent) toast('设置已保存', 'ok');
      return true;
    } catch (err) {
      toast(err.message, 'err');
      return false;
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = '保存设置';
      }
    }
  }

  // ------------------------------------------------------------------------
  // 使用指南
  // ------------------------------------------------------------------------
  function renderGuide() {
    const origin = window.location.origin;
    $('#view').innerHTML = `
      <div class="steps">
        <div class="card step">
          <div class="step-num">1</div>
          <div class="step-body">
            <h3>保持本地服务运行</h3>
            <p>题库服务地址是 <span class="inline-code">${esc(origin)}</span>。关闭命令行窗口或按 Ctrl+C 后，OCS 会连不上题库。重新启动只需双击项目里的「启动.bat」。</p>
            <div class="btn-row"><a class="btn ghost sm" href="${esc(origin)}/api/health" target="_blank">检查服务状态</a></div>
          </div>
        </div>

        <div class="card step">
          <div class="step-num">2</div>
          <div class="step-body">
            <h3>配置 DeepSeek API Key</h3>
            <p>言溪题库的 Token 在「设置 → 言溪题库」里填写（本机已经配置好）。再到 <a class="btn link" href="https://platform.deepseek.com/api_keys" target="_blank" rel="noreferrer">platform.deepseek.com</a> 创建 DeepSeek Key 并粘贴保存。</p>
            <p>没有 DeepSeek Key 也能用：本地题库和言溪题库会正常工作，只是两边都没收录的冷门题无法作答。</p>
            <div class="btn-row"><a class="btn soft sm" href="#/settings">打开设置</a></div>
          </div>
        </div>

        <div class="card step">
          <div class="step-num">3</div>
          <div class="step-body">
            <h3>复制 OCS 题库配置</h3>
            <p>这段 JSON 已经按 OCS 的 <span class="inline-code">AnswererWrapper</span> 协议写好，直接整段复制。</p>
            <div class="callout" style="margin:12px 0">
              ${icons.info}
              <div><strong>不要再把言溪那条配置单独贴进 OCS。</strong>OCS 会并行请求配置里的所有题库；言溪和 AI 答案不一致时，可能随机选中其中一个。本服务已经按「本地 → 言溪 → DeepSeek」的顺序串起来，只保留下面这一条即可。</div>
            </div>
            <div class="code-box">
              <pre class="code" id="guide-code">${esc(ocsConfigText())}</pre>
              <button class="btn ghost sm copy-btn" id="copy-guide-config">${icons.copy}<span>复制</span></button>
            </div>
          </div>
        </div>

        <div class="card step">
          <div class="step-num">4</div>
          <div class="step-body">
            <h3>在 OCS 中粘贴并测试</h3>
            <p>打开 OCS 网课助手 → 「通用」→「全局设置」→「题库配置」，把上面的 JSON 粘贴进去并保存（<strong>替换掉原来的言溪配置</strong>）。随便答一道题，观察是否出现「本地题库（言溪 + DeepSeek）」的答案。</p>
            <p>之后每答一道题：<strong>本地题库 → 言溪题库 → DeepSeek</strong>。言溪命中后直接缓存到本地，下次连言溪也不用再查；两边都没有才调用 AI。刷得越多，命中率越高，费用越少。</p>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><h2>常见问题</h2><p>接入过程中最容易遇到的几个坑</p></div></div>
          <div class="card-body">
            <div class="faq">
              <div class="faq-item">
                <div class="faq-q">OCS 提示题库请求失败 / 跨域错误</div>
                <div class="faq-a">先确认服务在运行：浏览器打开 <span class="inline-code">${esc(origin)}/api/health</span> 能看到 JSON。油猴脚本版 OCS 需要在脚本头部加上 <span class="inline-code">@connect 127.0.0.1</span>，或安装官方「全域名通用版」；仍失败时把配置里的 <span class="inline-code">"type": "fetch"</span> 改成 <span class="inline-code">"GM_xmlhttpRequest"</span> 再试。Chrome 插件的 fetch 一般可直接访问 localhost。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">我原来的言溪题库还要单独配置吗？</div>
                <div class="faq-a">不用。言溪已经在「设置 → 言溪题库」里配置好，本服务会在本地未收录时自动查它。把 OCS 里原来的言溪配置删掉，只保留本服务这一条即可，否则 OCS 会并行请求两边，答案冲突时可能选错，而且每道题都会白调一次 AI。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">答案匹配不上选项</div>
                <div class="faq-a">本服务返回的是「选项文本」而不是字母，正常情况下 OCS 会做归一化匹配。如果某道题选项格式很特殊（图片选项、乱码标号），可以在「题库」页找到这道题手动改答案，下次就会用你改过的答案。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">准确率大概多少？</div>
                <div class="faq-a">deepseek-chat 在常见公共课题目上大致 80–90%，冷门专业课会低一些。追求准确率可切换 <span class="inline-code">deepseek-reasoner</span>，但每题会慢 5–20 秒、费用更高。答错的题手动改一次，之后同一题就是 100% 命中。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">会花很多钱吗？</div>
                <div class="faq-a">每题大约几百 token，DeepSeek 的价格很低；且第二次遇到同一题时直接命中本地题库，不再调用 AI。首页的「今日 Token」可以看到实时消耗。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">API Key 安全吗？</div>
                <div class="faq-a">Key 只写入本机 <span class="inline-code">data/config.json</span>，接口返回时始终打码，不会上传到任何地方。但请不要把 data 目录或截图发给别人。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">端口被占用 / 想换端口</div>
                <div class="faq-a">用 <span class="inline-code">python app.py --port 9000</span> 启动，然后把 OCS 配置里的 8787 全部替换成 9000。</div>
              </div>
              <div class="faq-item">
                <div class="faq-q">可以给局域网里的手机 / 平板用吗？</div>
                <div class="faq-a">可以，但要注意安全：服务默认只监听 127.0.0.1，改成 <span class="inline-code">--host 0.0.0.0</span> 后同网段设备能访问，且没有任何鉴权，不要暴露到公网。非 localhost 的 http 地址在 https 页面里会被浏览器拦截，需要反向代理加 HTTPS。</div>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><div><h2>实现说明</h2><p>为什么没有直接用现成的开源项目</p></div></div>
          <div class="card-body">
            <div class="hint" style="line-height:1.9">
              项目参考了 OCS 官方题库协议与社区项目（ocsjs-ai-answer-service、OcsAiAnswerer）的思路，但那些项目大多只有单一 AI 兜底、缺少本地题库与管理界面。本项目的差异：<br>
              · 本地 SQLite 题库优先，AI 答案自动沉淀，重复题目零成本；<br>
              · 答案统一转成「选项文本」，对选项打乱、标点差异更鲁棒；<br>
              · 低置信度拒答，避免错题污染题库；<br>
              · 内置管理后台：题库检索 / 编辑 / 导入导出 / 连接测试 / 用量统计；<br>
              · 纯 Python 标准库，无需 pip 安装任何依赖。
            </div>
          </div>
        </div>
      </div>
    `;

    $('#copy-guide-config').addEventListener('click', (event) => copyText(ocsConfigText(), event.currentTarget));
  }

  // ------------------------------------------------------------------------
  // 路由 & 初始化
  // ------------------------------------------------------------------------
  const VIEWS = {
    overview: { title: '概览', sub: '本地题库优先，言溪次之，最后交给 DeepSeek' },
    bank: { title: '题库', sub: '查看、修正、导入和导出你的题目' },
    settings: { title: '设置', sub: '连接 DeepSeek 与言溪，调整答题策略' },
    guide: { title: '使用指南', sub: '四步接入 OCS 网课助手' },
  };

  async function loadConfig() {
    const res = await api('/api/config');
    state.config = res.data;
  }

  async function loadStats() {
    try {
      const res = await api('/api/stats');
      state.stats = res.data;
      updateChrome();
      if (state.view === 'overview' && $('#view').children.length) renderOverview();
    } catch (err) {
      console.warn(err);
    }
  }

  function route() {
    const hash = (location.hash.match(/^#\/([\w-]+)/) || [])[1] || 'overview';
    const view = VIEWS[hash] ? hash : 'overview';
    state.view = view;
    $$('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === view));
    $('#page-title').textContent = VIEWS[view].title;
    $('#page-sub').textContent = VIEWS[view].sub;
    $('#view').style.animation = 'none';
    void $('#view').offsetWidth;
    $('#view').style.animation = '';

    if (view === 'overview') {
      renderOverview();
      loadStats();
    } else if (view === 'bank') {
      renderBank();
    } else if (view === 'settings') {
      renderSettings();
    } else {
      renderGuide();
    }
  }

  async function init() {
    $('#btn-copy-config').addEventListener('click', (event) => copyText(ocsConfigText(), event.currentTarget));

    try {
      await loadConfig();
      await loadStats();
    } catch (err) {
      toast(err.message, 'err');
      $('#side-dot').className = 'dot dot-err';
      $('#side-status').textContent = '服务连接失败';
    }
    updateChrome();
    route();
    window.addEventListener('hashchange', route);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
