import { useEffect, useState } from "react";
import { api } from "../api/client";
type O = { id: number; ticket_code: string; garment_name: string; length_cm: number; status: string; is_express: boolean; due_at: string };

export default function OrdersPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  // 录入表单
  const [ticket, setTicket] = useState("");
  const [garment, setGarment] = useState("");
  const [len, setLen] = useState("30");
  const [express, setExpress] = useState(false);

  const reload = () => api<O[]>("/orders").then(setRows);
  useEffect(() => { reload(); }, []);
  const flash = (m: string) => { setMsg(m); setErr(""); };
  const fail = (e: unknown) => setErr(e instanceof Error ? e.message : String(e));

  async function hang(id: number) {
    setMsg(""); setErr("");
    try {
      const o = await api<O>("/hang", { method: "POST", body: JSON.stringify({ order_id: id }) });
      flash(`${o.ticket_code} 已上杆${o.is_express ? "（加急优先专区）" : ""}`);
      reload();
    } catch (e) { fail(e); }
  }

  async function toggleExpress(o: O) {
    setMsg(""); setErr("");
    try {
      const u = await api<O>(`/orders/${o.id}/express`, { method: "PATCH", body: JSON.stringify({ is_express: !o.is_express }) });
      flash(`${u.ticket_code} ${u.is_express ? "已标记快递加急" : "已取消加急"}`);
      reload();
    } catch (e) { fail(e); }
  }

  async function intake() {
    setMsg(""); setErr("");
    const length_cm = Number(len);
    if (!ticket.trim() || !garment.trim() || !(length_cm > 0)) { setErr("票号、衣物与正数衣长必填"); return; }
    try {
      const o = await api<O>("/orders", { method: "POST", body: JSON.stringify({ ticket_code: ticket.trim(), garment_name: garment.trim(), length_cm, is_express: express }) });
      flash(`已录入 ${o.ticket_code}${o.is_express ? "（快递加急）" : ""}`);
      setTicket(""); setGarment(""); setLen("30"); setExpress(false);
      reload();
    } catch (e) { fail(e); }
  }

  return (<>
    <h2>工单</h2>
    <div className="toolbar">
      <input value={ticket} onChange={e => setTicket(e.target.value)} placeholder="票号，如 HR-2101" className="mono" />
      <input value={garment} onChange={e => setGarment(e.target.value)} placeholder="衣物名称" />
      <input value={len} onChange={e => setLen(e.target.value)} placeholder="衣长 cm" className="mono zone-input" />
      <label className="check-pill">
        <input type="checkbox" checked={express} onChange={e => setExpress(e.target.checked)} />
        快递加急
      </label>
      <button onClick={intake}>录入工单</button>
    </div>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>票号</th><th>衣物</th><th>衣长</th><th>类型</th><th>状态</th><th>到期</th><th></th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}>
      <td className="mono">{o.ticket_code}</td><td>{o.garment_name}</td><td className="mono">{o.length_cm}cm</td>
      <td>{o.is_express ? <span className="tag-express">快递加急</span> : <span className="tag-normal">普通</span>}
        {(o.status === "ready" || o.status === "overdue") && <button className="btn-mini" onClick={() => toggleExpress(o)}>{o.is_express ? "取消加急" : "标加急"}</button>}
      </td>
      <td>{o.status}</td>
      <td className="mono">{new Date(o.due_at).toLocaleString()}</td>
      <td>{(o.status === "ready" || o.status === "overdue") && <button onClick={() => hang(o.id)}>上杆</button>}</td>
    </tr>)}</tbody></table>
  </>);
}
