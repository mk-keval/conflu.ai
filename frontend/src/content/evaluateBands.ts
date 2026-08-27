/**
 * Bands DSL evaluator — frontend half of the parity contract with
 * `backend/app/infrastructure/professional/education_bands.py`.
 *
 * Grammar (must stay identical on both sides):
 *   condition := "value" <op> <rhs>
 *   op        := ">=" | "<=" | "==" | "!=" | ">" | "<"
 *   rhs       := single-quoted string | number
 *   band      := { if: condition, text: string }        // evaluated in order
 *
 * `${value}` inside band text is replaced by the transformed value.
 * The LAST band acts as fallback when no condition matches — the content
 * validator enforces that a final unconditional-ish band exists; at runtime,
 * if nothing matches, we return an empty string rather than crash.
 */

export type BandTransform =
  | 'percent'      // append % (value already expressed as percent)
  | 'ratio'        // 2-decimal + "x"
  | 'compactNumber' // K/M/B abbreviation
  | 'money'        // $ + thousands separators, 2 decimals
  | 'plain';       // raw passthrough

export interface ValueBand {
  /** Condition string, e.g. "value >= 70" or "value == 'bullish'" */
  if: string;
  /** Text template. `${value}` interpolates the transformed value. */
  text: string;
}

export interface ValueInterpretation {
  type: 'bands';
  transform?: BandTransform | null;
  bands: ValueBand[];
}

const CONDITION_RE =
  /^\s*value\s*(>=|<=|==|!=|>|<)\s*(?:'([^']*)'|(-?\d+(?:\.\d+)?))\s*$/;
const EPSILON = 1e-9;

function applyTransform(raw: string, transform?: BandTransform | null): string {
  const num = Number(raw);
  switch (transform) {
    case 'percent':
      return Number.isFinite(num) ? `${raw}%` : `${raw}%`;
    case 'ratio':
      return Number.isFinite(num) ? `${num.toFixed(2)}x` : `${raw}x`;
    case 'money':
      return Number.isFinite(num)
        ? `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : `$${raw}`;
    case 'compactNumber': {
      if (!Number.isFinite(num)) return raw;
      const abs = Math.abs(num);
      if (abs >= 1e9) return `${(num / 1e9).toFixed(1)}B`;
      if (abs >= 1e6) return `${(num / 1e6).toFixed(1)}M`;
      if (abs >= 1e3) return `${(num / 1e3).toFixed(1)}K`;
      return String(num);
    }
    case 'plain':
    default:
      // Default rendering: trim floats beyond 2 decimals to exactly 2
      // (mirrors narration._fmt). Strings and short decimals pass through.
      if (!Number.isFinite(num)) return raw;
      const dec = raw.split('.')[1];
      if (dec && dec.length > 2) {
        return num.toFixed(2);
      }
      return raw;
  }
}

/** Evaluate one condition against a value. Mirrors Python implementation exactly.
 * Empty/whitespace condition = unconditional (fallback band, must be last). */
export function evaluateCondition(condition: string, value: string): boolean {
  if (!condition || !condition.trim()) return true;
  const match = CONDITION_RE.exec(condition);
  if (!match) return false;

  const op = match[1];
  const strRhs = match[2];
  const numRhs = match[3];

  if (strRhs !== undefined) {
    const lhs = value.trim().toLowerCase();
    const rhs = strRhs.trim().toLowerCase();
    if (op === '==') return lhs === rhs;
    if (op === '!=') return lhs !== rhs;
    return false;
  }

  const num = Number(value);
  if (!Number.isFinite(num)) return false;
  const rhsNum = Number(numRhs);

  switch (op) {
    case '>': return num > rhsNum;
    case '<': return num < rhsNum;
    case '>=': return num >= rhsNum;
    case '<=': return num <= rhsNum;
    case '==': return Math.abs(num - rhsNum) < EPSILON;
    case '!=': return Math.abs(num - rhsNum) >= EPSILON;
    default: return false;
  }
}

/** Render band text for the first matching band. */
export function evaluateBands(
  interp: ValueInterpretation,
  value: string
): string {
  for (const band of interp.bands ?? []) {
    if (evaluateCondition(band.if, value)) {
      return band.text.replaceAll('${value}', applyTransform(value, interp.transform));
    }
  }
  return '';
}
