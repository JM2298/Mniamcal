"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { buildBackendApiUrl, getBackendApiBaseUrl, resolveBackendAssetUrl } from "@/lib/backend-asset-url";

type BackendResponse = {
  CODE?: string;
  detail?: string;
  access?: string;
  refresh?: string;
  [key: string]: unknown;
};

type PaginatedResponse<T> = {
  results?: T[];
};

type DietItem = {
  id: number;
  dieta: string;
};

type MealPreview = {
  id: number;
  dieta_id: number;
  nazwa_posilku: string;
  zdjecie_url?: string | null;
  pora_posilku?: string;
  czas_przygotowania?: string;
  kalorie?: string;
};

async function parseBackendResponse(apiResponse: Response): Promise<BackendResponse> {
  const contentType = apiResponse.headers.get("content-type") || "";
  const rawBody = await apiResponse.text();

  if (!rawBody) {
    return {};
  }

  if (contentType.includes("application/json")) {
    return JSON.parse(rawBody) as BackendResponse;
  }

  try {
    return JSON.parse(rawBody) as BackendResponse;
  } catch {
    const snippet = rawBody.replace(/\s+/g, " ").trim().slice(0, 180);
    throw new Error(
      `Backend zwrocil nie-JSON (HTTP ${apiResponse.status}). Fragment odpowiedzi: ${snippet || "pusta odpowiedz"}.`,
    );
  }
}

function toUserFriendlyErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] = useState<BackendResponse | null>(null);
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [previewMeals, setPreviewMeals] = useState<MealPreview[]>([]);
  const [dietNamesById, setDietNamesById] = useState<Record<number, string>>({});
  const [previewLoading, setPreviewLoading] = useState(true);
  const [previewError, setPreviewError] = useState("");

  const backendApiBaseUrl = useMemo(() => getBackendApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL), []);

  const loginUrl = useMemo(() => {
    return buildBackendApiUrl("/api/auth/login/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const registerUrl = useMemo(() => {
    return buildBackendApiUrl("/api/auth/register/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const tokenRefreshUrl = useMemo(() => {
    return buildBackendApiUrl("/api/auth/token/refresh/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const dietsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/diets/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const dietMealsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/diets/meals/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  useEffect(() => {
    let cancelled = false;

    const fetchPreviewData = async () => {
      setPreviewLoading(true);
      setPreviewError("");

      try {
        const [dietsResponse, mealsResponse] = await Promise.all([
          fetch(dietsUrl),
          fetch(`${dietMealsUrl}?limit=24`),
        ]);

        if (!dietsResponse.ok || !mealsResponse.ok) {
          throw new Error("Nie udalo sie pobrac przykladowych posilkow.");
        }

        const dietsPayload = (await dietsResponse.json()) as PaginatedResponse<DietItem>;
        const mealsPayload = (await mealsResponse.json()) as PaginatedResponse<MealPreview>;

        if (cancelled) {
          return;
        }

        const diets = dietsPayload.results ?? [];
        const meals = mealsPayload.results ?? [];
        const namesById = diets.reduce<Record<number, string>>((acc, diet) => {
          acc[diet.id] = diet.dieta;
          return acc;
        }, {});

        setDietNamesById(namesById);
        setPreviewMeals(meals.slice(0, 6));
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Nieznany blad pobierania posilkow.";
          setPreviewError(message);
        }
      } finally {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      }
    };

    void fetchPreviewData();

    return () => {
      cancelled = true;
    };
  }, [dietsUrl, dietMealsUrl]);

  const persistTokens = (payload: BackendResponse) => {
    if (payload.access) {
      localStorage.setItem("access_token", payload.access);
    }
    if (payload.refresh) {
      localStorage.setItem("refresh_token", payload.refresh);
    }
  };

  const onLogin = async () => {
    setLoading(true);
    setError("");

    try {
      const trimmedUsername = username.trim();
      if (!trimmedUsername || !password) {
        throw new Error("Podaj nazwe uzytkownika i haslo.");
      }

      const apiResponse = await fetch(loginUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: trimmedUsername, password }),
      });

      const payload = await parseBackendResponse(apiResponse);
      setResponse(payload);

      if (!apiResponse.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${apiResponse.status}.`);
      }

      persistTokens(payload);
      router.push("/dashboard");
    } catch (err) {
      const message = toUserFriendlyErrorMessage(err, "Nieznany blad logowania.");
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async () => {
    setLoading(true);
    setError("");

    try {
      const trimmedUsername = username.trim();
      const trimmedFirstName = firstName.trim();
      if (!trimmedUsername || !trimmedFirstName || !password) {
        throw new Error("Podaj nazwe uzytkownika, imie i haslo.");
      }

      const apiResponse = await fetch(registerUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: trimmedUsername,
          first_name: trimmedFirstName,
          email: email.trim(),
          password,
        }),
      });

      const payload = await parseBackendResponse(apiResponse);
      setResponse(payload);

      if (!apiResponse.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${apiResponse.status}.`);
      }

      persistTokens(payload);
      router.push("/dashboard");
    } catch (err) {
      const message = toUserFriendlyErrorMessage(err, "Nieznany blad rejestracji.");
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const onRefreshAccessToken = async () => {
    setLoading(true);
    setError("");

    try {
      const refreshToken = localStorage.getItem("refresh_token");

      if (!refreshToken) {
        throw new Error("Brak refresh token. Zaloguj sie ponownie.");
      }

      const apiResponse = await fetch(tokenRefreshUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      });

      const payload = await parseBackendResponse(apiResponse);
      setResponse(payload);

      if (!apiResponse.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${apiResponse.status}.`);
      }

      persistTokens(payload);
    } catch (err) {
      const message = toUserFriendlyErrorMessage(err, "Nieznany blad odswiezania tokenu.");
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <section className="mx-auto mt-8 w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold">Logowanie do backendu</h1>
        <p className="mt-2 text-sm text-slate-600">
          Logowanie i rejestracja odbywaja sie bezposrednio przez endpointy backendu Django (bez Google).
        </p>

        <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          Endpoint logowania: {loginUrl}
        </div>
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          Endpoint rejestracji: {registerUrl}
        </div>
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          Endpoint odswiezania: {tokenRefreshUrl}
        </div>

        <div className="mt-5 grid gap-3 rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm font-semibold text-slate-800">Dane logowania</p>
          <input
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Nazwa uzytkownika"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            type="text"
            value={firstName}
            onChange={(event) => setFirstName(event.target.value)}
            placeholder="Imie (wymagane przy rejestracji)"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="email@example.com (opcjonalny przy logowaniu)"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Haslo"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />

          <button
            type="button"
            onClick={onLogin}
            disabled={loading}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Logowanie..." : "Zaloguj"}
          </button>

          <button
            type="button"
            onClick={onRegister}
            disabled={loading}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Rejestracja..." : "Zarejestruj"}
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRefreshAccessToken}
            disabled={loading}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Odswiezanie..." : "Odswiez token"}
          </button>

          <button
            type="button"
            onClick={() => {
              setResponse(null);
              setError("");
              localStorage.removeItem("access_token");
              localStorage.removeItem("refresh_token");
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            Wyczysc
          </button>
        </div>

        {error ? <p className="mt-4 text-sm font-semibold text-red-700">{error}</p> : null}

        <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
          {response ? JSON.stringify(response, null, 2) : "Odpowiedz backendu pojawi sie tutaj."}
        </pre>
      </section>

      <section className="mx-auto mt-6 w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Przykladowe posilki dla diet</h2>
        <p className="mt-2 text-sm text-slate-600">
          Na stronie glownej pokazujemy tylko podglad. Szczegoly posilkow sa dostepne dopiero po zalogowaniu.
        </p>

        {previewLoading ? <p className="mt-4 text-sm text-slate-600">Ladowanie przykladowych posilkow...</p> : null}
        {previewError ? <p className="mt-4 text-sm font-semibold text-red-700">{previewError}</p> : null}

        {!previewLoading && !previewError ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {previewMeals.map((meal) => {
              const imageUrl = resolveBackendAssetUrl(meal.zdjecie_url, process.env.NEXT_PUBLIC_API_BASE_URL);

              return (
                <article key={meal.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={meal.nazwa_posilku}
                      className="mb-3 h-40 w-full rounded-lg object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="mb-3 flex h-40 w-full items-center justify-center rounded-lg bg-slate-200 text-xs font-semibold text-slate-600">
                      Brak zdjecia posilku
                    </div>
                  )}
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {dietNamesById[meal.dieta_id] ?? `Dieta #${meal.dieta_id}`}
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-slate-900">{meal.nazwa_posilku}</h3>
                  <p className="mt-2 text-sm text-slate-700">Pora: {meal.pora_posilku || "brak danych"}</p>
                  <p className="text-sm text-slate-700">Czas: {meal.czas_przygotowania || "brak danych"}</p>
                  <p className="text-sm text-slate-700">Kalorie: {meal.kalorie || "brak danych"}</p>
                  <p className="mt-3 text-xs font-semibold text-amber-700">Zaloguj sie, aby wejsc w szczegoly posilku.</p>
                </article>
              );
            })}
          </div>
        ) : null}
      </section>
    </main>
  );
}
