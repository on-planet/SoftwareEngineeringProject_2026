import React, { ReactNode, useMemo, useRef, useState } from "react";

export type VirtualTableColumn<T> = {
  key: string;
  header: ReactNode;
  width?: string | number;
  align?: "left" | "center" | "right";
  cell: (row: T, index: number) => ReactNode;
};

type VirtualTableProps<T> = {
  rows: T[];
  columns: Array<VirtualTableColumn<T>>;
  rowKey: (row: T, index: number) => string | number;
  height?: number;
  rowHeight?: number;
  overscan?: number;
  emptyMessage?: ReactNode;
  className?: string;
};

function resolveWidth(width?: string | number) {
  if (typeof width === "number") {
    return `${width}px`;
  }
  return width ?? "minmax(0, 1fr)";
}

export function VirtualTable<T>({
  rows,
  columns,
  rowKey,
  height = 360,
  rowHeight = 44,
  overscan = 6,
  emptyMessage,
  className,
}: VirtualTableProps<T>) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const gridTemplateColumns = useMemo(
    () => columns.map((column) => resolveWidth(column.width)).join(" "),
    [columns],
  );
  const totalHeight = rows.length * rowHeight;
  const visibleCount = Math.max(1, Math.ceil(height / Math.max(rowHeight, 1)));
  const start = Math.max(0, Math.floor(scrollTop / Math.max(rowHeight, 1)) - overscan);
  const end = Math.min(rows.length, start + visibleCount + overscan * 2);

  return (
    <div
      className={className}
      style={{
        border: "1px solid rgba(148, 163, 184, 0.22)",
        borderRadius: 16,
        overflow: "hidden",
        background: "rgba(255, 255, 255, 0.88)",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns,
          gap: 12,
          padding: "12px 16px",
          borderBottom: "1px solid rgba(148, 163, 184, 0.18)",
          background: "rgba(248, 250, 252, 0.92)",
          fontSize: 12,
          fontWeight: 700,
          color: "var(--text-muted, #475467)",
        }}
      >
        {columns.map((column) => (
          <div key={column.key} style={{ textAlign: column.align ?? "left" }}>
            {column.header}
          </div>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="helper" style={{ padding: "28px 16px" }}>
          {emptyMessage ?? "No rows"}
        </div>
      ) : (
        <div
          ref={scrollRef}
          onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
          style={{ height, overflowY: "auto", overflowX: "hidden" }}
        >
          <div style={{ height: totalHeight, position: "relative" }}>
            {rows.slice(start, end).map((row, index) => {
              const absoluteIndex = start + index;
              return (
                <div
                  key={rowKey(row, absoluteIndex)}
                  style={{
                    position: "absolute",
                    top: absoluteIndex * rowHeight,
                    left: 0,
                    right: 0,
                    height: rowHeight,
                    display: "grid",
                    gridTemplateColumns,
                    gap: 12,
                    alignItems: "center",
                    padding: "0 16px",
                    borderBottom: "1px solid rgba(148, 163, 184, 0.12)",
                    background: absoluteIndex % 2 === 0 ? "transparent" : "rgba(248, 250, 252, 0.58)",
                    fontSize: 13,
                  }}
                >
                  {columns.map((column) => (
                    <div
                      key={column.key}
                      style={{
                        minWidth: 0,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        textAlign: column.align ?? "left",
                      }}
                    >
                      {column.cell(row, absoluteIndex)}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
