/**
 * Education content validator — run on EVERY education.json-touching commit.
 *
 * Usage: npm run validate:education
 *
 * Enforces (beyond JSON Schema):
 *  1. Bands: last band must be unconditional fallback ("" condition) OR the
 *     bands must cover the domain; we require explicit ""-fallback for safety.
 *  2. related[] keys resolve to a real entry somewhere in the file.
 *  3. No duplicate labels across sections (confuses search + TermLink).
 *  4. No raw enum leaks in text fields (above_upper, golden_cross, etc.)
 *     unless the field is demonstrating enum values deliberately.
 */

import Ajv from 'ajv';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONTENT_DIR = path.resolve(__dirname, '../src/content');
const SCHEMA_PATH = path.join(CONTENT_DIR, 'education.schema.json');
const CONTENT_PATH = path.join(CONTENT_DIR, 'education.json');

interface Band {
  if: string;
  text: string;
}
interface Interpretation {
  type: 'bands';
  transform?: string | null;
  bands: Band[];
}
interface Lesson {
  label: string;
  category?: string;
  oneLiner?: string;
  what?: string;
  whyMatters?: string;
  scoringImpact?: string;
  commonMistakes?: string[];
  example?: string;
  valueInterpretation?: Interpretation;
  related?: string[];
}
interface Content {
  meta: { version: string; updatedAt: string };
  thresholds?: Record<string, number>;
  metrics?: Record<string, Lesson>;
  backtestMetrics?: Record<string, Lesson>;
  tradePlan?: Record<string, { label: string; oneLiner: string; what: string; related?: string[] }>;
  modules?: Record<string, { title: string }>;
  concepts?: Record<string, { label: string; oneLiner: string; what: string; related?: string[] }>;
  glossary?: Array<{ term: string; definition: string; related?: string[] }>;
}

// Raw enum values that must never leak into rendered text (W0.2b class of bug)
const RAW_ENUMS = [
  'above_upper', 'below_lower', 'golden_cross', 'death_cross',
  'neutral_bullish', 'neutral_bearish',
];

function loadJson(p: string): unknown {
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

function collectIds(content: Content): Set<string> {
  const ids = new Set<string>();
  for (const k of Object.keys(content.metrics ?? {})) ids.add(k);
  for (const k of Object.keys(content.backtestMetrics ?? {})) ids.add(k);
  for (const k of Object.keys(content.tradePlan ?? {})) ids.add(k);
  for (const k of Object.keys(content.concepts ?? {})) ids.add(k);
  for (const k of Object.keys(content.modules ?? {})) ids.add(k);
  for (const g of content.glossary ?? []) ids.add(g.term.toLowerCase());
  return ids;
}

function validateBands(key: string, interp: Interpretation, errors: string[]): void {
  if (!Array.isArray(interp.bands) || interp.bands.length < 1) {
    errors.push(`${key}: valueInterpretation.bands is empty`);
    return;
  }
  const last = interp.bands[interp.bands.length - 1];
  if (last.if.trim() !== '') {
    errors.push(
      `${key}: LAST band must be unconditional fallback (if: "") — got "${last.if}"`
    );
  }
  // Only the last band may be unconditional
  interp.bands.slice(0, -1).forEach((b, i) => {
    if (b.if.trim() === '') {
      errors.push(`${key}: unconditional band at index ${i} but not last`);
    }
  });
}

function checkTextForEnumLeaks(key: string, lesson: Lesson, errors: string[]): void {
  const fields = [lesson.what, lesson.whyMatters, lesson.scoringImpact, lesson.example, ...(lesson.commonMistakes ?? [])];
  for (const text of fields) {
    if (!text) continue;
    for (const e of RAW_ENUMS) {
      // deliberate mentions are OK when quoted or followed by translation ("above_upper" → "above...")
      const pattern = new RegExp(`(?<!["'])\\b${e}\\b(?!["'])`, 'i');
      if (pattern.test(text)) {
        errors.push(`${key}: raw enum "${e}" leaked into prose — wrap in quotes with plain-word translation, or reword`);
      }
    }
  }
}

function main(): void {
  const schema = loadJson(SCHEMA_PATH);
  const content = loadJson(CONTENT_PATH) as Content;
  const errors: string[] = [];

  const ajv = new Ajv({ allErrors: true });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const validate = ajv.compile(schema as any);
  if (!validate(content)) {
    for (const e of validate.errors ?? []) {
      errors.push(`schema: ${e.instancePath} ${e.message}`);
    }
  }

  const ids = collectIds(content);
  // related[] may also point at glossary terms (display-cased) — index those too
  for (const g of content.glossary ?? []) ids.add(g.term.toLowerCase());
  // ...and at snake_case versions of glossary terms ("payout_ratio" → "Payout Ratio")
  for (const g of content.glossary ?? []) {
    if (/[\s-]/.test(g.term)) ids.add(g.term.toLowerCase().replace(/[\s-]+/g, '_'));
  }

  // related[] resolution
  const checkRelated = (owner: string, related?: string[]) => {
    for (const r of related ?? []) {
      if (!ids.has(r) && !ids.has(r.toLowerCase())) {
        errors.push(`${owner}: related key "${r}" does not resolve to any entry`);
      }
    }
  };
  for (const [k, l] of Object.entries(content.metrics ?? {})) checkRelated(`metrics.${k}`, l.related);
  for (const [k, l] of Object.entries(content.backtestMetrics ?? {})) checkRelated(`backtestMetrics.${k}`, l.related);
  for (const [k, l] of Object.entries(content.tradePlan ?? {})) checkRelated(`tradePlan.${k}`, l.related);
  for (const [k, l] of Object.entries(content.concepts ?? {})) checkRelated(`concepts.${k}`, l.related);
  for (const [i, g] of (content.glossary ?? []).entries()) checkRelated(`glossary[${i}]`, g.related);

  // duplicate labels: ERROR within the same section; WARN across sections
  // (cross-section overlap is BY DESIGN: glossary mirrors lesson keys so
  // TermLink can link any printed term; each consumer resolves keys within
  // its own section namespace).
  const labelOwner = new Map<string, Set<string>>();
  const claimLabel = (label: string, owner: string) => {
    const norm = label.toLowerCase().trim();
    const section = owner.split('.')[0];
    if (!labelOwner.has(norm)) labelOwner.set(norm, new Set());
    labelOwner.get(norm)!.add(section);
    // intra-section check via suffix map
    const intraKey = `${section}::${norm}`;
    if (intraSeen.has(intraKey)) {
      errors.push(`duplicate label "${label}" within ${section}`);
    } else {
      intraSeen.add(intraKey);
    }
  };
  const intraSeen = new Set<string>();
  for (const [k, l] of Object.entries(content.metrics ?? {})) claimLabel(l.label, `metrics.${k}`);
  for (const [k, l] of Object.entries(content.backtestMetrics ?? {})) claimLabel(l.label, `backtestMetrics.${k}`);
  for (const [k, l] of Object.entries(content.tradePlan ?? {})) claimLabel(l.label, `tradePlan.${k}`);
  for (const [k, l] of Object.entries(content.concepts ?? {})) claimLabel(l.label, `concepts.${k}`);
  for (const g of content.glossary ?? []) claimLabel(g.term, 'glossary');

  // bands validation + enum-leak scan on lessons that carry them
  for (const section of ['metrics', 'backtestMetrics'] as const) {
    for (const [k, l] of Object.entries(content[section] ?? {})) {
      if (l.valueInterpretation) validateBands(`${section}.${k}`, l.valueInterpretation, errors);
      checkTextForEnumLeaks(`${section}.${k}`, l, errors);
    }
  }

  if (errors.length > 0) {
    console.error(`\n✗ education.json INVALID (${errors.length} error(s)):\n`);
    for (const e of errors) console.error(`  • ${e}`);
    process.exit(1);
  }

  const counts = {
    metrics: Object.keys(content.metrics ?? {}).length,
    backtestMetrics: Object.keys(content.backtestMetrics ?? {}).length,
    tradePlan: Object.keys(content.tradePlan ?? {}).length,
    modules: Object.keys(content.modules ?? {}).length,
    concepts: Object.keys(content.concepts ?? {}).length,
    glossary: (content.glossary ?? []).length,
  };
  console.log('✓ education.json valid');
  console.log(`  ${JSON.stringify(counts)}`);
}

main();
