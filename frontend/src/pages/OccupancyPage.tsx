import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rail = { id: number; label: string; length_cm: number };
type Seg = { ticket_code: string; garment_name: string; is_express: boolean; start_cm: number; end_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; express_start_cm: number | null; express_end_cm: number | null; segments: Seg[] };

export default function OccupancyPage() {
  const [rails, setRails] = useState<Rail[]>([]);
  const [maps, setMaps] = useState<Occ[]>([]);
  useEffect(() => {
    api<Rail[]>("/rails").then(async rs => {
      setRails(rs);
      const all = await Promise.all(rs.map(r => api<Occ>(`/occupancy/${r.id}`)));
      setMaps(all);
    });
  }, []);
  return (<>
    <h2>占位图（横向尺线）</h2>
    {maps.map(m => {
      const zs = m.express_start_cm, ze = m.express_end_cm;
      const hasZone = zs != null && ze != null;
      return (
        <div className="ruler-wrap" key={m.rail_id}>
          <div className="ruler-label">
            <span>{m.label}
              {hasZone && <span className="zone-legend">▌快递专区 [{zs}, {ze}) cm · 仅加急</span>}
            </span>
            <span className="mono">0 — {m.length_cm} cm</span>
          </div>
          <div className="ruler">
            {hasZone && (
              <div className="zone-band"
                style={{ left: `${((zs as number) / m.length_cm) * 100}%`, width: `${(((ze as number) - (zs as number)) / m.length_cm) * 100}%` }}
                title={`快递专区 [${zs}, ${ze}) cm`} />
            )}
            {m.segments.map((s, i) => (
              <div key={i} className={`seg${s.is_express ? " seg--express" : ""}`}
                style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
                title={`${s.ticket_code}${s.is_express ? "（快递加急）" : ""} ${s.start_cm}-${s.end_cm}cm`}>
                {s.garment_name}
              </div>
            ))}
          </div>
        </div>
      );
    })}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
