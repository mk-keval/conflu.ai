import { cn } from '@/lib/cn';

/**
 * conflu.ai brand mark — "Converging Flow".
 *
 * Three signal streams flow in from the sides, converge into a single
 * rising stroke, and resolve into an upward arrowhead: confluence of
 * market signals → one clear verdict. The teal gradient is the brand
 * accent; the wordmark uses the Newsreader display face.
 */

interface BrandMarkProps {
  className?: string;
  showWordmark?: boolean;
}

export function BrandGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('h-8 w-8', className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id="conflu-flow"
          x1="4"
          y1="27"
          x2="24"
          y2="6"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#0D9488" />
          <stop offset="0.55" stopColor="#2DD4BF" />
          <stop offset="1" stopColor="#99F6E4" />
        </linearGradient>
      </defs>

      {/* Left signal stream */}
      <path
        d="M4 27C9.5 27 13 22.5 15.25 16.75"
        stroke="url(#conflu-flow)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      {/* Right signal stream */}
      <path
        d="M28 27C22.5 27 19 22.5 16.75 16.75"
        stroke="url(#conflu-flow)"
        strokeWidth="4"
        strokeLinecap="round"
        opacity="0.8"
      />
      {/* Converged rising stem */}
      <path
        d="M16 16.75V8.25"
        stroke="url(#conflu-flow)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      {/* Upward verdict arrowhead */}
      <path
        d="M11.25 12.75L16 7.25L20.75 12.75"
        stroke="url(#conflu-flow)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BrandMark({ className, showWordmark = true }: BrandMarkProps) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <BrandGlyph />
      {showWordmark && (
        <span className="font-display text-lg font-semibold tracking-tight text-text-primary">
          conflu<span className="text-accent">.ai</span>
        </span>
      )}
    </div>
  );
}
