import { useState, useEffect, useRef, useCallback } from 'react';
import { gardensAPI, gardenAdminAPI } from '../api';
import { toast } from './dialog/dialogService';

// Non-plot map elements ("dead zones") an organizer can place to match reality.
const FEATURE_TYPES = [
  { key: 'path', label: 'Path', icon: 'bi-signpost-split', color: '#d8cba3' },
  { key: 'shed', label: 'Shed', icon: 'bi-house', color: '#8b5e3c' },
  { key: 'table', label: 'Table', icon: 'bi-table', color: '#a9744f' },
  { key: 'water', label: 'Water', icon: 'bi-droplet', color: '#6bb7e6' },
  { key: 'compost', label: 'Compost', icon: 'bi-recycle', color: '#6b8e23' },
  { key: 'landscaping', label: 'Landscaping', icon: 'bi-tree', color: '#4a9b5e' },
  { key: 'public', label: 'Public area', icon: 'bi-people', color: '#9aa0a6' },
  { key: 'other', label: 'Other', icon: 'bi-square', color: '#7a7d85' },
];
const FEATURE_COLOR = Object.fromEntries(FEATURE_TYPES.map(f => [f.key, f.color]));
const FEATURE_LABEL = Object.fromEntries(FEATURE_TYPES.map(f => [f.key, f.label]));
const STATUS_COLOR = {
  available: '#7fd4ab', assigned: '#3f7ddb', reserved: '#d99a2b', maintenance: '#b0b4ba',
};
const CELL_SIZES = [22, 30, 40, 52];

export default function GardenLayoutEditor({ gardenId, plots, gridRows, gridCols, onSaved, onDirtyChange, isPro = true }) {
  const [rows, setRows] = useState(Math.max(gridRows || 8, 8));
  const [cols, setCols] = useState(Math.max(gridCols || 8, 8));
  const [cell, setCell] = useState(30);
  const [placed, setPlaced] = useState([]);   // {id, plot_number, status, row, col, w, h, rounded, isNew}
  const [features, setFeatures] = useState([]); // {key(tmp), feature_type, label, row, col, w, h, color, rounded}
  const [tool, setTool] = useState('plot');    // 'plot' | <feature_type> | 'select' | 'erase'
  const [rounded, setRounded] = useState(false);
  const [drag, setDrag] = useState(null);      // {r0,c0,r1,c1}
  const [sel, setSel] = useState(null);        // {kind:'plot'|'feature', key}
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const tmp = useRef(-1);
  const boardRef = useRef(null);

  // Report unsaved changes upward so the dashboard can warn before a tab
  // switch or page close silently discards a drawn layout.
  useEffect(() => { onDirtyChange && onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => { onDirtyChange && onDirtyChange(false); }, [onDirtyChange]);

  useEffect(() => {
    setPlaced((plots || [])
      .filter(p => p.grid_row != null && p.grid_col != null)
      .map(p => ({
        id: p.id, plot_number: p.plot_number, status: p.status || 'available',
        row: p.grid_row, col: p.grid_col, w: p.grid_width || 1, h: p.grid_height || 1,
        rounded: !!p.rounded, isNew: false,
      })));
  }, [plots]);

  useEffect(() => {
    gardensAPI.layoutFeatures(gardenId).then(r => {
      setFeatures((r.data || []).map(f => ({
        key: tmp.current--, feature_type: f.feature_type, label: f.label || '',
        row: f.grid_row, col: f.grid_col, w: f.grid_width || 1, h: f.grid_height || 1,
        color: f.color || FEATURE_COLOR[f.feature_type] || '#7a7d85', rounded: !!f.rounded,
      })));
    }).catch(() => {});
  }, [gardenId]);

  const ownerAt = useCallback((r, c) => {
    for (const p of placed)
      if (r >= p.row && r < p.row + p.h && c >= p.col && c < p.col + p.w) return { kind: 'plot', ref: p };
    for (const f of features)
      if (r >= f.row && r < f.row + f.h && c >= f.col && c < f.col + f.w) return { kind: 'feature', ref: f };
    return null;
  }, [placed, features]);

  const cellFromEvent = (e) => {
    const b = boardRef.current.getBoundingClientRect();
    let c = Math.floor((e.clientX - b.left) / cell);
    let r = Math.floor((e.clientY - b.top) / cell);
    r = Math.max(0, Math.min(r, rows - 1));
    c = Math.max(0, Math.min(c, cols - 1));
    return { r, c };
  };

  const rectOf = (d) => ({
    row: Math.min(d.r0, d.r1), col: Math.min(d.c0, d.c1),
    h: Math.abs(d.r1 - d.r0) + 1, w: Math.abs(d.c1 - d.c0) + 1,
  });

  const areaFree = (rect) => {
    for (let r = rect.row; r < rect.row + rect.h; r++)
      for (let c = rect.col; c < rect.col + rect.w; c++)
        if (ownerAt(r, c)) return false;
    return true;
  };

  const nextPlotNumber = () => {
    const nums = placed.map(p => parseInt(p.plot_number, 10)).filter(n => !isNaN(n));
    return String((nums.length ? Math.max(...nums) : 0) + 1);
  };

  const onDown = (e) => {
    const { r, c } = cellFromEvent(e);
    if (tool === 'select') {
      const o = ownerAt(r, c);
      setSel(o ? { kind: o.kind, key: o.kind === 'plot' ? o.ref.id : o.ref.key } : null);
      return;
    }
    if (tool === 'erase') {
      const o = ownerAt(r, c);
      if (o) remove(o.ref, o.kind);
      return;
    }
    boardRef.current.setPointerCapture(e.pointerId);
    setDrag({ r0: r, c0: c, r1: r, c1: c });
  };
  const onMove = (e) => { if (drag) { const { r, c } = cellFromEvent(e); setDrag(d => ({ ...d, r1: r, c1: c })); } };
  const onUp = () => {
    if (!drag) return;
    const rect = rectOf(drag);
    setDrag(null);
    if (!areaFree(rect)) { toast('That overlaps something — pick an open area.', { type: 'error' }); return; }
    if (tool === 'plot') {
      const id = tmp.current--;
      setPlaced(p => [...p, { id, plot_number: nextPlotNumber(), status: 'available', ...rect, rounded, isNew: true }]);
      setSel({ kind: 'plot', key: id });
    } else {
      const key = tmp.current--;
      setFeatures(f => [...f, { key, feature_type: tool, label: '', ...rect, color: FEATURE_COLOR[tool], rounded }]);
      setSel({ kind: 'feature', key });
    }
    setDirty(true);
  };

  const remove = (ref, kind) => {
    if (kind === 'plot') setPlaced(p => p.filter(x => x !== ref));
    else setFeatures(f => f.filter(x => x !== ref));
    setSel(null); setDirty(true);
  };
  const patchPlot = (id, patch) => { setPlaced(p => p.map(x => x.id === id ? { ...x, ...patch } : x)); setDirty(true); };
  const patchFeature = (key, patch) => { setFeatures(f => f.map(x => x.key === key ? { ...x, ...patch } : x)); setDirty(true); };

  const selPlot = sel?.kind === 'plot' ? placed.find(p => p.id === sel.key) : null;
  const selFeature = sel?.kind === 'feature' ? features.find(f => f.key === sel.key) : null;

  const resize = (nr, nc) => {
    nr = Math.max(2, Math.min(nr, 60)); nc = Math.max(2, Math.min(nc, 60));
    // Drop anything that would fall outside the smaller grid.
    setPlaced(p => p.filter(x => x.row + x.h <= nr && x.col + x.w <= nc));
    setFeatures(f => f.filter(x => x.row + x.h <= nr && x.col + x.w <= nc));
    setRows(nr); setCols(nc); setDirty(true);
  };

  const handleSave = async () => {
    // Saving the layout is Pro-gated but creating plots is not — check up
    // front so a free garden never half-saves (plots created, never placed).
    if (!isPro) {
      toast('Saving the layout designer is part of Garden Pro — see your garden billing page for plans.', { type: 'error' });
      return;
    }
    setSaving(true);
    try {
      const newOnes = placed.filter(p => p.isNew);
      const idMap = {};
      if (newOnes.length) {
        const res = await gardensAPI.addPlots(gardenId, {
          plots: newOnes.map(p => ({ plot_number: p.plot_number, size: '' })),
        });
        (res.data || []).forEach((created, i) => { if (newOnes[i]) idMap[newOnes[i].id] = created.id; });
      }
      await gardenAdminAPI.updatePlotLayout(gardenId, {
        grid_rows: rows, grid_cols: cols,
        plots: placed.map(p => ({
          id: idMap[p.id] || p.id, grid_row: p.row, grid_col: p.col,
          grid_width: p.w, grid_height: p.h, rounded: p.rounded,
        })),
        features: features.map(f => ({
          feature_type: f.feature_type, label: f.label,
          grid_row: f.row, grid_col: f.col, grid_width: f.w, grid_height: f.h,
          color: f.color, rounded: f.rounded,
        })),
      });
      toast('Layout saved!', { type: 'success' });
      setDirty(false);
      onSaved && onSaved();
    } catch (err) {
      toast(err.response?.data?.error || 'Failed to save layout', { type: 'error' });
    }
    setSaving(false);
  };

  // ---- render helpers ----
  const toolBtn = (key, label, icon, color) => (
    <button key={key} type="button" onClick={() => setTool(key)}
      className="btn btn-sm d-inline-flex align-items-center gap-1"
      style={{
        border: tool === key ? '2px solid var(--yh-ink)' : '1px solid var(--yh-border)',
        background: tool === key ? 'var(--yh-lime-soft)' : '#fff', fontSize: '.78rem',
        color: 'var(--yh-ink)', padding: '4px 9px',
      }}>
      {color && <span style={{ width: 11, height: 11, borderRadius: 3, background: color, display: 'inline-block' }} />}
      <i className={`bi ${icon}`} /> {label}
    </button>
  );

  const overlay = (el, kind) => {
    const isSel = (kind === 'plot' && sel?.kind === 'plot' && sel.key === el.id)
      || (kind === 'feature' && sel?.kind === 'feature' && sel.key === el.key);
    const bg = kind === 'plot' ? (STATUS_COLOR[el.status] || STATUS_COLOR.available) : el.color;
    return (
      <div key={kind + (el.id ?? el.key)} style={{
        position: 'absolute', left: el.col * cell + 1, top: el.row * cell + 1,
        width: el.w * cell - 2, height: el.h * cell - 2,
        background: bg, opacity: kind === 'feature' ? 0.92 : 1,
        border: isSel ? '2px solid var(--yh-ink)' : '1px solid rgba(0,0,0,.18)',
        borderRadius: el.rounded ? Math.min(cell, el.w * cell, el.h * cell) / 2 : 4,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '.66rem', fontWeight: 600, color: '#22242a', textAlign: 'center',
        overflow: 'hidden', pointerEvents: 'none', boxSizing: 'border-box', lineHeight: 1.05,
        backgroundImage: kind === 'feature' ? 'repeating-linear-gradient(45deg,rgba(255,255,255,.18) 0 6px,transparent 6px 12px)' : 'none',
      }}>
        {kind === 'plot' ? el.plot_number : (el.label || FEATURE_LABEL[el.feature_type])}
      </div>
    );
  };

  const dragRect = drag ? rectOf(drag) : null;

  return (
    <div>
      {/* Toolbar */}
      <div className="d-flex flex-wrap align-items-center gap-2 mb-2 p-2"
        style={{ background: 'var(--yh-surface)', borderRadius: 10, border: '1px solid var(--yh-border)' }}>
        <span className="small fw-semibold me-1">Draw:</span>
        {toolBtn('plot', 'Plot', 'bi-bounding-box', STATUS_COLOR.available)}
        {FEATURE_TYPES.map(f => toolBtn(f.key, f.label, f.icon, f.color))}
        <span className="mx-1" style={{ borderLeft: '1px solid var(--yh-border)', height: 22 }} />
        {toolBtn('select', 'Select', 'bi-cursor', null)}
        {toolBtn('erase', 'Erase', 'bi-eraser', null)}
        <label className="d-inline-flex align-items-center gap-1 small ms-1" style={{ cursor: 'pointer' }}>
          <input type="checkbox" checked={rounded} onChange={e => setRounded(e.target.checked)} /> Rounded
        </label>
      </div>

      <div className="d-flex flex-wrap align-items-center gap-3 mb-2 small text-muted">
        <span>Grid:
          <button className="btn btn-sm btn-outline-secondary py-0 px-1 mx-1" onClick={() => resize(rows, cols - 1)}>−</button>
          {cols}<span className="mx-1">cols ×</span>
          <button className="btn btn-sm btn-outline-secondary py-0 px-1 mx-1" onClick={() => resize(rows - 1, cols)}>−</button>
          {rows}<span className="ms-1">rows</span>
          <button className="btn btn-sm btn-outline-secondary py-0 px-1 ms-1" onClick={() => resize(rows + 1, cols)}>+row</button>
          <button className="btn btn-sm btn-outline-secondary py-0 px-1 ms-1" onClick={() => resize(rows, cols + 1)}>+col</button>
        </span>
        <span>Zoom:
          {CELL_SIZES.map(s => (
            <button key={s} className="btn btn-sm py-0 px-2 ms-1"
              style={{ border: cell === s ? '2px solid var(--yh-ink)' : '1px solid var(--yh-border)', background: '#fff' }}
              onClick={() => setCell(s)}>{s === 22 ? 'S' : s === 30 ? 'M' : s === 40 ? 'L' : 'XL'}</button>
          ))}
        </span>
        <span className="ms-auto">
          <button className="btn btn-sm" disabled={saving || !dirty}
            style={{ background: 'var(--yh-lime)', color: 'var(--yh-ink)', fontWeight: 600 }}
            onClick={handleSave}>
            {saving ? 'Saving…' : <><i className="bi bi-check-lg me-1" />Save layout</>}
          </button>
        </span>
      </div>

      <div className="d-flex gap-3 flex-wrap align-items-start">
        {/* Board */}
        <div style={{ overflow: 'auto', maxWidth: '100%', border: '1px solid var(--yh-border)', borderRadius: 8, background: '#fbfbf7' }}>
          <div
            ref={boardRef}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            style={{
              position: 'relative', width: cols * cell, height: rows * cell,
              cursor: tool === 'erase' ? 'crosshair' : (tool === 'select' ? 'pointer' : 'cell'),
              backgroundSize: `${cell}px ${cell}px`,
              backgroundImage: 'linear-gradient(to right,#e3e3da 1px,transparent 1px),linear-gradient(to bottom,#e3e3da 1px,transparent 1px)',
              touchAction: 'none', userSelect: 'none',
            }}>
            {features.map(f => overlay(f, 'feature'))}
            {placed.map(p => overlay(p, 'plot'))}
            {dragRect && (
              <div style={{
                position: 'absolute', left: dragRect.col * cell, top: dragRect.row * cell,
                width: dragRect.w * cell, height: dragRect.h * cell,
                border: '2px dashed var(--yh-ink)', background: 'rgba(227,255,143,.35)',
                borderRadius: rounded ? cell / 2 : 4, pointerEvents: 'none', boxSizing: 'border-box',
              }} />
            )}
          </div>
        </div>

        {/* Properties / help panel */}
        <div style={{ minWidth: 220, flex: '1 1 220px', maxWidth: 320 }}>
          {selPlot ? (
            <div className="p-3" style={{ border: '1px solid var(--yh-border)', borderRadius: 10 }}>
              <div className="fw-bold mb-2"><i className="bi bi-bounding-box me-1" />Plot {selPlot.plot_number}</div>
              <div className="small text-muted mb-2">{selPlot.w}×{selPlot.h} cells · {selPlot.status}</div>
              <label className="d-flex align-items-center gap-2 small mb-2" style={{ cursor: 'pointer' }}>
                <input type="checkbox" checked={selPlot.rounded} onChange={e => patchPlot(selPlot.id, { rounded: e.target.checked })} /> Rounded corners
              </label>
              <button className="btn btn-sm btn-outline-danger w-100" onClick={() => remove(selPlot, 'plot')}>
                <i className="bi bi-trash me-1" />Remove from map
              </button>
            </div>
          ) : selFeature ? (
            <div className="p-3" style={{ border: '1px solid var(--yh-border)', borderRadius: 10 }}>
              <div className="fw-bold mb-2"><i className="bi bi-pin-map me-1" />{FEATURE_LABEL[selFeature.feature_type]}</div>
              <input className="form-control form-control-sm mb-2" placeholder="Label (e.g. North shed)"
                value={selFeature.label} onChange={e => patchFeature(selFeature.key, { label: e.target.value })} />
              <div className="d-flex align-items-center gap-2 mb-2">
                <span className="small">Color</span>
                <input type="color" value={selFeature.color || '#7a7d85'}
                  onChange={e => patchFeature(selFeature.key, { color: e.target.value })}
                  style={{ width: 40, height: 28, border: '1px solid var(--yh-border)', borderRadius: 6, padding: 0 }} />
              </div>
              <label className="d-flex align-items-center gap-2 small mb-2" style={{ cursor: 'pointer' }}>
                <input type="checkbox" checked={selFeature.rounded} onChange={e => patchFeature(selFeature.key, { rounded: e.target.checked })} /> Rounded corners
              </label>
              <button className="btn btn-sm btn-outline-danger w-100" onClick={() => remove(selFeature, 'feature')}>
                <i className="bi bi-trash me-1" />Delete
              </button>
            </div>
          ) : (
            <div className="p-3 small text-muted" style={{ border: '1px dashed var(--yh-border)', borderRadius: 10 }}>
              <p className="mb-2"><strong>Design your garden</strong></p>
              <p className="mb-2">Pick <strong>Plot</strong> or a feature, then <strong>drag across squares</strong> to draw it. New plots auto-number.</p>
              <p className="mb-2">Use <strong>Select</strong> to edit an element (label, color, rounded corners) and <strong>Erase</strong> to clear cells.</p>
              <p className="mb-0">Add rows/cols and zoom to match your real space, then <strong>Save layout</strong>.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
