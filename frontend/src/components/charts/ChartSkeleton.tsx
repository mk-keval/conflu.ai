export function ChartSkeleton() {
  return (
    <div className="bg-dark-800 h-[300px] animate-pulse rounded p-4">
      <div className="mb-4 flex items-center gap-4">
        <div className="bg-dark-500 h-4 w-20 rounded" />
        <div className="bg-dark-500 h-4 w-16 rounded" />
      </div>
      <div className="flex h-[200px] items-end gap-2">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="bg-dark-500 flex-1 rounded-t"
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
