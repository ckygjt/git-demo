import { useEffect, useRef, useState } from "react";

const VERDICT = {
  credible: { label: "可信", cls: "ok" },
  doubtful_insufficient: { label: "存疑 · 信息不足", cls: "warn" },
  doubtful_suspicious: { label: "存疑 · 有疑点", cls: "warn2" },
  high_risk: { label: "高风险", cls: "bad" },
  health_referral: { label: "健康类 · 转专人", cls: "info" },
};
const SRC = {
  S0: "图像质量", S1: "像素取证", S2: "图像内容", S3: "元数据", S4: "诉求", S5: "聊天", S6: "订单",
  S7: "物流", S8: "账号", S9: "跨工单", S10: "产品知识", S11: "批次", S12: "补充证据",
};
const STRENGTH = { strong: "强", medium: "中", weak: "弱" };
const TOOL_MODE = {
  S1: { model: "取证模型", mock: "回放" },
  S2: { llm: "VLM", mock: "回放" },
};
const SET_CN = { real_damaged: "真实破损", real_intact: "真实完好", fake_damaged: "AI 假破损" };
const VARIANT_CN = {
  raw: "原图(PNG)", resize768: "仅缩放 768", jpeg95: "JPEG q95", jpeg85: "JPEG q85", jpeg75: "JPEG q75", "resize768+jpeg85": "缩放 768 + JPEG q85",
};

const api = (p, o) => fetch(p, o).then((r) => r.json());

function Badge({ verdict }) {
  const v = VERDICT[verdict];
  return v ? <span className={`badge ${v.cls}`}>{v.label}</span> : null;
}

function Box({ img, bboxes }) {
  return (
    <div className="imgbox">
      <img src={`/api/images/${img}`} alt={img} onError={(e) => (e.target.style.opacity = 0.2)} />
      {bboxes.map((b, i) => (
        <div key={i} className="bbox" style={{ left: `${b[0] * 100}%`, top: `${b[1] * 100}%`, width: `${(b[2] - b[0]) * 100}%`, height: `${(b[3] - b[1]) * 100}%` }} />
      ))}
    </div>
  );
}

function Evidence({ e, onHover }) {
  return (
    <li className={`ev ${e.polarity}`} onMouseEnter={() => onHover?.(e)} onMouseLeave={() => onHover?.(null)}>
      <div className="ev-head">
        <span className="tag">{SRC[e.source] || e.source}</span>
        <span className={`dir ${e.polarity}`}>{e.polarity === "up" ? "增信" : e.polarity === "down" ? "降信" : "备注"}</span>
        <span className="str">{STRENGTH[e.strength]}</span>
        <span className="rule">{e.rule}</span>
      </div>
      <div>{e.summary}</div>
    </li>
  );
}

function Panel({ ticketId, onHover }) {
  const [steps, setSteps] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const es = useRef(null);

  useEffect(() => {
    es.current?.close();
    setSteps([]);
    setResult(null);
    setRunning(false);
    onHover(null);
  }, [ticketId]);

  const run = () => {
    es.current?.close();
    setSteps([]);
    setResult(null);
    setRunning(true);
    const s = new EventSource(`/api/tickets/${ticketId}/stream`);
    es.current = s;
    s.addEventListener("event", (m) => {
      const d = JSON.parse(m.data);
      setSteps((prev) => [...prev.filter((x) => !(x.step === d.step && x.status === "running")), d]);
    });
    s.addEventListener("result", (m) => {
      setResult(JSON.parse(m.data));
      setRunning(false);
      s.close();
    });
    s.onerror = () => {
      setRunning(false);
      s.close();
    };
  };

  return (
    <aside className="panel">
      <div className="panel-head">
        <h3>Agent 核验</h3>
        <button className="btn" onClick={run} disabled={running}>{running ? "核验中…" : result ? "重新核验" : "开始核验"}</button>
      </div>

      {steps.length > 0 && (
        <ol className="steps">
          {steps.filter((s) => !s.step.startsWith("tool_")).map((s) => (
            <li key={s.step} className={s.status}>
              <span className="dot" />
              <div>
                <b>{s.title}</b>
                {s.elapsed_ms > 0 && <span className="ms">{s.elapsed_ms}ms</span>}
                <div className="sub">{s.detail}</div>
              </div>
            </li>
          ))}
        </ol>
      )}

      {result && (
        <div className="result">
          <div className="verdict-row">
            <Badge verdict={result.verdict} />
            <span className="conf">置信度 {Math.round(result.confidence * 100)}%</span>
            <span className="rule">{result.fired_rule}</span>
          </div>
          <p className="reason">{result.reason}</p>
          <div className="action">建议处置：<b>{result.action_cn}</b></div>

          {result.supplement_requests.length > 0 && (
            <div className="supp"><b>建议向买家索取：</b>
              <ul>{result.supplement_requests.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </div>
          )}

          <h4>证据链</h4>
          <ul className="evs">{result.evidence.map((e) => <Evidence key={e.id} e={e} onHover={onHover} />)}</ul>
          {result.flags.length > 0 && (
            <>
              <h4>备注 / 弱信号（不影响结论）</h4>
              <ul className="evs">{result.flags.map((e) => <Evidence key={e.id} e={e} />)}</ul>
            </>
          )}

          <h4>建议话术</h4>
          <div className="script">{result.script}</div>
          <button className="btn ghost" onClick={() => navigator.clipboard.writeText(result.script)}>复制话术</button>
          <div className="meta">
            模式 {result.mode} · 耗时 {result.elapsed_ms}ms
            {Object.keys(TOOL_MODE).map((k) => {
              const t = result.tools?.find((x) => x.tool === k);
              return t ? <span key={k} className={`src ${t.mode}`}> · {SRC[k]}：{TOOL_MODE[k][t.mode] || t.mode}</span> : null;
            })}
          </div>
        </div>
      )}
    </aside>
  );
}

const fmt = (v, d = 2) => (v === null || v === undefined ? "-" : Number(v).toFixed(d));

function EvalPage() {
  const [d, setD] = useState(null);
  useEffect(() => { api("/api/eval").then(setD); }, []);
  if (!d) return <div className="evalpage">加载中…</div>;
  if (!d.available) return <div className="evalpage">尚无评测结果，请先运行 scripts/ 下的评测脚本。</div>;
  const { vlm, aigc, tamper, limitations } = d;
  return (
    <div className="evalpage">
      <h2>离线评测基线</h2>
      <div className="warnbox">
        <b>局限与结论</b>
        <ul>{limitations.map((x, i) => <li key={i}>{x}</li>)}</ul>
      </div>

      {vlm && (
        <>
          <h3>VLM 图像描述（零样本）</h3>
          <table>
            <thead><tr><th>集合</th><th>样本</th><th>调用成功</th><th>报出破损</th><th>判为 AI</th><th>ai_prob 均值</th></tr></thead>
            <tbody>{vlm.map((r) => (
              <tr key={r.set}><td>{SET_CN[r.set] || r.set}</td><td>{r.n}</td><td>{r.vision_ok}</td><td>{r.reported_damage}/{r.vision_ok}</td><td>{r.ai_flagged}</td><td>{fmt(r.ai_prob_mean)}</td></tr>
            ))}</tbody>
          </table>
          <p className="note">VLM 能描述破损，但无法区分 AI 假图与真图，所以需要独立取证与交叉验证。</p>
        </>
      )}

      {aigc && (
        <>
          <h3>S1a 整图 AIGC 检测（Community Forensics）</h3>
          <table>
            <thead><tr><th>口径</th><th>AUC</th><th>真图最高分</th><th>假图均值</th><th>假图检出@0.5</th><th>真图误报@0.5</th></tr></thead>
            <tbody>{[["raw", "原图"], ["norm", "缩放 768 + JPEG q85"]].map(([m, label]) => {
              const r = aigc.modes[m];
              return <tr key={m}><td>{label}</td><td>{fmt(r.auc, 3)}</td><td>{fmt(r.real_max, 3)}</td><td>{fmt(r.fake_mean, 3)}</td><td>{r["fake_detected@0.5"]}/{aigc.n_fake}</td><td>{r["real_false_pos@0.5"]}/{aigc.n_real}</td></tr>;
            })}</tbody>
          </table>
          <p className="note">原图口径的高 AUC 可能含 PNG/JPEG 格式泄漏；以压缩口径为准。</p>
        </>
      )}

      {tamper && (
        <>
          <h3>S1b 局部篡改检测（TruFor）</h3>
          <table>
            <thead><tr><th>输入处理</th><th>AUC（完好底图 vs 局部拼接）</th><th>拼接均值</th><th>拼接≥0.9</th><th>底图≥0.9</th></tr></thead>
            <tbody>{tamper.ablation.map((r) => (
              <tr key={r.variant} className={r.auc < 0.6 ? "bad" : ""}><td>{VARIANT_CN[r.variant] || r.variant}</td><td>{fmt(r.auc, 3)}</td><td>{fmt(r.pos_mean)}</td><td>{r["pos_ge_0.9"]}/{r.n}</td><td>{r["neg_ge_0.9"]}/{r.n}</td></tr>
            ))}</tbody>
          </table>
          <p className="note">
            {tamper.real_false_pos.raw.n} 张原生真图中，TruFor 分数 ≥0.55 有 {tamper.real_false_pos.raw[">=0.55"]} 张、≥0.80 有 {tamper.real_false_pos.raw[">=0.8"]} 张、≥0.90 有 {tamper.real_false_pos.raw[">=0.9"]} 张，
            因此模型分数低于 {d.tamper_model_min} 一律记 0。整图重绘类假图 TruFor 无效（AUC {fmt(tamper.auc.raw.base_vs_full, 2)}）。
          </p>
        </>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("tickets");
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [hover, setHover] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api("/api/tickets").then((l) => { setList(l); if (l[0]) setSel(l[0].ticket_id); });
    api("/api/health").then(setHealth);
  }, []);
  useEffect(() => { if (sel) api(`/api/tickets/${sel}`).then(setDetail); }, [sel]);

  const t = detail?.ticket;
  const boxes = (name) => (hover?.locator?.image === name && hover.locator.bbox ? [hover.locator.bbox] : []);

  return (
    <div className="app">
      <header>
        <div className="logo">TruthGuard</div>
        <div className="sub">售后客诉证据鉴真 Agent</div>
        <div className="tabs">
          <button className={tab === "tickets" ? "on" : ""} onClick={() => setTab("tickets")}>工单核验</button>
          <button className={tab === "eval" ? "on" : ""} onClick={() => setTab("eval")}>评估</button>
        </div>
        <div className="spacer" />
        {health && <span className={`mode ${health.mode}`}>{health.mode === "mock" ? "Mock 模式" : `模型：${health.providers.join(",")}`}</span>}
      </header>
      {tab === "eval" ? <EvalPage /> : (
      <main>
        <nav className="list">
          <h3>待处理仅退款工单</h3>
          {list.map((x) => (
            <div key={x.ticket_id} className={`row ${sel === x.ticket_id ? "sel" : ""}`} onClick={() => setSel(x.ticket_id)}>
              <div className="row-top"><b>{x.ticket_id}</b><span className="reason">{x.reason}</span></div>
              <div className="case">{x.case}</div>
            </div>
          ))}
        </nav>

        <section className="detail">
          {t && (
            <>
              <h2>{t.ticket_id} · {t.reason}</h2>
              <p className="desc">“{t.description}”</p>
              <div className="imgs">{t.images.map((n) => <Box key={n} img={n} bboxes={boxes(n)} />)}</div>
              <div className="cards">
                <div className="card"><h4>订单</h4>
                  {detail.order && <>
                    <div>{detail.product?.name} · {detail.order.spec}</div>
                    <div>批次 {detail.order.batch_no} · {detail.order.warehouse}</div>
                    <div>金额 ¥{detail.order.amount}</div></>}
                </div>
                <div className="card"><h4>物流</h4>
                  {detail.logistics?.events.map((e, i) => <div key={i}>{e.time.slice(5, 16)} {e.desc}</div>)}
                </div>
                <div className="card"><h4>账号</h4>
                  {detail.account && <>
                    <div>VIP{detail.account.vip_level} · 近90天订单 {detail.account.orders_90d}</div>
                    <div>近90天售后 {detail.account.refunds_90d}（仅退款 {detail.account.refund_only_90d}）</div></>}
                </div>
                <div className="card wide"><h4>聊天记录</h4>
                  {detail.chat?.messages.map((m, i) => <div key={i} className={`msg ${m.role}`}>{m.role === "buyer" ? "买家" : "客服"}：{m.text}</div>)}
                </div>
              </div>
            </>
          )}
        </section>

        {sel && <Panel ticketId={sel} onHover={setHover} />}
      </main>
      )}
    </div>
  );
}
