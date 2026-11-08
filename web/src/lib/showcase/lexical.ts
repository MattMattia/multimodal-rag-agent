/** Exact TypeScript port of `app/services/lexical.py`: bilingual (es/en) tokenizer and Okapi BM25. */

export const BM25_K1 = 1.5;
export const BM25_B = 0.75;

const TOKEN_RE = /[a-z0-9]+/g;
const VOWELS = "aeiou";
const COMBINING_MARK_RE = /\p{M}/gu;

const STOPWORDS: ReadonlySet<string> = new Set(
  (
    // español
    "a al algo ante como con contra cual cuando de del desde donde e el ella ellos en entre era es esta este esto " +
    "estos fue ha hay la las le les lo los mas me mi muy no nos o para pero por que se si sin sobre su sus te tu un " +
    "una uno unos y ya " +
    // inglés
    "an and are as at be been but by do does for from had has have how in is it its of on or that the their then " +
    "there these this to was were what when where which who why will with"
  ).split(" "),
);

function foldAccents(text: string): string {
  return text.toLowerCase().normalize("NFKD").replace(COMBINING_MARK_RE, "");
}

/** Light stemming for plurals and a final "e": ingresos→ingreso, controles→control, files→fil. */
function stem(input: string): string {
  let word = input;
  if (word.length > 4 && word.endsWith("ies")) {
    word = `${word.slice(0, -3)}y`;
  } else if (word.length > 4 && word.endsWith("es") && !VOWELS.includes(word.at(-3) ?? "")) {
    word = word.slice(0, -2);
  } else if (word.length > 3 && word.endsWith("s") && !word.endsWith("ss")) {
    word = word.slice(0, -1);
  }
  if (word.length > 4 && word.endsWith("e")) {
    word = word.slice(0, -1);
  }
  return word;
}

export function tokenize(text: string): string[] {
  if (!text) return [];
  const folded = foldAccents(text);
  return (folded.match(TOKEN_RE) ?? []).filter((tok) => !STOPWORDS.has(tok)).map(stem);
}

export function bm25Scores(queryTokens: readonly string[], documents: readonly (readonly string[])[]): number[] {
  const nDocs = documents.length;
  if (nDocs === 0 || queryTokens.length === 0) return new Array<number>(nDocs).fill(0);

  const avgLen = documents.reduce((sum, d) => sum + d.length, 0) / nDocs || 1;
  const terms = [...new Set(queryTokens)];
  const docFreq = new Map(terms.map((t) => [t, documents.filter((d) => d.includes(t)).length]));

  return documents.map((doc) => {
    let score = 0;
    for (const term of terms) {
      const tf = doc.filter((t) => t === term).length;
      if (!tf) continue;
      const df = docFreq.get(term) ?? 0;
      const idf = Math.log(1 + (nDocs - df + 0.5) / (df + 0.5));
      score += (idf * tf * (BM25_K1 + 1)) / (tf + BM25_K1 * (1 - BM25_B + (BM25_B * doc.length) / avgLen));
    }
    return score;
  });
}
