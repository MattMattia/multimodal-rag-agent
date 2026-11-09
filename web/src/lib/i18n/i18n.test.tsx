// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageToggle } from "@/components/shell/LanguageToggle";
import { en } from "./en";
import { es } from "./es";
import { LocaleProvider, useLocale } from "./LocaleProvider";
import { LOCALE_STORAGE_KEY } from "./types";

/** Every key path of a dictionary; arrays contribute their length so both languages offer the same items. */
function keyPaths(value: unknown, prefix = ""): string[] {
  if (Array.isArray(value)) return [`${prefix}[${value.length}]`];
  if (typeof value === "function") return [`${prefix}()`];
  if (typeof value === "object" && value !== null) {
    return Object.entries(value).flatMap(([key, child]) => keyPaths(child, prefix ? `${prefix}.${key}` : key));
  }
  return [prefix];
}

function Probe() {
  const { locale, t } = useLocale();
  return (
    <p>
      {locale}:{t.shell.nav.knowledge}
    </p>
  );
}

const setNavigatorLanguage = (language: string) => vi.spyOn(window.navigator, "language", "get").mockReturnValue(language);

beforeEach(() => {
  localStorage.clear();
  document.documentElement.lang = "es";
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("dictionaries", () => {
  it("es and en define exactly the same keys (100% parity)", () => {
    const esKeys = keyPaths(es).sort();
    const enKeys = keyPaths(en).sort();
    expect(esKeys).toEqual(enKeys);
    expect(enKeys.length).toBeGreaterThan(100);
  });

  it("has no empty strings in either language", () => {
    const empty = (dict: unknown, path = ""): string[] =>
      typeof dict === "string"
        ? dict.trim()
          ? []
          : [path]
        : typeof dict === "object" && dict !== null
          ? Object.entries(dict).flatMap(([k, v]) => empty(v, `${path}.${k}`))
          : [];
    expect(empty(es)).toEqual([]);
    expect(empty(en)).toEqual([]);
  });
});

describe("LocaleProvider", () => {
  it("defaults to Spanish when the browser language is not English", () => {
    setNavigatorLanguage("fr-FR");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText("es:📚 Base de Conocimiento")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("es");
  });

  it("picks English when navigator.language starts with en", () => {
    setNavigatorLanguage("en-GB");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText("en:📚 Knowledge Base")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
  });

  it("prefers the stored choice over the browser language", () => {
    setNavigatorLanguage("en-US");
    localStorage.setItem(LOCALE_STORAGE_KEY, "es");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText("es:📚 Base de Conocimiento")).toBeInTheDocument();
  });

  it("keeps working when localStorage throws (private mode)", () => {
    setNavigatorLanguage("en-US");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText("en:📚 Knowledge Base")).toBeInTheDocument();
  });
});

describe("LanguageToggle", () => {
  it("toggles es <-> en, persists rag_locale and updates <html lang>", async () => {
    const user = userEvent.setup();
    localStorage.setItem(LOCALE_STORAGE_KEY, "es");
    render(
      <LocaleProvider>
        <LanguageToggle />
        <Probe />
      </LocaleProvider>,
    );
    const button = screen.getByRole("button", { name: es.shell.language.toggleLabel });
    expect(button).toHaveTextContent("🇪🇸 ES");
    expect(document.documentElement.lang).toBe("es");

    await user.click(button);
    expect(button).toHaveTextContent("🇺🇸 EN");
    expect(button).toHaveAccessibleName(en.shell.language.toggleLabel);
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(screen.getByText("en:📚 Knowledge Base")).toBeInTheDocument();

    await user.click(button);
    expect(button).toHaveTextContent("🇪🇸 ES");
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("es");
    expect(document.documentElement.lang).toBe("es");
  });
});
