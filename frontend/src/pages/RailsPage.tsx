import { useEffect, useState } from "react";
import { api } from "../api/client";
type R = { id: number; store_id: number; label: string; length_cm: number; express_zone_start_cm: number | null; express_zone_end_cm: number | null };

type Draft = { start: string; end: string };
type Errors = Record<number, string>;

export default function RailsPage() {
  const [rows, setRows] = useState<R[]>([]);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [errs, setErrs] = useState<Errors>({});
  const [ok, setOk] = useState<Record<number, boolean>>({});

  function draftFor(r: R): Draft {
    return drafts[r.id] ?? {
      start: r.express_zone_start_cm?.toString() ?? "",
      end: r.express_zone_end_cm?.toString() ?? "",
    };
  }
  function setDraft(id: number, patch: Partial<Draft>) {
    setDrafts((d) => ({ ...d, [id]: { ...(d[id] ?? { start: "", end: "" }), ...patch } }));
    setErrs((e) => ({ ...e, [id]: "" }));
    setOk((o) => ({ ...o, [id]: false }));
  }
  async function reload() {
    const rs = await api<R[]>("/rails");
    setRows(rs);
  }
  useEffect(() => { reload(); }, []);

  async function save(r: R) {
    const d = draftFor(r);
    setErrs((e) => ({ ...e, [r.id]: "" }));
    setOk((o) => ({ ...o, [r.id]: false }));
    try {
      const start = parseFloat(d.start);
      const end = parseFloat(d.end);
      if (!Number.isFinite(start) || !Number.isFinite(end)) {
        setErrs((e) => ({ ...e, [r.id]: "请填写专区起止厘米" }));
        return;
      }
      await api<R>(`/rails/${r.id}/express-zone`, {
        method: "PUT",
        body: JSON.stringify({ start_cm: start, end_cm: end }),
      });
      setDrafts((d2) => { const c = { ...d2 }; delete c[r.id]; return c; });
      setOk((o) => ({ ...o, [r.id]: true }));
      reload();
    } catch (e) {
      setErrs((e2) => ({ ...e2, [r.id]: e instanceof Error ? e.message : String(e) }));
    }
  }

  async function clearZone(r: R) {
    setErrs((e) => ({ ...e, [r.id]: "" }));
    try {
      await api<R>(`/rails/${r.id}/express-zone`, {
        method: "PUT",
        body: JSON.stringify({ start_cm: null, end_cm: null }),
      });
      setDrafts((d2) => { const c = { ...d2 }; delete c[r.id]; return c; });
      reload();
    } catch (e) {
      setErrs((e2) => ({ ...e2, [r.id]: e instanceof Error ? e.message : String(e) }));
    }
  }

  return (<>
    <h2>挂杆 · 快递专区</h2>
    <p className="hint">每根挂杆可登记一段半开区间 [起, 止)（厘米）作为快递专区，仅快递加急工单可占用；普通工单上杆自动跳过专区空隙。</p>
    <table className="table">
      <thead><tr><th>标签</th><th>门店</th><th>长度 cm</th><th>专区起 cm</th><th>专区止 cm</th><th>操作</th></tr></thead>
      <tbody>{rows.map(r => {
        const d = draftFor(r);
        return (
          <tr key={r.id}>
            <td>{r.label}</td>
            <td>{r.store_id}</td>
            <td className="mono">{r.length_cm}</td>
            <td><input className="zone-input mono" type="number" min={0} max={r.length_cm} value={d.start}
              onChange={(ev) => setDraft(r.id, { start: ev.target.value })} aria-label="专区起" /></td>
            <td><input className="zone-input mono" type="number" min={0} max={r.length_cm} value={d.end}
              onChange={(ev) => setDraft(r.id, { end: ev.target.value })} aria-label="专区止" /></td>
            <td className="zone-actions">
              <button onClick={() => save(r)}>保存专区</button>
              {(r.express_zone_start_cm != null || d.start !== "") && <button className="btn-ghost" onClick={() => clearZone(r)}>清除</button>}
              {errs[r.id] && <span className="err zone-msg">{errs[r.id]}</span>}
              {ok[r.id] && <span className="ok zone-msg">已保存</span>}
            </td>
          </tr>
        );
      })}</tbody>
    </table>
  </>);
}
