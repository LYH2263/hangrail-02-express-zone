import { useEffect, useState } from "react";
import { api } from "../api/client";
type Rail = { id: number; label: string; length_cm: number };
type Occ = { rail_id: number; label: string; length_cm: number; express_zone_start_cm: number | null; express_zone_end_cm: number | null; segments: { ticket_code: string; garment_name: string; is_express: boolean; start_cm: number; end_cm: number }[] };

function hasZone(m: Occ) {
  return m.express_zone_start_cm != null && m.express_zone_end_cm != null;
}

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
    <div className="zone-legend">
      <span className="zone-legend-swatch zone-band" /> 快递专区（仅加急工单）
      <span className="zone-legend-swatch seg-express-swatch" /> 加急工单占位
    </div>
    {maps.map(m => (
      <div className="ruler-wrap" key={m.rail_id}>
        <div className="ruler-label">
          <span>{m.label}</span>
          <span className="mono">0 — {m.length_cm} cm
            {hasZone(m) && <em className="zone-range"> · 专区 [{m.express_zone_start_cm}, {m.express_zone_end_cm})</em>}
          </span>
        </div>
        <div className="ruler">
          {hasZone(m) && (
            <div
              className="zone-band"
              style={{
                left: `${((m.express_zone_start_cm as number) / m.length_cm) * 100}%`,
                width: `${(((m.express_zone_end_cm as number) - (m.express_zone_start_cm as number)) / m.length_cm) * 100}%`,
              }}
              title={`快递专区 [${m.express_zone_start_cm}, ${m.express_zone_end_cm})cm，普通工单跳过`}
            >
              <span className="zone-band-label">快递专区</span>
            </div>
          )}
          {m.segments.map((s, i) => (
            <div
              key={i}
              className={s.is_express ? "seg seg--express" : "seg"}
              style={{ left: `${(s.start_cm / m.length_cm) * 100}%`, width: `${((s.end_cm - s.start_cm) / m.length_cm) * 100}%` }}
              title={`${s.ticket_code}${s.is_express ? " ⚡加急" : ""} ${s.start_cm}-${s.end_cm}cm`}
            >
              {s.is_express ? "⚡" : ""}{s.garment_name}
            </div>
          ))}
        </div>
      </div>
    ))}
    {!rails.length && <p>暂无挂杆</p>}
  </>);
}
