export function ChartSkeleton() {
  return (
    <div className="h-[300px] animate-pulse rounded bg-dark-800 p-4">
      <div className="mb-4 flex items-center gap-4">
        <div className="h-4 w-20 rounded bg-dark-500" />
        <div className="h-4 w-16 rounded bg-dark-500" />
      </div>
      <div className="flex h-[200px] items-end gap-2">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 rounded-t bg-dark-500"
            style={{
              height: `${30 + Math.random() * 70}%`,
              opacity: 0.3 + Math.random() * 0.4,
            }}
          />
        ))}
      </div>
    </div>
  );
}
