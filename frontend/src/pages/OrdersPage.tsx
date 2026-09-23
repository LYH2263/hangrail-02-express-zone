import { useEffect, useState } from "react";
import { api } from "../api/client";
type O = { id: number; ticket_code: string; garment_name: string; length_cm: number; is_express: boolean; status: string; due_at: string };
export default function OrdersPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const reload = () => api<O[]>("/orders").then(setRows);
  useEffect(() => { reload(); }, []);
  async function hang(id: number) {
    setMsg(""); setErr("");
    try {
      const o = await api<O>("/hang", { method: "POST", body: JSON.stringify({ order_id: id }) });
      setMsg(`${o.ticket_code} 已上杆`);
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  async function toggleExpress(o: O) {
    setMsg(""); setErr(""); setBusy(o.id);
    try {
      await api<O>(`/orders/${o.id}/express`, { method: "POST", body: JSON.stringify({ is_express: !o.is_express }) });
      reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(null); }
  }
  return (<>
    <h2>工单</h2>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>票号</th><th>衣物</th><th>衣长</th><th>快递加急</th><th>状态</th><th>到期</th><th></th></tr></thead>
    <tbody>{rows.map(o => <tr key={o.id}>
      <td className="mono">{o.ticket_code}</td>
      <td>{o.garment_name}</td>
      <td className="mono">{o.length_cm}cm</td>
      <td>{o.is_express
        ? <span className="express-badge express-badge--on" title="仅可占用快递专区，专区满再扫普通空隙">⚡ 加急</span>
        : <span className="express-badge">普通</span>}
        {o.status !== "picked" &&
          <button className="btn-ghost btn-xs" disabled={busy === o.id} onClick={() => toggleExpress(o)}>
            {o.is_express ? "撤加急" : "标加急"}
          </button>}
      </td>
      <td>{o.status}</td>
      <td className="mono">{new Date(o.due_at).toLocaleString()}</td>
      <td>{(o.status === "ready" || o.status === "overdue") && <button onClick={() => hang(o.id)}>上杆</button>}</td>
    </tr>)}</tbody></table>
  </>);
}
