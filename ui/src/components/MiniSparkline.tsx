import { useMemo } from "react";

type MiniSparklineProps = {
  values: number[];
  label: string;
  color?: string;
  emptyText?: string;
  min?: number;
  max?: number;
};

function toPath(values: number[], width: number, height: number, padding: number, minY: number, maxY: number): string {
  if (values.length === 0) return "";
  const drawWidth = width - padding * 2;
  const drawHeight = height - padding * 2;
  const safeSpan = Math.max(1e-9, maxY - minY);

  return values
    .map((value, index) => {
      const x = padding + (values.length <= 1 ? drawWidth / 2 : (index / (values.length - 1)) * drawWidth);
      const y = padding + ((maxY - value) / safeSpan) * drawHeight;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function MiniSparkline({
  values,
  label,
  color = "#2563eb",
  emptyText = "데이터 없음",
  min,
  max,
}: MiniSparklineProps) {
  const width = 220;
  const height = 48;
  const padding = 4;

  const path = useMemo(() => {
    const finiteValues = values.filter(Number.isFinite);
    if (finiteValues.length === 0) return "";

    const rawMin = typeof min === "number" ? min : Math.min(...finiteValues);
    const rawMax = typeof max === "number" ? max : Math.max(...finiteValues);
    const pad = Math.max(0.5, (rawMax - rawMin) * 0.08);
    return toPath(finiteValues, width, height, padding, rawMin - pad, rawMax + pad);
  }, [max, min, values]);

  if (!path) {
    return <p className="spark-empty">{emptyText}</p>;
  }

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <path d={path} stroke={color} fill="none" strokeWidth={2} strokeLinecap="round" />
    </svg>
  );
}
