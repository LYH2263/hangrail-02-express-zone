import { useEffect, useState } from "react";
import { api } from "../api/client";
type R = { id: number; store_id: number; label: string; length_cm: number; express_start_cm: number | null; express_end_cm: number | null };

function ZoneEditor({ rail, onSaved }: { rail: R; onSaved: () => void }) {
  const hasZone = rail.express_start_cm != null && rail.express_end_cm != null;
  const [start, setStart] = useState(String(hasZone ? rail.express_start_cm : ""));
  const [end, setEnd] = useState(String(hasZone ? rail.express_end_cm : ""));
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  async function save() {
    setMsg(""); setErr("");
    const s = num(start), e = num(end);
    if (s === null || e === null) { setErr("请填写专区起止厘米"); return; }
    try {
      await api(`/rails/${rail.id}/zone`, { method: "PUT", body: JSON.stringify({ express_start_cm: s, express_end_cm: e }) });
      setMsg("快递专区已保存"); onSaved();
    } catch (ex) { setErr(ex instanceof Error ? ex.message : String(ex)); }
  }
  async function clear() {
    setMsg(""); setErr("");
    try {
      await api(`/rails/${rail.id}/zone`, { method: "PUT", body: JSON.stringify({ express_start_cm: null, express_end_cm: null }) });
      setStart(""); setEnd(""); setMsg("专区已清除，全杆可挂"); onSaved();
    } catch (ex) { setErr(ex instanceof Error ? ex.message : String(ex)); }
  }
  return (
    <div className="zone-editor">
      <span className="zone-pill">{hasZone ? `专区 [${rail.express_start_cm}, ${rail.express_end_cm}) cm` : "全杆可挂"}</span>
      <input aria-label="专区起点" value={start} onChange={ev => setStart(ev.target.value)} placeholder="起 cm" className="zone-input mono" />
      <span className="zone-sep">—</span>
      <input aria-label="专区终点" value={end} onChange={ev => setEnd(ev.target.value)} placeholder="止 cm（不含）" className="zone-input mono" />
      <button onClick={save}>保存专区</button>
      {hasZone && <button className="btn-ghost" onClick={clear}>清除</button>}
      {msg && <span className="ok">{msg}</span>}
      {err && <span className="err">{err}</span>}
    </div>
  );
}

export default function RailsPage() {
  const [rows, setRows] = useState<R[]>([]);
  const reload = () => api<R[]>("/rails").then(setRows);
  useEffect(() => { reload(); }, []);
  return (<>
    <h2>挂杆 · 快递专区</h2>
    <p className="hint">每根挂杆可登记一段半开区间 [起, 止) 作为快递加急专区；仅加急工单可占用，普通工单 First-Fit 自动跳过专区空隙。</p>
    <table className="table"><thead><tr><th>标签</th><th>门店</th><th>长度 cm</th><th>快递专区（半开区间，cm）</th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.id}>
      <td>{r.label}</td><td className="mono">{r.store_id}</td><td className="mono">{r.length_cm}</td>
      <td><ZoneEditor key={`${r.id}-${r.express_start_cm}-${r.express_end_cm}`} rail={r} onSaved={reload} /></td>
    </tr>)}</tbody></table>
  </>);
}
