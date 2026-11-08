import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const staticDir = path.join(process.cwd(), ".next", "static");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? files(full) : [full];
  });
}

// Runs against the last production build; `npm run build` first (CI builds before testing this).
describe.skipIf(!existsSync(staticDir))("client bundle (.next/static)", () => {
  it("contains no server-only env names", () => {
    const leaks = files(staticDir).filter((file) => /API_KEY|FASTAPI_URL/.test(readFileSync(file, "utf8")));
    expect(leaks).toEqual([]);
  });
});
