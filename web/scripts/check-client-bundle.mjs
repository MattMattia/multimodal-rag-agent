// Fails when a server-only secret name leaks into the client bundle (`.next/static`). Run after `next build`.
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const FORBIDDEN = ["API_KEY", "FASTAPI_URL", "NEXT_PUBLIC_API_KEY"];
const root = path.join(process.cwd(), ".next", "static");

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else yield full;
  }
}

const leaks = [];
try {
  for await (const file of walk(root)) {
    const text = await readFile(file, "utf8");
    for (const needle of FORBIDDEN) if (text.includes(needle)) leaks.push(`${path.relative(root, file)}: ${needle}`);
  }
} catch (error) {
  console.error(`Cannot scan ${root}: run "npm run build" first.`, error.message);
  process.exit(2);
}

if (leaks.length) {
  console.error(`Server-only names found in the client bundle:\n${leaks.join("\n")}`);
  process.exit(1);
}
console.log("Client bundle clean: no server-only names in .next/static.");
