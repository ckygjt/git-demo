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
          <div className="meta">模式 {result.mode} · 耗时 {result.elapsed_ms}ms</div>
        </div>
      )}
    </aside>
  );
}

export default function App() {
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
        <div className="spacer" />
        {health && <span className={`mode ${health.mode}`}>{health.mode === "mock" ? "Mock 模式" : `模型：${health.providers.join(",")}`}</span>}
      </header>
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
    </div>
  );
}
