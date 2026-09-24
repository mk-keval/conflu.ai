import { cn } from '@/lib/cn';

interface SkeletonProps {
  className?: string;
}

export function SkeletonLine({ className }: SkeletonProps) {
  return (
    <div
      className={cn('bg-dark-500 h-4 w-full animate-pulse rounded', className)}
    />
  );
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn('bg-dark-700 rounded p-4', className)}>
      <SkeletonLine className="mb-3 w-1/3" />
      <SkeletonLine className="mb-2" />
      <SkeletonLine className="w-2/3" />
    </div>
  );
}

export function SkeletonTable({
  rows = 5,
  className,
}: SkeletonProps & { rows?: number }) {
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex gap-4 pb-2">
        <SkeletonLine className="h-6 w-24" />
        <SkeletonLine className="h-6 w-16" />
        <SkeletonLine className="h-6 w-20" />
        <SkeletonLine className="h-6 w-32" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <SkeletonLine className="h-8 w-24" />
          <SkeletonLine className="h-8 w-16" />
          <SkeletonLine className="h-8 w-20" />
          <SkeletonLine className="h-8 w-32" />
        </div>
      ))}
    </div>
  );
}
