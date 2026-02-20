import { KeyboardEvent, PointerEvent, useEffect, useId, useMemo, useRef, useState } from "react";

export type ChartPoint = {
  x: string;
  y: number;
  y2?: number;
};

type EditablePoint = ChartPoint & {
  xPos: number;
};

type PersistedChartPoint = {
  xPos: number;
  y: number;
};

type SimpleLineChartProps = {
  title: string;
  points: ChartPoint[];
  yLabel?: string;
  seriesAName?: string;
  seriesBName?: string;
  seriesAColor?: string;
  seriesBColor?: string;
  height?: number;
  editable?: boolean;
  persistKey?: string;
};

type Domain = {
  minY: number;
  maxY: number;
};

const CHART_LOCAL_STORAGE_PREFIX = "spline-lstm:chart-control-points:v1";
const MIN_X_GAP_PX = 14;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function indexToRatio(index: number, length: number): number {
  if (length <= 1) return 0.5;
  return index / (length - 1);
}

export function svgToRatio(svgX: number, width: number, padding: number): number {
  const drawWidth = Math.max(1e-9, width - padding * 2);
  const clampedSvgX = clamp(svgX, padding, width - padding);
  return (clampedSvgX - padding) / drawWidth;
}

export function ratioToSvgX(ratio: number, width: number, padding: number): number {
  return padding + clamp(ratio, 0, 1) * (width - padding * 2);
}

export function constrainXRatio(
  ratio: number,
  index: number,
  points: Pick<EditablePoint, "xPos">[],
  minGapRatio: number,
): number {
  if (points.length <= 1) return 0.5;
  if (index <= 0) return 0;
  if (index >= points.length - 1) return 1;

  const left = (points[index - 1]?.xPos ?? 0) + minGapRatio;
  const right = (points[index + 1]?.xPos ?? 1) - minGapRatio;
  return clamp(ratio, left, right);
}

function getStorageKey(persistKey: string): string {
  return `${CHART_LOCAL_STORAGE_PREFIX}:${persistKey}`;
}

export function readPersistedControlPoints(persistKey?: string): PersistedChartPoint[] | null {
  if (!persistKey || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(getStorageKey(persistKey));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    const normalized = parsed
      .map((entry) => {
        const xPos = typeof entry?.xPos === "number" ? entry.xPos : Number.NaN;
        const y = typeof entry?.y === "number" ? entry.y : Number.NaN;
        if (!Number.isFinite(xPos) || !Number.isFinite(y)) return null;
        return { xPos: clamp(xPos, 0, 1), y };
      })
      .filter((v): v is PersistedChartPoint => !!v);
    return normalized.length > 0 ? normalized : null;
  } catch {
    return null;
  }
}

export function writePersistedControlPoints(persistKey: string, points: PersistedChartPoint[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(getStorageKey(persistKey), JSON.stringify(points));
  } catch {
    // no-op (storage unavailable/full)
  }
}

export function clearPersistedControlPoints(persistKey: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(getStorageKey(persistKey));
  } catch {
    // no-op
  }
}

function buildEditablePoints(basePoints: ChartPoint[]): EditablePoint[] {
  return basePoints.map((point, index) => ({ ...point, xPos: indexToRatio(index, basePoints.length) }));
}

function applyPersistedPoints(basePoints: ChartPoint[], persisted: PersistedChartPoint[] | null): EditablePoint[] {
  const withDefaults = buildEditablePoints(basePoints);
  if (!persisted || persisted.length !== withDefaults.length) return withDefaults;

  return withDefaults.map((point, index) => ({
    ...point,
    xPos: index === 0 ? 0 : index === withDefaults.length - 1 ? 1 : clamp(persisted[index]?.xPos ?? point.xPos, 0, 1),
    y: Number.isFinite(persisted[index]?.y) ? persisted[index]!.y : point.y,
  }));
}

function getPaddedDomain(points: ChartPoint[]): Domain | null {
  const yValues = points.map((p) => p.y).filter(Number.isFinite);
  const y2Values = points
    .map((p) => p.y2)
    .filter((v): v is number => typeof v === "number" && Number.isFinite(v));

  if (yValues.length === 0 && y2Values.length === 0) {
    return null;
  }

  const all = [...yValues, ...y2Values];
  const minYRaw = Math.min(...all);
  const maxYRaw = Math.max(...all);
  const pad = Math.max(1, (maxYRaw - minYRaw) * 0.08);

  return {
    minY: minYRaw - pad,
    maxY: maxYRaw + pad,
  };
}


function formatXAxisLabel(label: string): string {
  if (!label) return "-";
  const isoLike = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(label);
  if (isoLike) {
    const date = new Date(label);
    if (!Number.isNaN(date.getTime())) {
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hour = String(date.getHours()).padStart(2, "0");
      const minute = String(date.getMinutes()).padStart(2, "0");
      return `${month}-${day} ${hour}:${minute}`;
    }
  }

  if (label.length <= 12) return label;
  return `${label.slice(0, 12)}…`;
}

function buildXTicks(points: EditablePoint[], width: number, padding: number): Array<{ x: number; label: string }> {
  if (points.length === 0) return [];

  const preferredTickCount = points.length <= 24 ? 4 : points.length <= 72 ? 6 : 8;
  const tickCount = Math.min(points.length, preferredTickCount);
  const indices = new Set<number>();

  for (let i = 0; i < tickCount; i += 1) {
    const ratio = tickCount <= 1 ? 0 : i / (tickCount - 1);
    const index = Math.round(ratio * (points.length - 1));
    indices.add(index);
  }

  return [...indices]
    .sort((a, b) => a - b)
    .map((index) => ({
      x: ratioToSvgX(points[index]?.xPos ?? indexToRatio(index, points.length), width, padding),
      label: formatXAxisLabel(points[index]?.x ?? `t-${index + 1}`),
    }));
}

function toPath(
  values: Array<{ xPos: number; y: number }>,
  width: number,
  height: number,
  padding: number,
  minY: number,
  maxY: number,
): string {
  if (values.length === 0) return "";
  const safeSpan = Math.max(1e-9, maxY - minY);

  return values
    .map((v, index) => {
      const x = ratioToSvgX(v.xPos, width, padding);
      const y = padding + ((maxY - v.y) / safeSpan) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function yToSvg(
  value: number,
  height: number,
  padding: number,
  minY: number,
  maxY: number,
): number {
  const safeSpan = Math.max(1e-9, maxY - minY);
  const drawHeight = height - padding * 2;
  return padding + ((maxY - value) / safeSpan) * drawHeight;
}

export function svgToY(
  svgY: number,
  height: number,
  padding: number,
  minY: number,
  maxY: number,
): number {
  const safeSpan = Math.max(1e-9, maxY - minY);
  const drawHeight = height - padding * 2;
  const clampedSvgY = clamp(svgY, padding, height - padding);
  const ratio = (clampedSvgY - padding) / Math.max(1e-9, drawHeight);
  return maxY - ratio * safeSpan;
}

function isModifiedAgainstBaseline(base: EditablePoint[], current: EditablePoint[]): boolean {
  if (base.length !== current.length) return false;
  return base.some((point, index) => {
    const next = current[index];
    if (!next) return false;
    return Math.abs(point.y - next.y) > 1e-9 || Math.abs(point.xPos - next.xPos) > 1e-9;
  });
}

export function SimpleLineChart({
  title,
  points,
  yLabel = "값",
  seriesAName = "Series A",
  seriesBName,
  seriesAColor = "#2563eb",
  seriesBColor = "#ef4444",
  height = 240,
  editable = false,
  persistKey,
}: SimpleLineChartProps) {
  const id = useId();
  const width = 900;
  const padding = 28;

  const [workingPoints, setWorkingPoints] = useState<EditablePoint[]>(() => buildEditablePoints(points));
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [hasSavedEdits, setHasSavedEdits] = useState(false);
  const [didHydratePersisted, setDidHydratePersisted] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const persisted = editable ? readPersistedControlPoints(persistKey) : null;
    const restored = applyPersistedPoints(points, persisted);
    setWorkingPoints(restored);
    setHasSavedEdits(Boolean(editable && persistKey && persisted));
    setDidHydratePersisted(true);
  }, [editable, persistKey, points]);

  const domain = useMemo(() => getPaddedDomain(points), [points]);
  const renderPoints = editable ? workingPoints : buildEditablePoints(points);

  const baselinePoints = useMemo(() => buildEditablePoints(points), [points]);
  const isEdited = useMemo(
    () => (editable ? isModifiedAgainstBaseline(baselinePoints, workingPoints) : false),
    [baselinePoints, editable, workingPoints],
  );

  useEffect(() => {
    if (!editable || !persistKey || !didHydratePersisted) return;

    if (!isEdited) {
      clearPersistedControlPoints(persistKey);
      setHasSavedEdits(false);
      return;
    }

    writePersistedControlPoints(
      persistKey,
      workingPoints.map((p) => ({ xPos: p.xPos, y: p.y })),
    );
    setHasSavedEdits(true);
  }, [didHydratePersisted, editable, isEdited, persistKey, workingPoints]);

  const computed = useMemo(() => {
    const yValues = renderPoints.map((p) => p.y).filter(Number.isFinite);
    const y2Values = renderPoints
      .map((p) => p.y2)
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v));

    if (!domain || (yValues.length === 0 && y2Values.length === 0)) {
      return null;
    }

    const pathA = toPath(renderPoints.map((p) => ({ xPos: p.xPos, y: p.y })), width, height, padding, domain.minY, domain.maxY);
    const pathB = y2Values.length > 0
      ? toPath(renderPoints.map((p) => ({ xPos: p.xPos, y: p.y2 ?? Number.NaN })).filter((v) => Number.isFinite(v.y)), width, height, padding, domain.minY, domain.maxY)
      : "";

    return {
      minY: domain.minY,
      maxY: domain.maxY,
      pathA,
      pathB,
      controlPoints: renderPoints.map((point, index) => ({
        index,
        x: ratioToSvgX(point.xPos, width, padding),
        y: yToSvg(point.y, height, padding, domain.minY, domain.maxY),
      })),
      leftTicks: [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const value = domain.maxY - (domain.maxY - domain.minY) * ratio;
        const y = padding + (height - padding * 2) * ratio;
        return { value, y };
      }),
      xTicks: buildXTicks(renderPoints, width, padding),
    };
  }, [domain, height, padding, renderPoints]);

  function updatePointFromEvent(index: number, event: PointerEvent<SVGCircleElement | SVGSVGElement>) {
    if (!editable || !domain || !svgRef.current) return;

    const rect = svgRef.current.getBoundingClientRect();
    const scaleY = height / Math.max(1, rect.height);
    const scaleX = width / Math.max(1, rect.width);
    const svgY = (event.clientY - rect.top) * scaleY;
    const svgX = (event.clientX - rect.left) * scaleX;

    const nextY = clamp(svgToY(svgY, height, padding, domain.minY, domain.maxY), domain.minY, domain.maxY);

    setWorkingPoints((prev) => {
      const minGapRatio = MIN_X_GAP_PX / Math.max(1e-9, width - padding * 2);
      const desiredRatio = svgToRatio(svgX, width, padding);
      const nextRatio = constrainXRatio(desiredRatio, index, prev, minGapRatio);
      return prev.map((point, i) => (i === index ? { ...point, y: nextY, xPos: nextRatio } : point));
    });
  }

  function handlePointKeyboard(index: number, event: KeyboardEvent<SVGCircleElement>) {
    if (!editable || !domain) return;

    const yStep = (domain.maxY - domain.minY) * 0.02;
    const xStep = 1 / Math.max(20, points.length * 2);

    let deltaY = 0;
    let deltaX = 0;

    if (event.key === "ArrowUp") deltaY = yStep;
    if (event.key === "ArrowDown") deltaY = -yStep;
    if (event.key === "ArrowLeft") deltaX = -xStep;
    if (event.key === "ArrowRight") deltaX = xStep;

    if (deltaY === 0 && deltaX === 0) return;

    event.preventDefault();
    setWorkingPoints((prev) => {
      const minGapRatio = MIN_X_GAP_PX / Math.max(1e-9, width - padding * 2);
      return prev.map((point, i) => {
        if (i !== index) return point;
        return {
          ...point,
          y: clamp(point.y + deltaY, domain.minY, domain.maxY),
          xPos: constrainXRatio(point.xPos + deltaX, index, prev, minGapRatio),
        };
      });
    });
  }

  const editStatusLabel = !editable ? "" : isEdited ? "edited · saved" : hasSavedEdits ? "saved" : "original";

  return (
    <div className="chart-wrap" role="img" aria-label={title}>
      <div className="chart-header">
        <h4>{title}</h4>
        <div className="chart-legend">
          <span><i style={{ background: seriesAColor }} />{seriesAName}</span>
          {seriesBName && computed?.pathB && <span><i style={{ background: seriesBColor }} />{seriesBName}</span>}
          {editable && <span className={`chart-edit-badge ${isEdited ? "is-edited" : ""}`}>{editStatusLabel}</span>}
        </div>
      </div>

      {editable && (
        <div className="action-row">
          <button
            type="button"
            onClick={() => setWorkingPoints(baselinePoints)}
            disabled={!isEdited}
            aria-label="Reset chart control points"
          >
            Reset to original
          </button>
          <button
            type="button"
            onClick={() => {
              if (persistKey) clearPersistedControlPoints(persistKey);
              setHasSavedEdits(false);
              setWorkingPoints(baselinePoints);
            }}
            disabled={!hasSavedEdits && !isEdited}
            aria-label="Clear saved chart control points"
          >
            Clear saved edits
          </button>
          <span className="muted">점을 드래그(또는 방향키)해서 곡선을 수정할 수 있습니다.</span>
        </div>
      )}

      {!computed ? (
        <p className="muted">표시할 데이터가 없습니다.</p>
      ) : (
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          className="chart-svg"
          aria-labelledby={`${id}-title`}
          onPointerMove={(event) => {
            if (draggingIndex === null) return;
            updatePointFromEvent(draggingIndex, event);
          }}
          onPointerUp={() => setDraggingIndex(null)}
          onPointerCancel={() => setDraggingIndex(null)}
          onPointerLeave={() => setDraggingIndex(null)}
        >
          <title id={`${id}-title`}>{title}</title>

          {computed.leftTicks.map((t, i) => (
            <g key={i}>
              <line x1={padding} y1={t.y} x2={width - padding} y2={t.y} className="chart-grid" />
              <text x={8} y={t.y + 4} className="chart-tick">{t.value.toFixed(2)}</text>
            </g>
          ))}

          {computed.xTicks.map((t, i) => (
            <text key={i} x={t.x} y={height - 8} className="chart-tick" textAnchor="middle">{t.label}</text>
          ))}

          <text x={10} y={14} className="chart-axis-label">{yLabel}</text>

          <path d={computed.pathA} stroke={seriesAColor} fill="none" strokeWidth="2.2" />
          {computed.pathB && <path d={computed.pathB} stroke={seriesBColor} fill="none" strokeWidth="2" />}

          {editable && computed.controlPoints.map((point) => (
            <circle
              key={point.index}
              cx={point.x}
              cy={point.y}
              r={draggingIndex === point.index ? 6 : 5}
              className="chart-control-point"
              tabIndex={0}
              role="slider"
              aria-label={`Control point ${point.index + 1}`}
              onKeyDown={(event) => handlePointKeyboard(point.index, event)}
              onPointerDown={(event) => {
                setDraggingIndex(point.index);
                event.currentTarget.setPointerCapture(event.pointerId);
                updatePointFromEvent(point.index, event);
              }}
              onPointerUp={() => setDraggingIndex(null)}
            />
          ))}
        </svg>
      )}
    </div>
  );
}
