import React, { ReactNode, useEffect, useMemo, useRef, useState } from "react";

type VirtualListProps<T> = {
  items: T[];
  itemKey: (item: T, index: number) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  height: number;
  itemHeight: number;
  overscan?: number;
  gap?: number;
  className?: string;
  emptyMessage?: ReactNode;
  footer?: ReactNode;
  onEndReached?: () => void;
  endReachedThreshold?: number;
  resetKey?: string | number;
};

export function VirtualList<T>({
  items,
  itemKey,
  renderItem,
  height,
  itemHeight,
  overscan = 4,
  gap = 0,
  className,
  emptyMessage,
  footer,
  onEndReached,
  endReachedThreshold = 240,
  resetKey,
}: VirtualListProps<T>) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const stride = itemHeight + gap;
  const totalHeight = items.length > 0 ? items.length * stride - gap : 0;

  useEffect(() => {
    if (!scrollRef.current) {
      return;
    }
    scrollRef.current.scrollTop = 0;
    setScrollTop(0);
  }, [resetKey]);

  const windowRange = useMemo(() => {
    if (!items.length) {
      return { start: 0, end: 0 };
    }
    const visibleCount = Math.max(1, Math.ceil(height / Math.max(stride, 1)));
    const start = Math.max(0, Math.floor(scrollTop / Math.max(stride, 1)) - overscan);
    const end = Math.min(items.length, start + visibleCount + overscan * 2);
    return { start, end };
  }, [height, items.length, overscan, scrollTop, stride]);

  useEffect(() => {
    if (!onEndReached || !items.length) {
      return;
    }
    const remaining = totalHeight - (scrollTop + height);
    if (remaining <= endReachedThreshold) {
      onEndReached();
    }
  }, [endReachedThreshold, height, items.length, onEndReached, scrollTop, totalHeight]);

  return (
    <div className={className} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div
        ref={scrollRef}
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
        style={{
          height,
          overflowY: "auto",
          overflowX: "hidden",
          position: "relative",
        }}
      >
        {items.length === 0 ? (
          <div className="helper" style={{ padding: "32px 16px" }}>
            {emptyMessage ?? "No rows"}
          </div>
        ) : (
          <div style={{ height: totalHeight, position: "relative" }}>
            {items.slice(windowRange.start, windowRange.end).map((item, index) => {
              const absoluteIndex = windowRange.start + index;
              return (
                <div
                  key={itemKey(item, absoluteIndex)}
                  style={{
                    position: "absolute",
                    top: absoluteIndex * stride,
                    left: 0,
                    right: 0,
                    height: itemHeight,
                  }}
                >
                  {renderItem(item, absoluteIndex)}
                </div>
              );
            })}
          </div>
        )}
      </div>
      {footer}
    </div>
  );
}
