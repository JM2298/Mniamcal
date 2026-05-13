"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { buildBackendApiUrl, getBackendApiBaseUrl, resolveBackendAssetUrl } from "@/lib/backend-asset-url";
import { getFirebaseApp } from "@/lib/firebase-client";

type TabKey = "tablica" | "diety" | "kalendarz" | "lista-zakupow" | "magazyn" | "konto";

type PaginatedResponse<T> = {
  count?: number;
  results?: T[];
  previous?: string | null;
  next?: string | null;
};

type DietItem = {
  id: number;
  dieta: string;
  opis_diety?: string;
};

type DietCalorieItem = {
  id: number;
  dieta_id: number;
  kalorycznosc_id?: number;
  kalorycznosc?: string;
  czysta_kalorycznosc?: number;
};

type IngredientItem = {
  nazwa_produktu: string;
  ilosc_produktu: string;
  miarka: string;
};

type MealItem = {
  id: number;
  dieta_id: number;
  nazwa_posilku: string;
  zdjecie_url?: string | null;
  skladniki?: IngredientItem[];
  cena_posilku?: string | null;
  brakujace_ceny_produktow?: string | null;
  pora_posilku?: string;
  czas_przygotowania?: string;
  kalorie?: string;
  bialko?: string;
  weglowodany?: string;
  tluszcze?: string;
  opis_posilku?: string;
};

type MealFilters = {
  nazwaPosilku: string;
  poraPosilku: string;
  czasPrzygotowania: string;
  czasPrzygotowaniaMaxMinut: string;
  czystaKalorycznosc: string;
  sortowanieCena: "" | "najtansze" | "najdrozsze";
};

type AuthMeResponse = {
  id: number;
  username: string;
  first_name?: string;
  email?: string;
  rodzina_id?: number | null;
  kalorycznosc_diety_id?: number | null;
  dieta_id?: number | null;
};

type FamilyCreateResponse = {
  id?: number;
  rodzina?: string;
  detail?: string;
};

type FamilyInviteResponse = {
  rodzina_id?: number;
  rodzina?: string;
  email?: string;
  detail?: string;
};

type FamilyMember = {
  id: number;
  username: string;
  first_name?: string;
  email?: string;
  is_founder: boolean;
  dieta?: string | null;
  kalorycznosc?: string | null;
  czysta_kalorycznosc?: number | null;
};

type FamilyMembersResponse = {
  rodzina_id?: number;
  rodzina?: string;
  members?: FamilyMember[];
  detail?: string;
};

type PlannedMealResponse = {
  planned_meal_id?: number;
  data?: string;
  czy_zjedzone?: boolean;
  pora_posilku?: string;
  rodzina_id?: number;
  liczba_czlonkow_rodziny?: number;
  liczba_osob_przy_posilku?: number;
  zaplanowane_posilki?: Array<{
    uzytkownik_id: number;
    uzytkownik_w_rodzinie_id: number;
    posilek_w_diecie_id: number;
    kalorycznosc_diety?: number | null;
    proporcja_kaloryczna?: number;
  }>;
  detail?: string;
};

type ShoppingListSummary = {
  id: number;
  nazwa_listy_zakupow: string;
  data_od: string;
  data_do: string;
  liczba_pozycji_na_liscie: number;
};

type ShoppingListDetailProduct = {
  produkt_id: number;
  nazwa_produktu: string;
  ilosc_produktu_do_kupienia: string;
  kolejnosc_kategorii?: number | null;
  kategoria_nazwa?: string | null;
};

type ShoppingListDetailResponse = {
  id: number;
  nazwa_listy_zakupow: string;
  rodzina_id: number;
  data_od: string;
  data_do: string;
  liczba_pozycji_na_liscie: number;
  produkty: ShoppingListDetailProduct[];
  detail?: string;
};

type SimplifiedProductItem = {
  id: number;
  nazwa_produktu_uproszczonego: string;
};

type ShoppingListCreateResponse = {
  lista_zakupow_id?: number;
  nazwa_listy_zakupow?: string;
  rodzina_id?: number;
  data_od?: string;
  data_do?: string;
  liczba_zaplanowanych_posilkow?: number;
  liczba_pozycji_na_liscie?: number;
  detail?: string;
};

type WarehouseProduct = {
  produkt_id: number;
  nazwa_produktu: string;
  ilosc_produktu: number;
};

type WarehouseResponse = {
  rodzina_id?: number;
  liczba_pozycji?: number;
  produkty?: WarehouseProduct[];
  detail?: string;
};

type WarehouseCoverageResponse = {
  total_planned_meals?: number;
  covered_meals?: number;
  uncovered_meals?: number;
  coverage_percent?: number;
  detail?: string;
};

type PossibleMeal = {
  posilek_w_diecie_id: number;
  nazwa_posilku: string;
  pora_posilku?: string;
  czas_przygotowania?: string;
  liczba_skladnikow?: number;
  coverage_percent?: number;
  can_prepare?: boolean;
};

type PossibleMealsResponse = {
  liczba_mozliwych_posilkow?: number;
  mozliwe_posilki?: PossibleMeal[];
  detail?: string;
};

const getMealTimeOrder = (mealTime?: string | null): number => {
  const normalized = String(mealTime || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

  if (normalized.includes("sniadanie") && !normalized.includes("drugie")) {
    return 1;
  }
  if (normalized.includes("drugie sniadanie")) {
    return 2;
  }
  if (normalized.includes("obiad")) {
    return 3;
  }
  if (normalized.includes("podwieczorek")) {
    return 4;
  }
  if (normalized.includes("kolacja")) {
    return 5;
  }
  return 99;
};

const formatDateForInput = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const getTodayDateForInput = (): string => formatDateForInput(new Date());

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "tablica", label: "TABLICA" },
  { key: "diety", label: "DIETY" },
  { key: "kalendarz", label: "KALENDARZ" },
  { key: "lista-zakupow", label: "LISTA ZAKUPOW" },
  { key: "magazyn", label: "MAGAZYN" },
  { key: "konto", label: "KONTO" },
];

export default function DashboardPage() {
  const router = useRouter();
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>("diety");
  const [notificationsConsent, setNotificationsConsent] = useState(false);
  const [accountMessage, setAccountMessage] = useState("");
  const [savingNotifications, setSavingNotifications] = useState(false);
  const [savingUserDiet, setSavingUserDiet] = useState(false);
  const [creatingFamily, setCreatingFamily] = useState(false);
  const [sendingFamilyInvite, setSendingFamilyInvite] = useState(false);
  const [leavingFamily, setLeavingFamily] = useState(false);
  const [familyName, setFamilyName] = useState("");
  const [familyInviteEmail, setFamilyInviteEmail] = useState("");
  const [familyMessage, setFamilyMessage] = useState("");
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [familyNameOverview, setFamilyNameOverview] = useState("");
  const [familyOverviewLoading, setFamilyOverviewLoading] = useState(false);
  const [familyOverviewError, setFamilyOverviewError] = useState("");
  const [userDietInitialized, setUserDietInitialized] = useState(false);
  const [preferredDietId, setPreferredDietId] = useState<number | null>(null);
  const [preferredDietCalorieId, setPreferredDietCalorieId] = useState<number | null>(null);
  const [accountSelectedDietId, setAccountSelectedDietId] = useState<number | null>(null);
  const [accountSelectedDietCalorieId, setAccountSelectedDietCalorieId] = useState<number | null>(null);
  const [diets, setDiets] = useState<DietItem[]>([]);
  const [meals, setMeals] = useState<MealItem[]>([]);
  const [mealsCount, setMealsCount] = useState(0);
  const [mealsPage, setMealsPage] = useState(1);
  const [dietsLoading, setDietsLoading] = useState(false);
  const [dietsError, setDietsError] = useState("");
  const [caloriesByDietId, setCaloriesByDietId] = useState<Record<number, DietCalorieItem[]>>({});
  const [mealsLoading, setMealsLoading] = useState(false);
  const [mealsError, setMealsError] = useState("");
  const [selectedDietId, setSelectedDietId] = useState<number | null>(null);
  const [expandedDietId, setExpandedDietId] = useState<number | null>(null);
  const [selectedDietCalorieId, setSelectedDietCalorieId] = useState<number | null>(null);
  const [selectedMealId, setSelectedMealId] = useState<number | null>(null);
  const [mealFilters, setMealFilters] = useState<MealFilters>({
    nazwaPosilku: "",
    poraPosilku: "",
    czasPrzygotowania: "",
    czasPrzygotowaniaMaxMinut: "",
    czystaKalorycznosc: "",
    sortowanieCena: "",
  });
  const [plannedMealDate, setPlannedMealDate] = useState(() => getTodayDateForInput());
  const [plannedMealId, setPlannedMealId] = useState("");
  const [planningMeal, setPlanningMeal] = useState(false);
  const [calendarMessage, setCalendarMessage] = useState("");
  const [createdPlannedMeal, setCreatedPlannedMeal] = useState<PlannedMealResponse | null>(null);
  const [shoppingListFromDate, setShoppingListFromDate] = useState(() => getTodayDateForInput());
  const [shoppingListToDate, setShoppingListToDate] = useState(() => getTodayDateForInput());
  const [shoppingListName, setShoppingListName] = useState("");
  const [creatingShoppingList, setCreatingShoppingList] = useState(false);
  const [shoppingMessage, setShoppingMessage] = useState("");
  const [shoppingLists, setShoppingLists] = useState<ShoppingListSummary[]>([]);
  const [shoppingListsLoading, setShoppingListsLoading] = useState(false);
  const [shoppingListsError, setShoppingListsError] = useState("");
  const [selectedShoppingListId, setSelectedShoppingListId] = useState<number | null>(null);
  const [selectedShoppingListDetail, setSelectedShoppingListDetail] = useState<ShoppingListDetailResponse | null>(null);
  const [shoppingListDetailLoading, setShoppingListDetailLoading] = useState(false);
  const [shoppingListDetailError, setShoppingListDetailError] = useState("");
  const [markingBoughtProductId, setMarkingBoughtProductId] = useState<number | null>(null);
  const [markingAllBought, setMarkingAllBought] = useState(false);
  const [warehouse, setWarehouse] = useState<WarehouseResponse | null>(null);
  const [warehouseCoverage, setWarehouseCoverage] = useState<WarehouseCoverageResponse | null>(null);
  const [possibleMeals, setPossibleMeals] = useState<PossibleMeal[]>([]);
  const [warehouseLoading, setWarehouseLoading] = useState(false);
  const [warehouseMessage, setWarehouseMessage] = useState("");
  const [warehouseProductId, setWarehouseProductId] = useState("");
  const [warehouseProductSearch, setWarehouseProductSearch] = useState("");
  const [warehouseSearchResults, setWarehouseSearchResults] = useState<SimplifiedProductItem[]>([]);
  const [warehouseSearchLoading, setWarehouseSearchLoading] = useState(false);
  const [warehouseProductAmount, setWarehouseProductAmount] = useState("");
  const [selectedWarehouseProductId, setSelectedWarehouseProductId] = useState<number | null>(null);
  const [mealToScheduleId, setMealToScheduleId] = useState<number | null>(null);
  const [mealScheduleDate, setMealScheduleDate] = useState(() => getTodayDateForInput());
  const [mealSchedulingLoading, setMealSchedulingLoading] = useState(false);
  const [mealSchedulingMessage, setMealSchedulingMessage] = useState("");
  const [calendarViewDate, setCalendarViewDate] = useState(() => getTodayDateForInput());
  const [calendarPlannedMeals, setCalendarPlannedMeals] = useState<Record<string, PlannedMealResponse[]>>({});
  const [calendarMealsLoading, setCalendarMealsLoading] = useState(false);
  const [calendarMealRemoving, setCalendarMealRemoving] = useState(false);
  const [calendarMealMarkingEaten, setCalendarMealMarkingEaten] = useState(false);
  const [calendarShoppingListCreating, setCalendarShoppingListCreating] = useState(false);
  const [calendarPdfFromDate, setCalendarPdfFromDate] = useState(() => getTodayDateForInput());
  const [calendarPdfToDate, setCalendarPdfToDate] = useState(() => getTodayDateForInput());
  const [calendarPdfGenerating, setCalendarPdfGenerating] = useState(false);
  const [selectedCalendarMeal, setSelectedCalendarMeal] = useState<{date: string; meal: PlannedMealResponse} | null>(null);
  const [selectedCalendarMealDetailId, setSelectedCalendarMealDetailId] = useState<number | null>(null);
  const [mealDetailById, setMealDetailById] = useState<Record<number, MealItem>>({});
  const [calendarMemberNameByUserId, setCalendarMemberNameByUserId] = useState<Record<number, string>>({});
  const mealsPageSize = 10;

  const backendApiBaseUrl = useMemo(() => getBackendApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL), []);

  const fcmDeviceUrl = useMemo(() => {
    return buildBackendApiUrl("/api/fcm/devices/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const authMeUrl = useMemo(() => {
    return buildBackendApiUrl("/api/auth/me/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const familyMembershipDietUrl = useMemo(() => {
    return buildBackendApiUrl("/api/families/my-membership/diet/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const familiesUrl = useMemo(() => {
    return buildBackendApiUrl("/api/families/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const familyInvitationsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/family-invitations/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const familyMembersUrl = useMemo(() => {
    return buildBackendApiUrl("/api/families/members/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const familyLeaveUrl = useMemo(() => {
    return buildBackendApiUrl("/api/families/leave/", backendApiBaseUrl);
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

  const dietCaloriesUrl = useMemo(() => {
    return buildBackendApiUrl("/api/diets/calories/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const calendarPlannedMealsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/calendar/family-planned-meals/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);
  const calendarPlannedMealRemoveUrl = useMemo(() => {
    return buildBackendApiUrl("/api/calendar/family-planned-meals/remove/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);
  const calendarPlannedMealMarkEatenUrl = useMemo(() => {
    return buildBackendApiUrl("/api/calendar/family-planned-meals/mark-eaten/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const shoppingListsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/shopping-lists/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const shoppingListFromCalendarUrl = useMemo(() => {
    return buildBackendApiUrl("/api/shopping-lists/from-calendar/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);
  const shoppingListMarkBoughtUrl = useMemo(() => {
    return buildBackendApiUrl("/api/shopping-lists/products/mark-bought/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);
  const simplifiedProductsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/products/simplified/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const warehouseUrl = useMemo(() => {
    return buildBackendApiUrl("/api/warehouse/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const warehouseCoverageUrl = useMemo(() => {
    return buildBackendApiUrl("/api/warehouse/meal-coverage/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const warehousePossibleMealsUrl = useMemo(() => {
    return buildBackendApiUrl("/api/warehouse/possible-meals/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const warehouseClearUrl = useMemo(() => {
    return buildBackendApiUrl("/api/warehouse/clear/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const warehouseUpdateProductUrl = useMemo(() => {
    return buildBackendApiUrl("/api/warehouse/update-product/", backendApiBaseUrl);
  }, [backendApiBaseUrl]);

  const redirectToLogin = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    router.replace("/");
  }, [router]);

  const refreshAccessToken = useCallback(async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      return null;
    }

    const response = await fetch(tokenRefreshUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    const rawBody = await response.text();
    let payload: { access?: string; refresh?: string } | null = null;
    try {
      payload = rawBody ? (JSON.parse(rawBody) as { access?: string; refresh?: string }) : null;
    } catch {
      payload = null;
    }

    if (!response.ok || !payload?.access) {
      return null;
    }

    localStorage.setItem("access_token", payload.access);
    if (payload.refresh) {
      localStorage.setItem("refresh_token", payload.refresh);
    }

    return payload.access;
  }, [tokenRefreshUrl]);

  const fetchWithAuth = useCallback(async (url: string, init?: RequestInit) => {
    const makeRequest = async (token: string) => {
      return fetch(url, {
        ...init,
        headers: {
          ...(init?.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      });
    };

    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
      redirectToLogin();
      throw new Error("Sesja wygasla. Zaloguj sie ponownie.");
    }

    let response = await makeRequest(accessToken);
    if (response.status !== 401) {
      return response;
    }

    const authErrorBody = await response.clone().text();
    const shouldRefresh =
      /token_not_valid|Given token not valid for any token type|NOT_AUTHENTICATED/i.test(authErrorBody);

    if (!shouldRefresh) {
      return response;
    }

    const refreshedAccessToken = await refreshAccessToken();
    if (!refreshedAccessToken) {
      redirectToLogin();
      throw new Error("Sesja wygasla. Zaloguj sie ponownie.");
    }

    response = await makeRequest(refreshedAccessToken);
    if (response.status === 401) {
      redirectToLogin();
      throw new Error("Sesja wygasla. Zaloguj sie ponownie.");
    }

    return response;
  }, [redirectToLogin, refreshAccessToken]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/");
    }

    setNotificationsConsent(localStorage.getItem("notifications_consent") === "1");
    const savedTheme = localStorage.getItem("theme_mode");
    const shouldUseDark =
      savedTheme === "dark" ||
      (!savedTheme && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setIsDarkMode(shouldUseDark);
    document.documentElement.classList.toggle("dark", shouldUseDark);
  }, [router]);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => {
      const next = !prev;
      localStorage.setItem("theme_mode", next ? "dark" : "light");
      document.documentElement.classList.toggle("dark", next);
      return next;
    });
  };

  useEffect(() => {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
      setUserDietInitialized(true);
      return;
    }

    let cancelled = false;

    const fetchProfile = async () => {
      try {
        const response = await fetchWithAuth(authMeUrl);

        if (!response.ok) {
          throw new Error("Nie udalo sie pobrac profilu uzytkownika.");
        }

        const payload = (await response.json()) as AuthMeResponse;
        if (cancelled) {
          return;
        }

        setPreferredDietId(payload.dieta_id ?? null);
        setPreferredDietCalorieId(payload.kalorycznosc_diety_id ?? null);
        setAccountSelectedDietId(payload.dieta_id ?? null);
        setAccountSelectedDietCalorieId(payload.kalorycznosc_diety_id ?? null);
      } catch {
        if (!cancelled) {
          setPreferredDietId(null);
          setPreferredDietCalorieId(null);
        }
      } finally {
        if (!cancelled) {
          setUserDietInitialized(true);
        }
      }
    };

    void fetchProfile();

    return () => {
      cancelled = true;
    };
  }, [authMeUrl, fetchWithAuth]);

  useEffect(() => {
    if (activeTab !== "tablica" && activeTab !== "konto") {
      return;
    }

    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
      setFamilyMembers([]);
      setFamilyNameOverview("");
      setFamilyOverviewError("");
      return;
    }

    let cancelled = false;

    const fetchFamilyOverview = async () => {
      setFamilyOverviewLoading(true);
      setFamilyOverviewError("");

      try {
        const response = await fetchWithAuth(familyMembersUrl);

        const payload = (await response.json()) as FamilyMembersResponse & { CODE?: string };

        if (cancelled) {
          return;
        }

        if (!response.ok) {
          if (response.status === 404 || payload.CODE === "FAMILY_NOT_FOUND") {
            setFamilyMembers([]);
            setFamilyNameOverview("");
            setFamilyOverviewError("");
            return;
          }
          throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
        }

        setFamilyMembers(payload.members ?? []);
        setFamilyNameOverview(payload.rodzina ?? "");
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Nie udalo sie pobrac danych rodziny.";
          setFamilyOverviewError(message);
        }
      } finally {
        if (!cancelled) {
          setFamilyOverviewLoading(false);
        }
      }
    };

    void fetchFamilyOverview();

    return () => {
      cancelled = true;
    };
  }, [activeTab, familyMembersUrl, fetchWithAuth]);

  useEffect(() => {
    if (activeTab !== "diety" && activeTab !== "konto") {
      return;
    }

    let cancelled = false;

    const fetchAllPages = async <T,>(initialUrl: string): Promise<T[]> => {
      const allResults: T[] = [];
      let nextUrl: string | null = buildBackendApiUrl(initialUrl, backendApiBaseUrl);

      while (nextUrl) {
        const response = await fetch(nextUrl);
        if (!response.ok) {
          throw new Error(`Nie udalo sie pobrac danych (HTTP ${response.status}).`);
        }

        const payload = (await response.json()) as PaginatedResponse<T>;
        allResults.push(...(payload.results ?? []));
        nextUrl = payload.next ? buildBackendApiUrl(payload.next, backendApiBaseUrl) : null;
      }

      return allResults;
    };

    const fetchDiets = async () => {
      setDietsLoading(true);
      setDietsError("");

      try {
        const [fetchedDiets, fetchedCalories] = await Promise.all([
          fetchAllPages<DietItem>(`${dietsUrl}?page=1`),
          fetchAllPages<DietCalorieItem>(`${dietCaloriesUrl}?page=1`),
        ]);

        if (cancelled) {
          return;
        }

        const groupedCalories = fetchedCalories.reduce<Record<number, DietCalorieItem[]>>((acc, item) => {
          if (!item.dieta_id) {
            return acc;
          }

          if (!acc[item.dieta_id]) {
            acc[item.dieta_id] = [];
          }

          if (!acc[item.dieta_id].some((entry) => entry.id === item.id)) {
            acc[item.dieta_id].push(item);
          }

          return acc;
        }, {});

        Object.keys(groupedCalories).forEach((dietId) => {
          groupedCalories[Number(dietId)].sort(
            (a, b) => (a.czysta_kalorycznosc ?? 0) - (b.czysta_kalorycznosc ?? 0),
          );
        });

        setDiets(fetchedDiets);
        setCaloriesByDietId(groupedCalories);
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Nieznany blad pobierania diet.";
          setDietsError(message);
        }
      } finally {
        if (!cancelled) {
          setDietsLoading(false);
        }
      }
    };

    void fetchDiets();

    return () => {
      cancelled = true;
    };
  }, [activeTab, backendApiBaseUrl, dietCaloriesUrl, dietsUrl]);

  useEffect(() => {
    if (activeTab !== "diety" || !diets.length || selectedDietId !== null || !userDietInitialized) {
      return;
    }

    const initialDietId = preferredDietId && diets.some((diet) => diet.id === preferredDietId)
      ? preferredDietId
      : diets[0].id;
    const initialCalories = caloriesByDietId[initialDietId] ?? [];
    const initialCalorieId = preferredDietCalorieId && initialCalories.some((option) => option.id === preferredDietCalorieId)
      ? preferredDietCalorieId
      : (initialCalories[0]?.id ?? null);

    setSelectedDietId(initialDietId);
    setExpandedDietId(initialDietId);
    setSelectedDietCalorieId(initialCalorieId);
    setMealsPage(1);
  }, [activeTab, caloriesByDietId, diets, preferredDietCalorieId, preferredDietId, selectedDietId, userDietInitialized]);

  useEffect(() => {
    if (!selectedDietId) {
      return;
    }

    const options = caloriesByDietId[selectedDietId] ?? [];
    if (!options.length) {
      setSelectedDietCalorieId(null);
      return;
    }

    if (!options.some((option) => option.id === selectedDietCalorieId)) {
      setSelectedDietCalorieId(options[0].id);
      setMealsPage(1);
      setSelectedMealId(null);
    }
  }, [caloriesByDietId, selectedDietCalorieId, selectedDietId]);

  useEffect(() => {
    if (!accountSelectedDietId) {
      return;
    }

    const options = caloriesByDietId[accountSelectedDietId] ?? [];
    if (!options.length) {
      setAccountSelectedDietCalorieId(null);
      return;
    }

    if (!options.some((option) => option.id === accountSelectedDietCalorieId)) {
      setAccountSelectedDietCalorieId(options[0].id);
    }
  }, [accountSelectedDietCalorieId, accountSelectedDietId, caloriesByDietId]);

  useEffect(() => {
    if (!selectedDietId || !selectedDietCalorieId) {
      return;
    }

    const selectedCalorieOption = (caloriesByDietId[selectedDietId] ?? []).find(
      (item) => item.id === selectedDietCalorieId,
    );

    if (typeof selectedCalorieOption?.czysta_kalorycznosc === "number") {
      setMealFilters((prev) => ({
        ...prev,
        czystaKalorycznosc: String(selectedCalorieOption.czysta_kalorycznosc),
      }));
    }
  }, [caloriesByDietId, selectedDietCalorieId, selectedDietId]);

  useEffect(() => {
    if (activeTab !== "diety" || !selectedDietId || !selectedDietCalorieId) {
      setMeals([]);
      setMealsCount(0);
      return;
    }

    let cancelled = false;

    const fetchMealsPage = async () => {
      setMealsLoading(true);
      setMealsError("");

      try {
        const selectedCalorieOption = (caloriesByDietId[selectedDietId] ?? []).find(
          (item) => item.id === selectedDietCalorieId,
        );

        const queryParams = new URLSearchParams();
        queryParams.set("dieta-id", String(selectedDietId));
        queryParams.set("kalorycznosc-diety-id", String(selectedDietCalorieId));
        queryParams.set("page", String(mealsPage));
        queryParams.set("page_size", String(mealsPageSize));

        if (selectedCalorieOption?.kalorycznosc_id) {
          queryParams.set("kalorycznosc-id", String(selectedCalorieOption.kalorycznosc_id));
        }

        if (mealFilters.nazwaPosilku.trim()) {
          queryParams.set("nazwa-posilku", mealFilters.nazwaPosilku.trim());
        }
        if (mealFilters.poraPosilku.trim()) {
          queryParams.set("pora-posilku", mealFilters.poraPosilku.trim());
        }
        if (mealFilters.czasPrzygotowania.trim()) {
          queryParams.set("czas-przygotowania", mealFilters.czasPrzygotowania.trim());
        }
        if (mealFilters.czasPrzygotowaniaMaxMinut.trim()) {
          queryParams.set("czas-przygotowania-max-minut", mealFilters.czasPrzygotowaniaMaxMinut.trim());
        }
        if (mealFilters.czystaKalorycznosc.trim()) {
          queryParams.set("czysta-kalorycznosc", mealFilters.czystaKalorycznosc.trim());
        }
        if (mealFilters.sortowanieCena) {
          queryParams.set("sortowanie-cena", mealFilters.sortowanieCena);
        }

        const response = await fetch(`${dietMealsUrl}?${queryParams.toString()}`);

        if (!response.ok) {
          throw new Error(`Nie udalo sie pobrac posilkow (HTTP ${response.status}).`);
        }

        const payload = (await response.json()) as PaginatedResponse<MealItem>;

        if (cancelled) {
          return;
        }

        setMeals(payload.results ?? []);
        setMealsCount(payload.count ?? 0);
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Nieznany blad pobierania posilkow.";
          setMealsError(message);
        }
      } finally {
        if (!cancelled) {
          setMealsLoading(false);
        }
      }
    };

    void fetchMealsPage();

    return () => {
      cancelled = true;
    };
  }, [
    activeTab,
    caloriesByDietId,
    dietMealsUrl,
    mealFilters,
    mealsPage,
    mealsPageSize,
    selectedDietCalorieId,
    selectedDietId,
  ]);

  const refreshShoppingLists = useCallback(async () => {
    setShoppingListsLoading(true);
    setShoppingListsError("");

    try {
      const response = await fetchWithAuth(shoppingListsUrl);
      const payload = (await response.json()) as ShoppingListSummary[] | { detail?: string; CODE?: string };

      if (!response.ok) {
        if (response.status === 404) {
          setShoppingLists([]);
          return;
        }
        throw new Error(!Array.isArray(payload) && payload.detail ? payload.detail : `Backend zwrocil HTTP ${response.status}.`);
      }

      setShoppingLists(Array.isArray(payload) ? payload : []);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie pobrac list zakupow.";
      setShoppingListsError(message);
    } finally {
      setShoppingListsLoading(false);
    }
  }, [fetchWithAuth, shoppingListsUrl]);

  useEffect(() => {
    if (activeTab !== "lista-zakupow") {
      return;
    }

    void refreshShoppingLists();
  }, [activeTab, refreshShoppingLists]);

  const refreshWarehouse = useCallback(async () => {
    setWarehouseLoading(true);
    setWarehouseMessage("");

    try {
      const [warehouseResponse, coverageResponse, possibleMealsResponse] = await Promise.all([
        fetchWithAuth(warehouseUrl),
        fetchWithAuth(warehouseCoverageUrl),
        fetchWithAuth(warehousePossibleMealsUrl),
      ]);

      const warehousePayload = (await warehouseResponse.json()) as WarehouseResponse;
      const coveragePayload = (await coverageResponse.json()) as WarehouseCoverageResponse;
      const possibleMealsPayload = (await possibleMealsResponse.json()) as PossibleMealsResponse;

      if (!warehouseResponse.ok) {
        if (warehouseResponse.status === 404) {
          setWarehouse(null);
          setWarehouseCoverage(null);
          setPossibleMeals([]);
          return;
        }
        throw new Error(warehousePayload.detail || `Magazyn zwrocil HTTP ${warehouseResponse.status}.`);
      }

      setWarehouse(warehousePayload);
      setWarehouseCoverage(coverageResponse.ok ? coveragePayload : null);
      setPossibleMeals(possibleMealsResponse.ok ? possibleMealsPayload.mozliwe_posilki ?? [] : []);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie pobrac magazynu.";
      setWarehouseMessage(message);
    } finally {
      setWarehouseLoading(false);
    }
  }, [fetchWithAuth, warehouseCoverageUrl, warehousePossibleMealsUrl, warehouseUrl]);

  useEffect(() => {
    if (activeTab !== "magazyn") {
      return;
    }

    void refreshWarehouse();
  }, [activeTab, refreshWarehouse]);

  const saveNotificationPreference = async () => {
    setSavingNotifications(true);
    setAccountMessage("");

    try {
      localStorage.setItem("notifications_consent", notificationsConsent ? "1" : "0");

      if (!notificationsConsent) {
        setAccountMessage("Ustawienie zapisane. Powiadomienia sa wylaczone.");
        return;
      }

      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Brak tokenu dostepu. Zaloguj sie ponownie.");
      }

      if (!("Notification" in window)) {
        throw new Error("Ta przegladarka nie obsluguje powiadomien.");
      }

      if (!("serviceWorker" in navigator)) {
        throw new Error("Brak obslugi service worker w przegladarce.");
      }

      const vapidKey = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY;
      if (!vapidKey) {
        throw new Error("Brakuje NEXT_PUBLIC_FIREBASE_VAPID_KEY w konfiguracji frontendu.");
      }

      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error("Brak zgody przegladarki na powiadomienia.");
      }

      const messagingModule = await import("firebase/messaging");
      const supported = await messagingModule.isSupported();
      if (!supported) {
        throw new Error("Firebase Messaging nie jest obslugiwany na tym urzadzeniu.");
      }

      const serviceWorkerRegistration = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
      const messaging = messagingModule.getMessaging(getFirebaseApp());
      const fcmToken = await messagingModule.getToken(messaging, {
        vapidKey,
        serviceWorkerRegistration,
      });

      if (!fcmToken) {
        throw new Error("Nie udalo sie pobrac tokenu urzadzenia FCM.");
      }

      const apiResponse = await fetch(fcmDeviceUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ token: fcmToken, platform: "web" }),
      });

      const payload = (await apiResponse.json()) as { detail?: string };

      if (!apiResponse.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${apiResponse.status}.`);
      }

      setAccountMessage("Zgoda zapisana. Token urzadzenia zostal zapisany w bazie.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie zapisac ustawien powiadomien.";
      setAccountMessage(message);
    } finally {
      setSavingNotifications(false);
    }
  };

  const refreshFamilyOverview = async () => {
    const accessToken = localStorage.getItem("access_token");
    if (!accessToken) {
      setFamilyMembers([]);
      setFamilyNameOverview("");
      return;
    }

    const response = await fetchWithAuth(familyMembersUrl);

    const payload = (await response.json()) as FamilyMembersResponse & { CODE?: string; detail?: string };
    if (!response.ok) {
      if (response.status === 404 || payload.CODE === "FAMILY_NOT_FOUND") {
        setFamilyMembers([]);
        setFamilyNameOverview("");
        setFamilyOverviewError("");
        return;
      }
      throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
    }

    setFamilyMembers(payload.members ?? []);
    setFamilyNameOverview(payload.rodzina ?? "");
    setFamilyOverviewError("");
  };

  const createFamily = async () => {
    setCreatingFamily(true);
    setFamilyMessage("");

    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Brak tokenu dostepu. Zaloguj sie ponownie.");
      }

      if (!familyName.trim()) {
        throw new Error("Podaj nazwe rodziny.");
      }

      const response = await fetch(familiesUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ rodzina: familyName.trim() }),
      });

      const payload = (await response.json()) as FamilyCreateResponse;

      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setFamilyMessage(`Rodzina '${payload.rodzina || familyName.trim()}' zostala utworzona.`);
      setFamilyName("");
      await refreshFamilyOverview();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie utworzyc rodziny.";
      setFamilyMessage(message);
    } finally {
      setCreatingFamily(false);
    }
  };

  const sendFamilyInvitation = async () => {
    setSendingFamilyInvite(true);
    setFamilyMessage("");

    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Brak tokenu dostepu. Zaloguj sie ponownie.");
      }

      if (!familyInviteEmail.trim()) {
        throw new Error("Podaj email do zaproszenia.");
      }

      const response = await fetch(familyInvitationsUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ email: familyInviteEmail.trim() }),
      });

      const payload = (await response.json()) as FamilyInviteResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setFamilyMessage(`Zaproszenie wyslane na ${payload.email || familyInviteEmail.trim()}.`);
      setFamilyInviteEmail("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie wyslac zaproszenia.";
      setFamilyMessage(message);
    } finally {
      setSendingFamilyInvite(false);
    }
  };

  const leaveFamily = async () => {
    setLeavingFamily(true);
    setFamilyMessage("");

    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Brak tokenu dostepu. Zaloguj sie ponownie.");
      }

      const response = await fetch(familyLeaveUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      const payload = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setFamilyMessage("Opuszczono rodzine.");
      await refreshFamilyOverview();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie opuscic rodziny.";
      setFamilyMessage(message);
    } finally {
      setLeavingFamily(false);
    }
  };

  const planFamilyMeal = async () => {
    setPlanningMeal(true);
    setCalendarMessage("");
    setCreatedPlannedMeal(null);

    try {
      if (!plannedMealDate) {
        throw new Error("Wybierz date posilku.");
      }
      if (!plannedMealId.trim()) {
        throw new Error("Podaj posilek_w_diecie_id.");
      }

      const response = await fetchWithAuth(calendarPlannedMealsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: plannedMealDate,
          posilek_w_diecie_id: Number(plannedMealId),
        }),
      });

      const payload = (await response.json()) as PlannedMealResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setCreatedPlannedMeal(payload);
      setCalendarMessage("Posilek zostal dodany do kalendarza rodziny.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie zaplanowac posilku.";
      setCalendarMessage(message);
    } finally {
      setPlanningMeal(false);
    }
  };

  const scheduleMealFromDiet = async (mealId: number | null) => {
    if (!mealId) {
      setMealSchedulingMessage("Błąd: Nie wybrano posiłku.");
      return;
    }

    setMealSchedulingLoading(true);
    setMealSchedulingMessage("");

    try {
      if (!mealScheduleDate) {
        throw new Error("Wybierz datę posiłku.");
      }

      console.log("Scheduling meal:", { mealId, mealScheduleDate });

      const response = await fetchWithAuth(calendarPlannedMealsUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: mealScheduleDate,
          posilek_w_diecie_id: mealId,
        }),
      });

      console.log("Response status:", response.status);
      const payload = await response.json();
      console.log("Response payload:", payload);

      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setCreatedPlannedMeal(payload);
      setMealSchedulingMessage("✓ Posiłek został dodany do kalendarza rodziny.");
      
      // Reset form after successful scheduling
      setTimeout(() => {
        setMealToScheduleId(null);
        setMealSchedulingMessage("");
      }, 2000);

      // Refresh calendar meals
      await fetchCalendarMealsForMonth(mealScheduleDate);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udało się zaplanować posiłku.";
      console.error("Scheduling error:", message);
      setMealSchedulingMessage(`❌ ${message}`);
    } finally {
      setMealSchedulingLoading(false);
    }
  };

  const fetchCalendarMealsForMonth = async (dateString: string) => {
    setCalendarMealsLoading(true);

    try {
      console.log("Fetching planned meals from:", calendarPlannedMealsUrl);

      const response = await fetchWithAuth(calendarPlannedMealsUrl, {
        method: "GET",
      });

      console.log("Calendar response status:", response.status);

      if (!response.ok) {
        throw new Error(`Backend zwrocil HTTP ${response.status}.`);
      }

      const data = await response.json();
      console.log("Calendar data received:", data);

      const listItems = Array.isArray(data?.zaplanowane_posilki) ? data.zaplanowane_posilki : [];
      const payload = Array.isArray(data) ? data : data.results || data.data || listItems;
      const rawPlannedMeals = Array.isArray(payload) ? payload : [];

      let allPlannedMeals: PlannedMealResponse[] = rawPlannedMeals
        .map((raw: any) => {
          const rawDate =
            raw?.data ||
            raw?.data_posilku ||
            raw?.date ||
            raw?.data_planowana ||
            raw?.data_posilku_rodziny ||
            "";
          const fallbackPlanned = raw?.posilek_w_diecie_id
            ? [
                {
                  uzytkownik_id: raw.uzytkownik_id,
                  uzytkownik_w_rodzinie_id: raw.uzytkownik_w_rodzinie_id,
                  posilek_w_diecie_id: raw.posilek_w_diecie_id,
                  kalorycznosc_diety: raw.kalorycznosc_diety,
                  proporcja_kaloryczna: raw.proporcja_kaloryczna,
                },
              ]
            : [];

          return {
            planned_meal_id: raw?.planned_meal_id ?? raw?.id ?? raw?.zaplanowany_posilek_id,
            data: rawDate,
            czy_zjedzone: raw?.czy_zjedzone ?? raw?.zjedzone,
            pora_posilku: raw?.pora_posilku ?? raw?.pora,
            rodzina_id: raw?.rodzina_id,
            liczba_czlonkow_rodziny: raw?.liczba_czlonkow_rodziny,
            liczba_osob_przy_posilku: raw?.liczba_osob_przy_posilku ?? raw?.liczba_osob,
            zaplanowane_posilki: raw?.zaplanowane_posilki ?? fallbackPlanned,
          } as PlannedMealResponse;
        })
        .filter((meal) => Boolean(meal.data));

      const memberNameByUserId: Record<number, string> = {};
      try {
        const membersResponse = await fetchWithAuth(familyMembersUrl, { method: "GET" });
        if (membersResponse.ok) {
          const membersPayload = await membersResponse.json();
          if (membersPayload?.members && Array.isArray(membersPayload.members)) {
            membersPayload.members.forEach((member: any) => {
              if (typeof member.id === "number") {
                memberNameByUserId[member.id] =
                  member.first_name || member.username || `Uzytkownik ${member.id}`;
              }
            });
          }

          // Fallback: if calendar endpoint returns empty, use members' planned meals
          if (!allPlannedMeals.length && membersPayload?.members) {
            const fallbackMeals: PlannedMealResponse[] = [];
            membersPayload.members.forEach((member: any) => {
              if (Array.isArray(member.zaplanowane_posilki)) {
                member.zaplanowane_posilki.forEach((plannedMeal: any) => {
                  const plannedDate =
                    plannedMeal?.data ||
                    plannedMeal?.data_posilku ||
                    plannedMeal?.date ||
                    plannedMeal?.data_planowana ||
                    "";
                  fallbackMeals.push({
                    planned_meal_id:
                      plannedMeal?.planned_meal_id ??
                      plannedMeal?.id ??
                      plannedMeal?.zaplanowany_posilek_id,
                    data: plannedDate,
                    czy_zjedzone: plannedMeal?.czy_zjedzone ?? plannedMeal?.zjedzone,
                    pora_posilku: plannedMeal?.pora_posilku ?? plannedMeal?.pora,
                    rodzina_id: membersPayload.rodzina_id,
                    liczba_czlonkow_rodziny: plannedMeal?.liczba_czlonkow_rodziny,
                    liczba_osob_przy_posilku: plannedMeal?.liczba_osob_przy_posilku ?? plannedMeal?.liczba_osob,
                    zaplanowane_posilki:
                      plannedMeal?.zaplanowane_posilki ??
                      (plannedMeal?.posilek_w_diecie_id
                        ? [
                            {
                              uzytkownik_id: member.id,
                              uzytkownik_w_rodzinie_id: plannedMeal?.uzytkownik_w_rodzinie_id,
                              posilek_w_diecie_id: plannedMeal?.posilek_w_diecie_id,
                              kalorycznosc_diety: plannedMeal?.kalorycznosc_diety,
                              proporcja_kaloryczna: plannedMeal?.proporcja_kaloryczna,
                            },
                          ]
                        : []),
                  } as PlannedMealResponse);
                });
              }
            });

            allPlannedMeals = fallbackMeals.filter((meal) => Boolean(meal.data));
          }
        }
      } catch (error) {
        console.error("Error fetching family members for calendar:", error);
      }

      const mealsByDate: Record<string, PlannedMealResponse[]> = {};
      const mealIdsToFetch = new Set<number>();
      
      allPlannedMeals.forEach((meal: PlannedMealResponse) => {
        if (meal.data) {
          if (!mealsByDate[meal.data]) {
            mealsByDate[meal.data] = [];
          }
          mealsByDate[meal.data].push(meal);
          
          // Collect meal IDs to fetch details for
          meal.zaplanowane_posilki?.forEach((item) => {
            mealIdsToFetch.add(item.posilek_w_diecie_id);
          });
        }
      });

      console.log("Meals by date:", mealsByDate);
      console.log("Meal IDs to fetch:", Array.from(mealIdsToFetch));

      // Fetch meal details for all meal IDs
      if (mealIdsToFetch.size > 0) {
        const mealDetailsMap: Record<number, MealItem> = {};
        
        for (const mealId of Array.from(mealIdsToFetch)) {
          try {
            const mealResponse = await fetch(`${dietMealsUrl}?posilek-w-diecie-id=${mealId}`);
            if (mealResponse.ok) {
              const mealData = await mealResponse.json();
              let meals: any[] = [];
              if (Array.isArray(mealData)) {
                meals = mealData;
              } else if (mealData.results && Array.isArray(mealData.results)) {
                meals = mealData.results;
              } else if (mealData.data && Array.isArray(mealData.data)) {
                meals = mealData.data;
              }
              
              if (meals.length > 0) {
                mealDetailsMap[mealId] = meals[0];
              }
            }
          } catch (err) {
            console.error(`Error fetching meal details for ID ${mealId}:`, err);
          }
        }
        
        console.log("Meal details map:", mealDetailsMap);
        setMealDetailById(mealDetailsMap);
      }

      setCalendarPlannedMeals(mealsByDate);
      setCalendarMemberNameByUserId(memberNameByUserId);
    } catch (error) {
      console.error("Error fetching calendar meals:", error);
      setCalendarPlannedMeals({});
      setCalendarMemberNameByUserId({});
    } finally {
      setCalendarMealsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === "kalendarz") {
      void fetchCalendarMealsForMonth(calendarViewDate);
    }
  }, [activeTab, calendarViewDate]);

  const createShoppingListFromCalendar = async () => {
    setCreatingShoppingList(true);
    setShoppingMessage("");

    try {
      if (!shoppingListFromDate || !shoppingListToDate) {
        throw new Error("Wybierz zakres dat.");
      }

      const response = await fetchWithAuth(shoppingListFromCalendarUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data_od: shoppingListFromDate,
          data_do: shoppingListToDate,
          nazwa_listy_zakupow: shoppingListName.trim(),
        }),
      });

      const payload = (await response.json()) as ShoppingListCreateResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setShoppingMessage(
        `Utworzono liste '${payload.nazwa_listy_zakupow || shoppingListName || "Lista zakupow"}' z ${
          payload.liczba_pozycji_na_liscie ?? 0
        } pozycjami.`,
      );
      setShoppingListName("");
      await refreshShoppingLists();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie utworzyc listy zakupow.";
      setShoppingMessage(message);
    } finally {
      setCreatingShoppingList(false);
    }
  };

  const fetchShoppingListDetail = async (shoppingListId: number) => {
    setSelectedShoppingListId(shoppingListId);
    setShoppingListDetailLoading(true);
    setShoppingListDetailError("");
    setSelectedShoppingListDetail(null);

    try {
      const response = await fetchWithAuth(`${shoppingListsUrl}${shoppingListId}/`, { method: "GET" });
      const payload = (await response.json()) as ShoppingListDetailResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }
      setSelectedShoppingListDetail(payload);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie pobrac szczegolow listy zakupow.";
      setShoppingListDetailError(message);
    } finally {
      setShoppingListDetailLoading(false);
    }
  };

  const markShoppingListProductAsBought = async (shoppingListId: number, productId: number) => {
    setMarkingBoughtProductId(productId);
    setShoppingMessage("");
    setShoppingListDetailError("");

    try {
      const response = await fetchWithAuth(shoppingListMarkBoughtUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shopping_list_id: shoppingListId,
          produkt_id: productId,
        }),
      });
      const payload = (await response.json()) as {
        detail?: string;
        ilosc_dodana_do_magazynu?: number;
        jednostka_dodanej_ilosci?: string;
      };
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      const amount =
        typeof payload.ilosc_dodana_do_magazynu === "number"
          ? `${payload.ilosc_dodana_do_magazynu} ${payload.jednostka_dodanej_ilosci || ""}`.trim()
          : null;
      setShoppingMessage(
        amount
          ? `Produkt przeniesiono do magazynu: ${amount}.`
          : "Produkt oznaczono jako kupiony i przeniesiono do magazynu.",
      );

      await Promise.all([
        fetchShoppingListDetail(shoppingListId),
        refreshShoppingLists(),
        refreshWarehouse(),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie oznaczyc produktu jako kupiony.";
      setShoppingListDetailError(message);
    } finally {
      setMarkingBoughtProductId(null);
    }
  };

  const markAllShoppingListProductsAsBought = async () => {
    if (!selectedShoppingListDetail?.produkty?.length) {
      setShoppingMessage("Brak produktow do oznaczenia jako kupione.");
      return;
    }

    const shoppingListId = selectedShoppingListDetail.id;
    const productIds = selectedShoppingListDetail.produkty.map((product) => product.produkt_id);

    setMarkingAllBought(true);
    setShoppingMessage("");
    setShoppingListDetailError("");

    try {
      let successCount = 0;
      for (const productId of productIds) {
        setMarkingBoughtProductId(productId);
        const response = await fetchWithAuth(shoppingListMarkBoughtUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            shopping_list_id: shoppingListId,
            produkt_id: productId,
          }),
        });
        const payload = (await response.json()) as { detail?: string };
        if (!response.ok) {
          throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
        }
        successCount += 1;
      }

      await Promise.all([
        fetchShoppingListDetail(shoppingListId),
        refreshShoppingLists(),
        refreshWarehouse(),
      ]);
      setShoppingMessage(`Oznaczono jako kupione: ${successCount} produktow.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie oznaczyc wszystkich produktow jako kupione.";
      setShoppingListDetailError(message);
    } finally {
      setMarkingBoughtProductId(null);
      setMarkingAllBought(false);
    }
  };

  const clearWarehouse = async () => {
    setWarehouseMessage("");

    try {
      const response = await fetchWithAuth(warehouseClearUrl, { method: "POST" });
      const payload = (await response.json()) as { detail?: string; deleted_entries?: number };
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setWarehouseMessage(`Magazyn wyczyszczony. Usunieto pozycji: ${payload.deleted_entries ?? 0}.`);
      await refreshWarehouse();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie wyczyscic magazynu.";
      setWarehouseMessage(message);
    }
  };

  const updateWarehouseProduct = async () => {
    setWarehouseMessage("");

    try {
      const productIdValue = warehouseProductId.trim() || (selectedWarehouseProductId ? String(selectedWarehouseProductId) : "");
      if (!productIdValue) {
        throw new Error("Podaj produkt_id.");
      }
      if (!warehouseProductAmount.trim()) {
        throw new Error("Podaj ilosc produktu.");
      }
      const normalizedAmountText = warehouseProductAmount.trim().replace(",", ".");
      const parsedAmount = Number(normalizedAmountText);
      if (Number.isNaN(parsedAmount) || parsedAmount < 0) {
        throw new Error("Ilosc produktu musi byc liczba >= 0.");
      }

      const response = await fetchWithAuth(warehouseUpdateProductUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          produkt_id: Number(productIdValue),
          ilosc_produktu: parsedAmount,
        }),
      });
      const payload = (await response.json()) as {
        detail?: string;
        produkt_id?: number;
        nazwa_produktu?: string;
        ilosc_produktu?: number;
      };
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setWarehouseMessage(`Zaktualizowano ${payload.nazwa_produktu || `produkt #${productIdValue}`}.`);
      setWarehouseProductId(String(payload.produkt_id ?? productIdValue));
      setSelectedWarehouseProductId(payload.produkt_id ?? Number(productIdValue));
      if (typeof payload.ilosc_produktu === "number") {
        setWarehouseProductAmount(String(payload.ilosc_produktu));
      }
      await refreshWarehouse();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie zaktualizowac magazynu.";
      setWarehouseMessage(message);
    }
  };

  const saveUserDietPreference = async () => {
    setSavingUserDiet(true);
    setAccountMessage("");

    try {
      const accessToken = localStorage.getItem("access_token");
      if (!accessToken) {
        throw new Error("Brak tokenu dostepu. Zaloguj sie ponownie.");
      }

      if (!accountSelectedDietCalorieId) {
        throw new Error("Wybierz opcje kalorycznosci diety.");
      }

      const response = await fetch(familyMembershipDietUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ kalorycznosc_diety_id: accountSelectedDietCalorieId }),
      });

      const rawBody = await response.text();
      let payload: (AuthMeResponse & { detail?: string }) | null = null;
      try {
        payload = rawBody ? (JSON.parse(rawBody) as AuthMeResponse & { detail?: string }) : null;
      } catch {
        payload = null;
      }

      if (!response.ok) {
        if (payload?.detail) {
          throw new Error(payload.detail);
        }

        if (rawBody.trim().startsWith("<!DOCTYPE") || rawBody.trim().startsWith("<html")) {
          throw new Error("Backend zwrocil nieprawidlowy format odpowiedzi (HTML zamiast JSON). Sprawdz logi backendu.");
        }

        throw new Error(`Backend zwrocil HTTP ${response.status}.`);
      }

      if (!payload) {
        throw new Error("Backend nie zwrocil poprawnego JSON po zapisie diety.");
      }

      const nextDietId = payload.dieta_id ?? accountSelectedDietId;
      const nextDietCalorieId = payload.kalorycznosc_diety_id ?? accountSelectedDietCalorieId;

      setPreferredDietId(nextDietId ?? null);
      setPreferredDietCalorieId(nextDietCalorieId ?? null);

      if (nextDietId) {
        setSelectedDietId(nextDietId);
        setExpandedDietId(nextDietId);
      }
      setSelectedDietCalorieId(nextDietCalorieId ?? null);
      setMealsPage(1);
      setSelectedMealId(null);

      setAccountMessage("Wybor diety zapisany.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie zapisac wyboru diety.";
      setAccountMessage(message);
    } finally {
      setSavingUserDiet(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/";
  };

  const tabContent = useMemo(() => {
    switch (activeTab) {
      case "tablica":
        return "Podglad diety i kalorycznosci calej rodziny.";
      case "diety":
        return "Po lewej masz liste diet, a w centrum posilki z backendu po 10 na strone.";
      case "kalendarz":
        return "Planowanie posilkow rodziny na wskazany dzien.";
      case "lista-zakupow":
        return "Generowanie i podglad list zakupow z kalendarza.";
      case "magazyn":
        return "Stan lodowki rodziny, pokrycie posilkow i aktualizacja ilosci.";
      case "konto":
        return "Profil konta, ustawienia, dieta uzytkownika i zarzadzanie rodzina.";
      default:
        return "";
    }
  }, [activeTab]);

  const selectedDiet = useMemo(() => {
    if (!selectedDietId) {
      return null;
    }
    return diets.find((diet) => diet.id === selectedDietId) ?? null;
  }, [diets, selectedDietId]);

  const selectedDietCalorie = useMemo(() => {
    if (!selectedDietId || !selectedDietCalorieId) {
      return null;
    }
    return (caloriesByDietId[selectedDietId] ?? []).find((item) => item.id === selectedDietCalorieId) ?? null;
  }, [caloriesByDietId, selectedDietCalorieId, selectedDietId]);

  const selectedDietCalorieLabel = useMemo(() => {
    if (!selectedDietCalorie) {
      return "";
    }
    if (typeof selectedDietCalorie.czysta_kalorycznosc === "number") {
      return `${selectedDietCalorie.czysta_kalorycznosc} kcal`;
    }
    return selectedDietCalorie.kalorycznosc || "wybrana opcja kcal";
  }, [selectedDietCalorie]);

  const accountDietCalorieOptions = useMemo(() => {
    if (!accountSelectedDietId) {
      return [];
    }
    return caloriesByDietId[accountSelectedDietId] ?? [];
  }, [accountSelectedDietId, caloriesByDietId]);

  const filteredWarehouseProducts = useMemo(() => {
    const products = warehouse?.produkty ?? [];
    const query = warehouseProductSearch.trim().toLowerCase();
    if (!query) {
      return products.slice(0, 8);
    }
    return products
      .filter((product) => product.nazwa_produktu.toLowerCase().includes(query))
      .slice(0, 8);
  }, [warehouse?.produkty, warehouseProductSearch]);

  useEffect(() => {
    if (activeTab !== "magazyn") {
      return;
    }

    const query = warehouseProductSearch.trim();
    if (query.length < 2) {
      setWarehouseSearchResults([]);
      setWarehouseSearchLoading(false);
      return;
    }

    let cancelled = false;
    setWarehouseSearchLoading(true);

    const fetchProducts = async () => {
      try {
        const response = await fetch(`${simplifiedProductsUrl}?nazwa-produktu=${encodeURIComponent(query)}&page=1`);
        if (!response.ok) {
          throw new Error(`Backend zwrocil HTTP ${response.status}.`);
        }
        const payload = await response.json();
        const rawList = Array.isArray(payload) ? payload : payload?.results ?? [];
        const mapped = (Array.isArray(rawList) ? rawList : [])
          .map((item: any) => ({
            id: Number(item?.id),
            nazwa_produktu_uproszczonego: String(item?.nazwa_produktu_uproszczonego || ""),
          }))
          .filter((item) => Number.isFinite(item.id) && item.id > 0 && item.nazwa_produktu_uproszczonego)
          .slice(0, 12);
        if (!cancelled) {
          setWarehouseSearchResults(mapped);
        }
      } catch {
        if (!cancelled) {
          setWarehouseSearchResults([]);
        }
      } finally {
        if (!cancelled) {
          setWarehouseSearchLoading(false);
        }
      }
    };

    void fetchProducts();
    return () => {
      cancelled = true;
    };
  }, [activeTab, simplifiedProductsUrl, warehouseProductSearch]);

  const totalMealPages = useMemo(() => {
    if (!mealsCount) {
      return 1;
    }
    return Math.max(1, Math.ceil(mealsCount / mealsPageSize));
  }, [mealsCount, mealsPageSize]);

  const dietNameById = useMemo(() => {
    return diets.reduce<Record<number, string>>((acc, diet) => {
      acc[diet.id] = diet.dieta;
      return acc;
    }, {});
  }, [diets]);

  const selectedCalendarMealIds = useMemo(() => {
    if (!selectedCalendarMeal?.meal.zaplanowane_posilki?.length) {
      return [];
    }
    const uniqueIds = Array.from(
      new Set(selectedCalendarMeal.meal.zaplanowane_posilki.map((item) => item.posilek_w_diecie_id)),
    );
    return [...uniqueIds].sort((a, b) => {
      const mealA = mealDetailById[a];
      const mealB = mealDetailById[b];
      const orderDiff = getMealTimeOrder(mealA?.pora_posilku) - getMealTimeOrder(mealB?.pora_posilku);
      if (orderDiff !== 0) {
        return orderDiff;
      }
      return String(mealA?.nazwa_posilku || "").localeCompare(String(mealB?.nazwa_posilku || ""), "pl");
    });
  }, [mealDetailById, selectedCalendarMeal]);

  useEffect(() => {
    if (!selectedCalendarMealIds.length) {
      setSelectedCalendarMealDetailId(null);
      return;
    }
    setSelectedCalendarMealDetailId((prev) => prev ?? selectedCalendarMealIds[0]);
  }, [selectedCalendarMealIds]);

  useEffect(() => {
    if (!selectedCalendarMeal) {
      return;
    }
    const representativeMealId = selectedCalendarMeal.meal.zaplanowane_posilki?.[0]?.posilek_w_diecie_id ?? null;
    setSelectedCalendarMealDetailId(representativeMealId ?? selectedCalendarMealIds[0] ?? null);
  }, [selectedCalendarMeal?.date, selectedCalendarMeal?.meal?.planned_meal_id, selectedCalendarMealIds]);

  const selectedCalendarMealDetail = useMemo(() => {
    if (!selectedCalendarMealDetailId) {
      return null;
    }
    return mealDetailById[selectedCalendarMealDetailId] ?? null;
  }, [mealDetailById, selectedCalendarMealDetailId]);

  const selectedCalendarMealPreview = useMemo(() => {
    if (!selectedCalendarMealIds.length) {
      return null;
    }

    const representativeMealId = selectedCalendarMeal?.meal.zaplanowane_posilki?.[0]?.posilek_w_diecie_id ?? null;
    const activeMealId =
      selectedCalendarMealDetailId ??
      representativeMealId ??
      selectedCalendarMealIds[0];
    const previewMeal = mealDetailById[activeMealId];
    const representativeMeal = representativeMealId ? mealDetailById[representativeMealId] : undefined;

    // Use exactly the same loading source as the smaller thumbnail in calendar cards.
    const previewImageUrl = resolveBackendAssetUrl(
      previewMeal?.zdjecie_url ?? representativeMeal?.zdjecie_url,
      process.env.NEXT_PUBLIC_API_BASE_URL,
    );

    return {
      id: activeMealId,
      name: previewMeal?.nazwa_posilku || `Posilek #${activeMealId}`,
      pora: previewMeal?.pora_posilku || selectedCalendarMeal?.meal.pora_posilku || "Posilek",
      imageUrl: previewImageUrl,
    };
  }, [mealDetailById, selectedCalendarMeal, selectedCalendarMealIds]);

  const visibleCalendarMealsByDate = useMemo(() => {
    const view = new Date(calendarViewDate);
    const year = view.getFullYear();
    const month = view.getMonth();

    return Object.entries(calendarPlannedMeals)
      .filter(([date]) => {
        const dateObj = new Date(date);
        return dateObj.getFullYear() === year && dateObj.getMonth() === month;
      })
      .sort((a, b) => a[0].localeCompare(b[0]));
  }, [calendarPlannedMeals, calendarViewDate]);

  useEffect(() => {
    if (!selectedCalendarMeal) {
      return;
    }
    const selectedDate = new Date(selectedCalendarMeal.date);
    const view = new Date(calendarViewDate);
    if (selectedDate.getFullYear() !== view.getFullYear() || selectedDate.getMonth() !== view.getMonth()) {
      setSelectedCalendarMeal(null);
      setSelectedCalendarMealDetailId(null);
    }
  }, [calendarViewDate, selectedCalendarMeal]);

  const removeSelectedCalendarMeal = async () => {
    if (!selectedCalendarMeal?.meal?.planned_meal_id) {
      setCalendarMessage("Nie mozna usunac tego wpisu: brak identyfikatora zaplanowanego posilku.");
      return;
    }

    setCalendarMealRemoving(true);
    setCalendarMessage("");

    try {
      const response = await fetchWithAuth(calendarPlannedMealRemoveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planned_meal_id: selectedCalendarMeal.meal.planned_meal_id }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setSelectedCalendarMeal(null);
      setSelectedCalendarMealDetailId(null);
      setCalendarMessage("Zaplanowany posilek zostal usuniety.");
      await fetchCalendarMealsForMonth(calendarViewDate);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie usunac zaplanowanego posilku.";
      setCalendarMessage(message);
    } finally {
      setCalendarMealRemoving(false);
    }
  };

  const markSelectedCalendarMealAsEaten = async () => {
    if (!selectedCalendarMeal?.meal?.planned_meal_id) {
      setCalendarMessage("Nie mozna oznaczyc wpisu jako zjedzony: brak identyfikatora.");
      return;
    }

    setCalendarMealMarkingEaten(true);
    setCalendarMessage("");

    try {
      const response = await fetchWithAuth(calendarPlannedMealMarkEatenUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planned_meal_id: selectedCalendarMeal.meal.planned_meal_id }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      const consumedProducts = typeof payload?.consumed_products === "number" ? payload.consumed_products : null;
      setCalendarMessage(
        consumedProducts === null
          ? "Posilek oznaczono jako zjedzony."
          : `Posilek oznaczono jako zjedzony. Odjeto produkty z magazynu: ${consumedProducts}.`,
      );
      await fetchCalendarMealsForMonth(calendarViewDate);
      setSelectedCalendarMeal((prev) =>
        prev ? { ...prev, meal: { ...prev.meal, czy_zjedzone: true } } : prev,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie oznaczyc posilku jako zjedzony.";
      setCalendarMessage(message);
    } finally {
      setCalendarMealMarkingEaten(false);
    }
  };

  const createShoppingListFromVisibleCalendarDays = async () => {
    if (!visibleCalendarMealsByDate.length) {
      setCalendarMessage("Brak zaplanowanych posilkow w tym miesiacu.");
      return;
    }

    const firstDate = visibleCalendarMealsByDate[0]?.[0];
    const lastDate = visibleCalendarMealsByDate[visibleCalendarMealsByDate.length - 1]?.[0];
    if (!firstDate || !lastDate) {
      setCalendarMessage("Nie udalo sie wyznaczyc zakresu dat dla listy zakupow.");
      return;
    }

    setCalendarShoppingListCreating(true);
    setCalendarMessage("");

    try {
      const view = new Date(calendarViewDate);
      const defaultName = `Lista zakupow ${view.toLocaleDateString("pl-PL", { month: "long", year: "numeric" })}`;
      const response = await fetchWithAuth(shoppingListFromCalendarUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data_od: firstDate,
          data_do: lastDate,
          nazwa_listy_zakupow: defaultName,
        }),
      });

      const payload = (await response.json()) as ShoppingListCreateResponse;
      if (!response.ok) {
        throw new Error(payload.detail || `Backend zwrocil HTTP ${response.status}.`);
      }

      setCalendarMessage(
        `Utworzono liste '${payload.nazwa_listy_zakupow || defaultName}' dla zakresu ${firstDate} - ${lastDate}.`,
      );
      await refreshShoppingLists();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie utworzyc listy zakupow z kalendarza.";
      setCalendarMessage(message);
    } finally {
      setCalendarShoppingListCreating(false);
    }
  };

  const generateCalendarPdfForDateRange = () => {
    if (!calendarPdfFromDate || !calendarPdfToDate) {
      setCalendarMessage("Wybierz zakres dat dla PDF.");
      return;
    }
    if (calendarPdfToDate < calendarPdfFromDate) {
      setCalendarMessage("Data do nie moze byc wczesniejsza niz data od.");
      return;
    }

    const entries = Object.entries(calendarPlannedMeals)
      .filter(([date]) => date >= calendarPdfFromDate && date <= calendarPdfToDate)
      .sort((a, b) => a[0].localeCompare(b[0]));
    if (!entries.length) {
      setCalendarMessage("Brak posilkow w wybranym zakresie dat.");
      return;
    }

    setCalendarPdfGenerating(true);
    setCalendarMessage("");

    try {
      const rowsHtml = entries
        .map(([date, mealsOnDate]) => {
          const items = [...mealsOnDate]
            .sort((a, b) => getMealTimeOrder(a.pora_posilku) - getMealTimeOrder(b.pora_posilku))
            .map((meal) => {
              const mealIds = Array.from(new Set((meal.zaplanowane_posilki ?? []).map((x) => x.posilek_w_diecie_id)));
              const mealBlocks = mealIds
                .map((mealId) => {
                  const details = mealDetailById[mealId];
                  const mealName = details?.nazwa_posilku || `Posilek #${mealId}`;
                  const ingredients = details?.skladniki?.length
                    ? `<ul style="margin:4px 0 0 16px;padding:0;">${details.skladniki
                        .map(
                          (ingredient) =>
                            `<li>${ingredient.nazwa_produktu} - ${ingredient.ilosc_produktu} ${ingredient.miarka}</li>`,
                        )
                        .join("")}</ul>`
                    : `<p style="margin:4px 0 0 0;">Brak danych o skladnikach.</p>`;
                  const preparation = details?.opis_posilku
                    ? details.opis_posilku
                    : "Brak opisu przygotowania.";

                  return `
                    <div style="margin:8px 0;padding:8px;border:1px solid #e2e8f0;border-radius:6px;">
                      <p style="margin:0 0 4px 0;font-weight:700;">${mealName}</p>
                      <p style="margin:0;font-size:11px;"><strong>Skladniki:</strong></p>
                      ${ingredients}
                      <p style="margin:8px 0 0 0;font-size:11px;"><strong>Sposob przygotowania:</strong> ${preparation}</p>
                    </div>
                  `;
                })
                .join("");
              return `<li><strong>${meal.pora_posilku || "Posilek"}:</strong>${mealBlocks}</li>`;
            })
            .join("");

          return `
            <section style="margin-bottom:12px;padding:10px;border:1px solid #ddd;border-radius:8px;">
              <h3 style="margin:0 0 8px 0;font-size:14px;">${new Date(date).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</h3>
              <ul style="margin:0;padding-left:18px;font-size:12px;line-height:1.4;">${items}</ul>
            </section>
          `;
        })
        .join("");

      const html = `
        <html>
          <head>
            <meta charset="utf-8" />
            <title>MniamCal - Kalendarz posilkow</title>
          </head>
          <body style="font-family: Arial, sans-serif; color:#111; padding:20px;">
            <h1 style="margin:0 0 8px 0;">MniamCal - Kalendarz posilkow</h1>
            <p style="margin:0 0 16px 0;font-size:12px;">Zakres: ${calendarPdfFromDate} - ${calendarPdfToDate}</p>
            ${rowsHtml}
          </body>
        </html>
      `;

      const printWindow = window.open("", "_blank");
      if (!printWindow) {
        throw new Error("Przegladarka zablokowala okno podgladu PDF.");
      }

      printWindow.document.open();
      printWindow.document.write(html);
      printWindow.document.close();
      printWindow.focus();
      printWindow.print();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Nie udalo sie wygenerowac PDF.";
      setCalendarMessage(message);
    } finally {
      setCalendarPdfGenerating(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <section className="mx-auto w-full max-w-6xl rounded-2xl border border-slate-200 bg-white shadow-sm">
        <header className="border-b border-slate-200 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold">MniamCal</h1>
              <p className="mt-1 text-sm text-slate-600">Panel glowny po zalogowaniu.</p>
            </div>
            <button
              type="button"
              onClick={toggleDarkMode}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              {isDarkMode ? "Tryb dzienny" : "Tryb nocny"}
            </button>
          </div>
        </header>

        <nav className="flex flex-wrap gap-2 border-b border-slate-200 p-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                activeTab === tab.key
                  ? "bg-slate-900 text-white"
                  : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="p-6">
          <h2 className="text-lg font-semibold">{tabs.find((tab) => tab.key === activeTab)?.label}</h2>
          <p className="mt-2 text-sm text-slate-700">{tabContent}</p>

          {activeTab === "diety" ? (
            <div className="mt-6">
              <p className="text-sm text-slate-700">Kliknij diete, rozwin opcje kcal i wybierz kalorycznosc. Wtedy w centrum laduja sie przypisane posilki.</p>

              {dietsLoading ? <p className="mt-4 text-sm text-slate-600">Ladowanie listy diet i posilkow...</p> : null}
              {dietsError ? <p className="mt-4 text-sm font-semibold text-red-700">{dietsError}</p> : null}

              {!dietsLoading && !dietsError ? (
                <div className="mt-4 grid gap-6 lg:grid-cols-[260px_1fr]">
                  <aside className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">Dostepne diety</p>
                    <div className="max-h-[520px] overflow-y-auto pr-1">
                      <div className="grid gap-2">
                        {diets.map((diet) => {
                          const calorieOptions = caloriesByDietId[diet.id] ?? [];
                          const isExpanded = expandedDietId === diet.id;

                          return (
                            <div key={diet.id} className="rounded-lg border border-slate-300 bg-white p-2">
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedDietId(diet.id);
                                  setExpandedDietId((prev) => (prev === diet.id ? null : diet.id));
                                  setSelectedMealId(null);
                                }}
                                className="w-full rounded-lg px-2 py-2 text-left text-sm font-semibold text-slate-800 hover:bg-slate-100"
                              >
                                {diet.dieta}
                              </button>

                              {isExpanded ? (
                                <div className="mt-2 grid gap-1 px-1 pb-1">
                                  {calorieOptions.length ? (
                                    calorieOptions.map((option) => {
                                      const optionLabel = option.czysta_kalorycznosc
                                        ? `${option.czysta_kalorycznosc} kcal`
                                        : option.kalorycznosc || "opcja kcal";
                                      const isSelected = selectedDietCalorieId === option.id;

                                      return (
                                        <button
                                          key={option.id}
                                          type="button"
                                          onClick={() => {
                                            setSelectedDietId(diet.id);
                                            setSelectedDietCalorieId(option.id);
                                            setMealsPage(1);
                                            setSelectedMealId(null);
                                          }}
                                          className={`rounded-md px-2 py-1 text-left text-xs font-semibold ${
                                            isSelected
                                              ? "bg-slate-900 text-white"
                                              : "border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                                          }`}
                                        >
                                          {optionLabel}
                                        </button>
                                      );
                                    })
                                  ) : (
                                    <p className="px-2 py-1 text-xs text-slate-500">Brak opcji kcal dla tej diety.</p>
                                  )}
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </aside>

                  <section>
                    <h3 className="text-base font-semibold">
                      {selectedDiet
                        ? `Posilki dla diety: ${selectedDiet.dieta}${selectedDietCalorie ? ` (${selectedDietCalorieLabel})` : ""}`
                        : "Wybierz diete z listy"}
                    </h3>

                    {selectedDiet && !selectedDietCalorie ? (
                      <p className="mt-2 text-sm text-slate-600">Wybierz opcje kcal dla diety, aby zaladowac posilki.</p>
                    ) : null}

                    {selectedDiet && selectedDietCalorie ? (
                      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-sm font-semibold text-slate-800">Filtry posilkow</p>

                        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                          <input
                            type="text"
                            value={mealFilters.nazwaPosilku}
                            onChange={(event) => {
                              setMealFilters((prev) => ({ ...prev, nazwaPosilku: event.target.value }));
                              setMealsPage(1);
                            }}
                            placeholder="nazwa-posilku"
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />

                          <input
                            type="text"
                            value={mealFilters.poraPosilku}
                            onChange={(event) => {
                              setMealFilters((prev) => ({ ...prev, poraPosilku: event.target.value }));
                              setMealsPage(1);
                            }}
                            placeholder="pora-posilku"
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />

                          <input
                            type="text"
                            value={mealFilters.czasPrzygotowania}
                            onChange={(event) => {
                              setMealFilters((prev) => ({ ...prev, czasPrzygotowania: event.target.value }));
                              setMealsPage(1);
                            }}
                            placeholder="czas-przygotowania"
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />

                          <input
                            type="number"
                            min={0}
                            value={mealFilters.czasPrzygotowaniaMaxMinut}
                            onChange={(event) => {
                              setMealFilters((prev) => ({ ...prev, czasPrzygotowaniaMaxMinut: event.target.value }));
                              setMealsPage(1);
                            }}
                            placeholder="czas-przygotowania-max-minut"
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />

                          <input
                            type="number"
                            min={0}
                            value={mealFilters.czystaKalorycznosc}
                            onChange={(event) => {
                              setMealFilters((prev) => ({ ...prev, czystaKalorycznosc: event.target.value }));
                              setMealsPage(1);
                            }}
                            placeholder="czysta-kalorycznosc"
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          />

                          <select
                            value={mealFilters.sortowanieCena}
                            onChange={(event) => {
                              const value = event.target.value as MealFilters["sortowanieCena"];
                              setMealFilters((prev) => ({ ...prev, sortowanieCena: value }));
                              setMealsPage(1);
                            }}
                            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                          >
                            <option value="">sortowanie-cena (brak)</option>
                            <option value="najtansze">sortowanie-cena: najtansze</option>
                            <option value="najdrozsze">sortowanie-cena: najdrozsze</option>
                          </select>
                        </div>

                        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                          <span className="rounded bg-white px-2 py-1">dieta-id: {selectedDietId}</span>
                          <span className="rounded bg-white px-2 py-1">kalorycznosc-diety-id: {selectedDietCalorieId}</span>
                          <span className="rounded bg-white px-2 py-1">
                            kalorycznosc-id: {selectedDietCalorie?.kalorycznosc_id ?? "brak"}
                          </span>
                          <span className="rounded bg-white px-2 py-1">page: {mealsPage}</span>
                        </div>

                        <button
                          type="button"
                          onClick={() => {
                            setMealFilters((prev) => ({
                              ...prev,
                              nazwaPosilku: "",
                              poraPosilku: "",
                              czasPrzygotowania: "",
                              czasPrzygotowaniaMaxMinut: "",
                              czystaKalorycznosc:
                                typeof selectedDietCalorie?.czysta_kalorycznosc === "number"
                                  ? String(selectedDietCalorie.czysta_kalorycznosc)
                                  : "",
                              sortowanieCena: "",
                            }));
                            setMealsPage(1);
                            setSelectedMealId(null);
                          }}
                          className="mt-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                        >
                          Wyczysc filtry
                        </button>
                      </div>
                    ) : null}

                    {mealsLoading ? <p className="mt-3 text-sm text-slate-600">Ladowanie posilkow...</p> : null}
                    {mealsError ? <p className="mt-3 text-sm font-semibold text-red-700">{mealsError}</p> : null}

                    {!mealsLoading && !mealsError ? (
                      <div className="mt-4 grid gap-3 xl:grid-cols-2">
                        {meals.map((meal) => {
                          const isExpanded = selectedMealId === meal.id;
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
                          {dietNameById[meal.dieta_id] ?? `Dieta #${meal.dieta_id}`}
                        </p>
                        <h3 className="mt-1 text-base font-semibold text-slate-900">{meal.nazwa_posilku}</h3>
                        <p className="mt-1 text-sm text-slate-700">Pora: {meal.pora_posilku || "brak danych"}</p>
                        <p className="text-sm text-slate-700">Czas: {meal.czas_przygotowania || "brak danych"}</p>
                        <p className="text-sm text-slate-700">Kalorie: {meal.kalorie || "brak danych"}</p>
                        <button
                          type="button"
                          onClick={() => setSelectedMealId((prev) => (prev === meal.id ? null : meal.id))}
                          className="mt-3 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800"
                        >
                          {isExpanded ? "Ukryj szczegoly" : "Wejdz w szczegoly posilku"}
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setMealToScheduleId(meal.id);
                            setMealScheduleDate(getTodayDateForInput());
                            setMealSchedulingMessage("");
                          }}
                          className="mt-3 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                        >
                          Zaplanuj posilek
                        </button>

                        {isExpanded ? (
                          <section className="mt-4 rounded-xl border border-slate-300 bg-white p-4">
                            <h3 className="text-base font-semibold">Szczegoly: {meal.nazwa_posilku}</h3>
                            <p className="mt-1 text-sm text-slate-700">Dieta: {dietNameById[meal.dieta_id] ?? `#${meal.dieta_id}`}</p>
                            <p className="text-sm text-slate-700">Pora: {meal.pora_posilku || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Czas przygotowania: {meal.czas_przygotowania || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Cena: {meal.cena_posilku || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Kalorie: {meal.kalorie || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Bialko: {meal.bialko || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Weglowodany: {meal.weglowodany || "brak danych"}</p>
                            <p className="text-sm text-slate-700">Tluszcze: {meal.tluszcze || "brak danych"}</p>
                            {meal.opis_posilku ? (
                              <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{meal.opis_posilku}</p>
                            ) : null}

                            <div className="mt-3">
                              <p className="text-sm font-semibold text-slate-800">Skladniki</p>
                              {meal.skladniki?.length ? (
                                <ul className="mt-2 list-disc pl-5 text-sm text-slate-700">
                                  {meal.skladniki.map((ingredient) => (
                                    <li key={`${ingredient.nazwa_produktu}-${ingredient.miarka}`}>
                                      {ingredient.nazwa_produktu}: {ingredient.ilosc_produktu} {ingredient.miarka}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="mt-2 text-sm text-slate-600">Brak danych o skladnikach.</p>
                              )}
                            </div>
                          </section>
                        ) : null}
                          </article>
                        );
                        })}
                      </div>
                    ) : null}

                    {!mealsLoading && !mealsError && selectedDietCalorieId && !meals.length ? (
                      <p className="mt-4 text-sm text-slate-600">Brak posilkow dla wybranej diety.</p>
                    ) : null}

                    {selectedDiet && selectedDietCalorieId ? (
                      <div className="mt-4 flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3">
                        <p className="text-sm text-slate-700">
                          Strona {mealsPage} z {totalMealPages} ({mealsCount} posilkow)
                        </p>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setMealsPage((prev) => Math.max(1, prev - 1));
                              setSelectedMealId(null);
                            }}
                            disabled={mealsPage <= 1 || mealsLoading}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Poprzednia
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setMealsPage((prev) => Math.min(totalMealPages, prev + 1));
                              setSelectedMealId(null);
                            }}
                            disabled={mealsPage >= totalMealPages || mealsLoading}
                            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            Nastepna
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {mealToScheduleId ? (
                      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                        <div className="rounded-2xl border border-slate-200 bg-white shadow-lg max-w-sm w-full mx-4">
                          <div className="border-b border-slate-200 p-4">
                            <h2 className="text-lg font-semibold text-slate-900">Zaplanuj posilek</h2>
                          </div>
                        <div className="p-4">
                            <label className="block text-xs font-semibold text-slate-700">Wybierz datę</label>
                            <input
                              type="date"
                              value={mealScheduleDate}
                              onChange={(event) => setMealScheduleDate(event.target.value)}
                              className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                            />
                            {mealSchedulingMessage && (
                              <p className={`mt-3 text-sm ${mealSchedulingMessage.includes("✓") ? "text-emerald-700" : "text-red-700"}`}>
                                {mealSchedulingMessage}
                              </p>
                            )}
                            <div className="mt-4 flex gap-2">
                              <button
                                type="button"
                                onClick={() => {
                                  setMealToScheduleId(null);
                                  setMealSchedulingMessage("");
                                }}
                                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                              >
                                Anuluj
                              </button>
                              <button
                                type="button"
                                onClick={() => scheduleMealFromDiet(mealToScheduleId)}
                                disabled={mealSchedulingLoading}
                                className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {mealSchedulingLoading ? "Planowanie..." : "Zaplanuj"}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : null}

                  </section>
                </div>
              ) : null}
            </div>
          ) : null}

          {activeTab === "tablica" ? (
            <div className="mt-6 max-w-4xl rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-800">Dieta i kalorycznosc rodziny</p>

              {familyOverviewLoading ? <p className="mt-3 text-sm text-slate-600">Ladowanie danych rodziny...</p> : null}
              {familyOverviewError ? <p className="mt-3 text-sm font-semibold text-red-700">{familyOverviewError}</p> : null}

              {!familyOverviewLoading && !familyOverviewError ? (
                familyMembers.length ? (
                  <>
                    <p className="mt-3 text-sm text-slate-700">Rodzina: {familyNameOverview || "(bez nazwy)"}</p>
                    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200 bg-white">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-100 text-left text-slate-700">
                          <tr>
                            <th className="px-3 py-2 font-semibold">Czlonek</th>
                            <th className="px-3 py-2 font-semibold">Rola</th>
                            <th className="px-3 py-2 font-semibold">Dieta</th>
                            <th className="px-3 py-2 font-semibold">Kalorycznosc</th>
                          </tr>
                        </thead>
                        <tbody>
                          {familyMembers.map((member) => (
                            <tr key={member.id} className="border-t border-slate-200">
                              <td className="px-3 py-2 text-slate-800">{member.first_name || member.username}</td>
                              <td className="px-3 py-2 text-slate-700">{member.is_founder ? "Zalozyciel" : "Czlonek"}</td>
                              <td className="px-3 py-2 text-slate-700">{member.dieta || "brak"}</td>
                              <td className="px-3 py-2 text-slate-700">
                                {typeof member.czysta_kalorycznosc === "number"
                                  ? `${member.czysta_kalorycznosc} kcal`
                                  : member.kalorycznosc || "brak"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">Uzytkownik nie nalezy jeszcze do zadnej rodziny.</p>
                )
              ) : null}
            </div>
          ) : null}

          {activeTab === "kalendarz" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_360px]">
              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-slate-800">Kalendarz posilkow</h2>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <input
                      type="date"
                      value={calendarPdfFromDate}
                      onChange={(event) => setCalendarPdfFromDate(event.target.value)}
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
                      title="PDF data od"
                    />
                    <input
                      type="date"
                      value={calendarPdfToDate}
                      onChange={(event) => setCalendarPdfToDate(event.target.value)}
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700"
                      title="PDF data do"
                    />
                    <button
                      type="button"
                      onClick={generateCalendarPdfForDateRange}
                      disabled={calendarPdfGenerating}
                      className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {calendarPdfGenerating ? "Generowanie PDF..." : "Wygeneruj PDF"}
                    </button>
                    <button
                      type="button"
                      onClick={createShoppingListFromVisibleCalendarDays}
                      disabled={calendarShoppingListCreating || !visibleCalendarMealsByDate.length}
                      className="rounded-lg bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {calendarShoppingListCreating ? "Tworzenie listy..." : "Utworz liste zakupow z miesiaca"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void fetchCalendarMealsForMonth(calendarViewDate)}
                      disabled={calendarMealsLoading}
                      className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                      title="Odśwież kalendarz"
                    >
                      ↻
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const prev = new Date(calendarViewDate);
                        prev.setMonth(prev.getMonth() - 1);
                        setCalendarViewDate(formatDateForInput(prev));
                      }}
                      className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      ◀
                    </button>
                    <span className="text-sm font-semibold text-slate-700 px-3 py-1">
                      {new Date(calendarViewDate).toLocaleDateString("pl-PL", { month: "long", year: "numeric" })}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const next = new Date(calendarViewDate);
                        next.setMonth(next.getMonth() + 1);
                        setCalendarViewDate(formatDateForInput(next));
                      }}
                      className="rounded-lg border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                    >
                      ▶
                    </button>
                  </div>
                </div>
                {calendarMessage ? (
                  <p className="mb-3 text-sm text-slate-700">{calendarMessage}</p>
                ) : null}

                {calendarMealsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <p className="text-sm text-slate-600">⏳ Ładowanie kalendarza...</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {visibleCalendarMealsByDate.length > 0 ? (
                      visibleCalendarMealsByDate.map(([date, mealsOnDate]) => (
                          <div key={date} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                            <p className="text-xs font-semibold text-slate-700 mb-2">
                              {new Date(date).toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })}
                            </p>
                            <div className="space-y-1">
                              {[...mealsOnDate]
                                .sort((a, b) => {
                                  if (Boolean(a.czy_zjedzone) !== Boolean(b.czy_zjedzone)) {
                                    return a.czy_zjedzone ? 1 : -1;
                                  }
                                  const orderDiff = getMealTimeOrder(a.pora_posilku) - getMealTimeOrder(b.pora_posilku);
                                  if (orderDiff !== 0) {
                                    return orderDiff;
                                  }
                                  return String(a.pora_posilku || "").localeCompare(String(b.pora_posilku || ""), "pl");
                                })
                                .map((meal, idx) => {
                                const mealNames = meal.zaplanowane_posilki
                                  ?.map((item) => mealDetailById[item.posilek_w_diecie_id]?.nazwa_posilku)
                                  .filter(Boolean) ?? [];
                                const uniqueMealNames = Array.from(new Set(mealNames));
                                const representativeMealId = meal.zaplanowane_posilki?.[0]?.posilek_w_diecie_id;
                                const representativeMeal = representativeMealId
                                  ? mealDetailById[representativeMealId]
                                  : undefined;
                                const thumbnailUrl = resolveBackendAssetUrl(
                                  representativeMeal?.zdjecie_url,
                                  process.env.NEXT_PUBLIC_API_BASE_URL,
                                );
                                const plannedByNames = meal.zaplanowane_posilki
                                  ?.map(
                                    (item) =>
                                      calendarMemberNameByUserId[item.uzytkownik_id] ||
                                      `Uzytkownik ${item.uzytkownik_id}`,
                                  ) ?? [];
                                const uniquePlannedByNames = Array.from(new Set(plannedByNames));
                                
                                return (
                                  <button
                                    key={idx}
                                    type="button"
                                    onClick={() => {
                                      const clickedRepresentativeMealId =
                                        meal.zaplanowane_posilki?.[0]?.posilek_w_diecie_id ?? null;
                                      setSelectedCalendarMealDetailId(clickedRepresentativeMealId);
                                      setSelectedCalendarMeal({date, meal});
                                    }}
                                    className="w-full text-left rounded-lg border border-emerald-200 bg-emerald-50 p-2 text-xs hover:bg-emerald-100 transition"
                                  >
                                    <div className="flex items-start gap-2">
                                      {thumbnailUrl ? (
                                        <img
                                          src={thumbnailUrl}
                                          alt={representativeMeal?.nazwa_posilku || "Posilek"}
                                          className="h-10 w-10 rounded-md object-cover border border-emerald-100"
                                          loading="lazy"
                                        />
                                      ) : (
                                        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-100 text-[10px] font-semibold text-emerald-700">
                                          Brak
                                        </div>
                                      )}
                                      <div className="min-w-0 flex-1">
                                        <p className="font-semibold text-emerald-900">
                                          {meal.pora_posilku ? `${meal.pora_posilku}` : "Posiłek"}
                                        </p>
                                        {uniqueMealNames.length > 0 && (
                                          <p className="text-emerald-800 text-xs mt-1 truncate">
                                            {uniqueMealNames.join(", ")}
                                          </p>
                                        )}
                                        {uniquePlannedByNames.length > 0 && (
                                          <p className="text-emerald-700 text-xs mt-1">
                                            Zaplanowal: {uniquePlannedByNames.join(", ")}
                                          </p>
                                        )}
                                        <p className="text-emerald-700 text-xs mt-1">
                                          {meal.zaplanowane_posilki?.length ?? 0} osób
                                        </p>
                                      </div>
                                    </div>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ))
                    ) : (
                      <div className="rounded-lg bg-slate-50 p-4 text-center">
                        <p className="text-sm font-semibold text-slate-700">Brak zaplanowanych posiłków</p>
                        <p className="mt-1 text-xs text-slate-600">
                          Zaplanuj posiłki w zakładce Diety, klikając przycisk "Zaplanuj posiłek" na każdej karcie posiłku.
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </section>

              {selectedCalendarMeal ? (
                <section className="rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-slate-800">Szczegoly posilku</h2>
                    <button
                      type="button"
                      onClick={() => setSelectedCalendarMeal(null)}
                      className="text-slate-500 hover:text-slate-700"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-semibold text-slate-700 mb-2">
                      {new Date(selectedCalendarMeal.date).toLocaleDateString("pl-PL", { 
                        weekday: "long", 
                        day: "numeric", 
                        month: "long",
                        year: "numeric"
                      })}
                    </p>
                    {selectedCalendarMealIds.length ? (
                      <div className="mb-3 space-y-2">
                        {selectedCalendarMealIds.map((mealId) => {
                          const mealDetails = mealDetailById[mealId];
                          const imageUrl = resolveBackendAssetUrl(
                            mealDetails?.zdjecie_url,
                            process.env.NEXT_PUBLIC_API_BASE_URL,
                          );

                          return (
                            <button
                              key={mealId}
                              type="button"
                              onClick={() => setSelectedCalendarMealDetailId(mealId)}
                              className={`flex w-full items-center gap-2 rounded-lg border bg-white p-2 text-left ${
                                selectedCalendarMealDetailId === mealId
                                  ? "border-emerald-500 ring-1 ring-emerald-300"
                                  : "border-slate-200 hover:border-emerald-300"
                              }`}
                            >
                              {imageUrl ? (
                                <img
                                  src={imageUrl}
                                  alt={mealDetails?.nazwa_posilku || `Posilek #${mealId}`}
                                  className="h-24 w-24 rounded-md object-cover"
                                  loading="lazy"
                                />
                              ) : (
                                <div className="flex h-24 w-24 items-center justify-center rounded-md bg-slate-200 text-[10px] font-semibold text-slate-600">
                                  Brak
                                </div>
                              )}
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-slate-800">
                                  {mealDetails?.nazwa_posilku || `Posilek #${mealId}`}
                                </p>
                                <p className="text-xs text-slate-600">
                                  {mealDetails?.pora_posilku || selectedCalendarMeal.meal.pora_posilku || "Posilek"}
                                </p>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                    <p className="text-sm font-semibold text-slate-900">
                      Pora: {selectedCalendarMeal.meal.pora_posilku || "Nie określona"}
                    </p>
                    <p className="text-sm text-slate-700 mt-1">
                      Czy zjedzone: {selectedCalendarMeal.meal.czy_zjedzone ? "Tak" : "Nie"}
                    </p>
                    <p className="text-sm text-slate-700 mt-1">
                      Liczba osób: {selectedCalendarMeal.meal.liczba_osob_przy_posilku ?? "-"}
                    </p>
                    <p className="text-sm text-slate-700 mt-1">
                      Liczba czlonkow rodziny: {selectedCalendarMeal.meal.liczba_czlonkow_rodziny ?? "-"}
                    </p>
                    <button
                      type="button"
                      onClick={markSelectedCalendarMealAsEaten}
                      disabled={
                        calendarMealMarkingEaten ||
                        !selectedCalendarMeal.meal.planned_meal_id ||
                        Boolean(selectedCalendarMeal.meal.czy_zjedzone)
                      }
                      className="mt-3 mr-2 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                      title={!selectedCalendarMeal.meal.planned_meal_id ? "Brak identyfikatora wpisu" : ""}
                    >
                      {calendarMealMarkingEaten ? "Oznaczanie..." : "Zjedzony (odejmij z magazynu)"}
                    </button>
                    <button
                      type="button"
                      onClick={removeSelectedCalendarMeal}
                      disabled={calendarMealRemoving || !selectedCalendarMeal.meal.planned_meal_id}
                      className="mt-3 rounded-lg bg-rose-700 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-800 disabled:cursor-not-allowed disabled:opacity-60"
                      title={!selectedCalendarMeal.meal.planned_meal_id ? "Brak identyfikatora wpisu do usuniecia" : ""}
                    >
                      {calendarMealRemoving ? "Usuwanie..." : "Usun zaplanowany posilek"}
                    </button>
                    <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
                      <p className="text-sm font-semibold text-slate-800">Jak przygotowac</p>
                      {selectedCalendarMealDetail?.opis_posilku ? (
                        <p className="mt-2 text-sm text-slate-700 whitespace-pre-line">
                          {selectedCalendarMealDetail.opis_posilku}
                        </p>
                      ) : (
                        <p className="mt-2 text-xs text-slate-600">Brak opisu przygotowania dla tego posilku.</p>
                      )}
                      {selectedCalendarMealDetail?.skladniki?.length ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold text-slate-700">Skladniki:</p>
                          <ul className="mt-1 space-y-1 text-xs text-slate-700">
                            {selectedCalendarMealDetail.skladniki.map((ingredient, idx) => (
                              <li key={`${ingredient.nazwa_produktu}-${idx}`}>
                                {ingredient.nazwa_produktu} - {ingredient.ilosc_produktu} {ingredient.miarka}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                    <div className="mt-3 rounded-lg border border-slate-200 bg-white p-2">
                      <p className="text-xs font-semibold text-slate-700 mb-2">Zaplanowani użytkownicy:</p>
                      {selectedCalendarMeal.meal.zaplanowane_posilki?.length ? (
                        <div className="space-y-2 text-xs text-slate-600">
                          {Object.entries(
                            selectedCalendarMeal.meal.zaplanowane_posilki.reduce<Record<string, number[]>>(
                              (acc, item) => {
                                const userKey = String(item.uzytkownik_id ?? "0");
                                if (!acc[userKey]) {
                                  acc[userKey] = [];
                                }
                                acc[userKey].push(item.posilek_w_diecie_id);
                                return acc;
                              },
                              {},
                            ),
                          ).map(([userId, mealIds]) => {
                            const plannerName =
                              calendarMemberNameByUserId[Number(userId)] || `Uzytkownik ${userId}`;
                            return (
                              <div key={userId} className="rounded-lg border border-slate-200 bg-slate-50 p-2">
                                <p className="text-xs font-semibold text-slate-700">{plannerName}</p>
                                <ul className="mt-1 space-y-1">
                                  {mealIds.map((mealId, idx) => {
                                    const mealName =
                                      mealDetailById[mealId]?.nazwa_posilku || `Posilek #${mealId}`;
                                    return (
                                      <li key={`${userId}-${mealId}-${idx}`} className="text-slate-600">
                                        {mealName}
                                      </li>
                                    );
                                  })}
                                </ul>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-600">Brak zaplanowanych użytkowników</p>
                      )}
                    </div>
                  </div>
                </section>
              ) : null}
            </div>
          ) : null}

          {activeTab === "lista-zakupow" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-[360px_1fr]">
              <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Generuj z kalendarza</p>

                <label className="mt-4 block text-xs font-semibold text-slate-700">Data od</label>
                <input
                  type="date"
                  value={shoppingListFromDate}
                  onChange={(event) => setShoppingListFromDate(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />

                <label className="mt-3 block text-xs font-semibold text-slate-700">Data do</label>
                <input
                  type="date"
                  value={shoppingListToDate}
                  onChange={(event) => setShoppingListToDate(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />

                <label className="mt-3 block text-xs font-semibold text-slate-700">Nazwa listy</label>
                <input
                  type="text"
                  value={shoppingListName}
                  onChange={(event) => setShoppingListName(event.target.value)}
                  placeholder="np. Zakupy na tydzien"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />

                <button
                  type="button"
                  onClick={createShoppingListFromCalendar}
                  disabled={creatingShoppingList}
                  className="mt-4 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {creatingShoppingList ? "Generowanie..." : "Utworz liste zakupow"}
                </button>

                {shoppingMessage ? <p className="mt-3 text-sm text-slate-700">{shoppingMessage}</p> : null}
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-800">Listy zakupow rodziny</p>
                  <button
                    type="button"
                    onClick={() => void refreshShoppingLists()}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Odswiez
                  </button>
                </div>

                {shoppingListsLoading ? <p className="mt-3 text-sm text-slate-600">Ladowanie list...</p> : null}
                {shoppingListsError ? <p className="mt-3 text-sm font-semibold text-red-700">{shoppingListsError}</p> : null}

                {!shoppingListsLoading && !shoppingListsError ? (
                  shoppingLists.length ? (
                    <div className="mt-3 grid gap-2">
                      {shoppingLists.map((list) => (
                        <button
                          key={list.id}
                          type="button"
                          onClick={() => void fetchShoppingListDetail(list.id)}
                          className={`w-full rounded-lg border bg-slate-50 p-3 text-left ${
                            selectedShoppingListId === list.id
                              ? "border-emerald-500 ring-1 ring-emerald-300"
                              : "border-slate-200 hover:border-emerald-300"
                          }`}
                        >
                          <p className="text-sm font-semibold text-slate-900">{list.nazwa_listy_zakupow}</p>
                          <p className="mt-1 text-xs text-slate-600">
                            {list.data_od} - {list.data_do}
                          </p>
                          <p className="mt-1 text-xs text-slate-700">Pozycji: {list.liczba_pozycji_na_liscie}</p>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-slate-600">Brak list zakupow dla rodziny.</p>
                  )
                ) : null}

                {shoppingListDetailLoading ? (
                  <p className="mt-4 text-sm text-slate-600">Ladowanie produktow listy...</p>
                ) : null}
                {shoppingListDetailError ? (
                  <p className="mt-4 text-sm font-semibold text-red-700">{shoppingListDetailError}</p>
                ) : null}
                {selectedShoppingListDetail && !shoppingListDetailLoading ? (
                  <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800">Wymagane skladniki</p>
                      <button
                        type="button"
                        onClick={() => void markAllShoppingListProductsAsBought()}
                        disabled={markingAllBought || !selectedShoppingListDetail.produkty.length}
                        className="rounded-lg bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {markingAllBought ? "Przenoszenie..." : "Kupione wszystko"}
                      </button>
                    </div>
                    <p className="mt-1 text-xs text-slate-600">
                      {selectedShoppingListDetail.nazwa_listy_zakupow} ({selectedShoppingListDetail.data_od} - {selectedShoppingListDetail.data_do})
                    </p>
                    {selectedShoppingListDetail.produkty.length ? (
                      <div className="mt-3 grid gap-2">
                        {selectedShoppingListDetail.produkty.map((product) => (
                          <div key={`${selectedShoppingListDetail.id}-${product.produkt_id}`} className="rounded-md border border-slate-200 bg-white p-2">
                            <p className="text-sm font-semibold text-slate-800">{product.nazwa_produktu}</p>
                            <p className="text-xs text-slate-600">{product.ilosc_produktu_do_kupienia}</p>
                            {product.kategoria_nazwa ? (
                              <p className="text-xs text-slate-500">Kategoria: {product.kategoria_nazwa}</p>
                            ) : null}
                            <button
                              type="button"
                              onClick={() =>
                                void markShoppingListProductAsBought(
                                  selectedShoppingListDetail.id,
                                  product.produkt_id,
                                )
                              }
                              disabled={markingBoughtProductId === product.produkt_id || markingAllBought}
                              className="mt-2 rounded-lg bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {markingBoughtProductId === product.produkt_id ? "Przenoszenie..." : "Kupione"}
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-xs text-slate-600">Brak produktow do kupienia na tej liscie.</p>
                    )}
                  </div>
                ) : null}
              </section>
            </div>
          ) : null}

          {activeTab === "magazyn" ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-[360px_1fr]">
              <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-800">Aktualizuj produkt w magazynie</p>

                <label className="mt-4 block text-xs font-semibold text-slate-700">Wyszukaj produkt po nazwie</label>
                <input
                  type="text"
                  value={warehouseProductSearch}
                  onChange={(event) => setWarehouseProductSearch(event.target.value)}
                  placeholder="np. ryz, mleko, kurczak..."
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
                {warehouseProductSearch.trim() ? (
                  <div className="mt-2 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
                    {warehouseSearchLoading ? (
                      <p className="text-xs text-slate-500">Wyszukiwanie produktow...</p>
                    ) : warehouseSearchResults.length ? (
                      <div className="grid gap-1">
                        {warehouseSearchResults.map((product) => (
                          <button
                            key={`search-${product.id}`}
                            type="button"
                            onClick={() => {
                              setSelectedWarehouseProductId(product.id);
                              setWarehouseProductId(String(product.id));
                              setWarehouseProductSearch(product.nazwa_produktu_uproszczonego);
                              const inWarehouse = (warehouse?.produkty ?? []).find((item) => item.produkt_id === product.id);
                              if (inWarehouse) {
                                setWarehouseProductAmount(String(inWarehouse.ilosc_produktu));
                                setWarehouseMessage(`Wybrano produkt ${inWarehouse.nazwa_produktu} do edycji.`);
                              } else {
                                setWarehouseProductAmount("");
                                setWarehouseMessage("Wybrany produkt nie jest jeszcze w magazynie rodziny.");
                              }
                            }}
                            className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-left text-xs text-slate-700 hover:border-emerald-300 hover:bg-emerald-50"
                          >
                            {product.nazwa_produktu_uproszczonego} (id: {product.id})
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">Brak produktow pasujacych do frazy w bazie.</p>
                    )}
                  </div>
                ) : null}

                <label className="mt-4 block text-xs font-semibold text-slate-700">produkt_id</label>
                <input
                  type="number"
                  min={1}
                  value={warehouseProductId}
                  onChange={(event) => {
                    setWarehouseProductId(event.target.value);
                    setSelectedWarehouseProductId(event.target.value ? Number(event.target.value) : null);
                  }}
                  placeholder="np. 630"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />

                <label className="mt-3 block text-xs font-semibold text-slate-700">Ilosc produktu</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={warehouseProductAmount}
                  onChange={(event) => setWarehouseProductAmount(event.target.value)}
                  placeholder="0 usuwa produkt"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={updateWarehouseProduct}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
                  >
                    Zapisz ilosc
                  </button>
                  <button
                    type="button"
                    onClick={clearWarehouse}
                    className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-800"
                  >
                    Wyczysc magazyn
                  </button>
                </div>

                {warehouseMessage ? <p className="mt-3 text-sm text-slate-700">{warehouseMessage}</p> : null}
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-800">Magazyn rodziny</p>
                  <button
                    type="button"
                    onClick={() => void refreshWarehouse()}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  >
                    Odswiez
                  </button>
                </div>

                {warehouseLoading ? <p className="mt-3 text-sm text-slate-600">Ladowanie magazynu...</p> : null}

                {!warehouseLoading ? (
                  <>
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs text-slate-600">Pozycji</p>
                        <p className="mt-1 text-lg font-semibold">{warehouse?.liczba_pozycji ?? 0}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs text-slate-600">Pokrycie posilkow</p>
                        <p className="mt-1 text-lg font-semibold">{warehouseCoverage?.coverage_percent ?? 0}%</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs text-slate-600">Mozliwe posilki</p>
                        <p className="mt-1 text-lg font-semibold">{possibleMeals.length}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid gap-2">
                      {warehouse?.produkty?.length ? (
                        warehouse.produkty.map((product) => (
                          <button
                            key={product.produkt_id}
                            type="button"
                            onClick={() => {
                              setSelectedWarehouseProductId(product.produkt_id);
                              setWarehouseProductId(String(product.produkt_id));
                              setWarehouseProductAmount(String(product.ilosc_produktu));
                              setWarehouseProductSearch(product.nazwa_produktu);
                              setWarehouseMessage(`Wybrano produkt ${product.nazwa_produktu} do edycji.`);
                            }}
                            className={`w-full rounded-lg border p-3 text-left ${
                              selectedWarehouseProductId === product.produkt_id
                                ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-300"
                                : "border-slate-200 bg-slate-50 hover:border-emerald-300"
                            }`}
                          >
                            <p className="text-sm font-semibold text-slate-900">{product.nazwa_produktu}</p>
                            <p className="mt-1 text-xs text-slate-700">
                              produkt_id: {product.produkt_id} | ilosc: {product.ilosc_produktu}
                            </p>
                          </button>
                        ))
                      ) : (
                        <p className="text-sm text-slate-600">Magazyn jest pusty.</p>
                      )}
                    </div>

                    {possibleMeals.length ? (
                      <div className="mt-5">
                        <p className="text-sm font-semibold text-slate-800">Posilki mozliwe z lodowki</p>
                        <div className="mt-2 grid gap-2">
                          {possibleMeals.slice(0, 5).map((meal) => (
                            <article key={meal.posilek_w_diecie_id} className="rounded-lg border border-slate-200 bg-white p-3">
                              <p className="text-sm font-semibold">{meal.nazwa_posilku}</p>
                              <p className="mt-1 text-xs text-slate-600">
                                {meal.pora_posilku || "brak pory"} | pokrycie: {meal.coverage_percent ?? 0}%
                              </p>
                            </article>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : null}
              </section>
            </div>
          ) : null}

          {activeTab === "konto" ? (
            <div className="mt-6 max-w-3xl rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-sm font-semibold text-slate-800">Ustawienia powiadomien</p>

              <label className="mt-3 flex items-start gap-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={notificationsConsent}
                  onChange={(event) => setNotificationsConsent(event.target.checked)}
                  className="mt-0.5 h-4 w-4"
                />
                <span>Czy zgadzasz sie na powiadomienia push na tym urzadzeniu?</span>
              </label>

              <button
                type="button"
                onClick={saveNotificationPreference}
                disabled={savingNotifications}
                className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {savingNotifications ? "Zapisywanie..." : "Zapisz ustawienie"}
              </button>

              {accountMessage ? <p className="mt-3 text-sm text-slate-700">{accountMessage}</p> : null}

              <div className="mt-6 border-t border-slate-200 pt-4">
                <p className="text-sm font-semibold text-slate-800">Wybor diety uzytkownika</p>
                <p className="mt-1 text-xs text-slate-600">
                  Ten wybor bedzie domyslnie zaznaczany w zakladce Diety po zalogowaniu.
                </p>

                <div className="mt-3 grid gap-3">
                  <select
                    value={accountSelectedDietId ?? ""}
                    onChange={(event) => {
                      const rawValue = event.target.value;
                      const nextDietId = rawValue ? Number(rawValue) : null;
                      setAccountSelectedDietId(nextDietId);
                      setAccountSelectedDietCalorieId(null);
                    }}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">Wybierz diete</option>
                    {diets.map((diet) => (
                      <option key={diet.id} value={diet.id}>
                        {diet.dieta}
                      </option>
                    ))}
                  </select>

                  <select
                    value={accountSelectedDietCalorieId ?? ""}
                    onChange={(event) => {
                      const rawValue = event.target.value;
                      setAccountSelectedDietCalorieId(rawValue ? Number(rawValue) : null);
                    }}
                    disabled={!accountSelectedDietId || !accountDietCalorieOptions.length}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <option value="">Wybierz kalorycznosc</option>
                    {accountDietCalorieOptions.map((option) => (
                      <option key={option.id} value={option.id}>
                        {typeof option.czysta_kalorycznosc === "number"
                          ? `${option.czysta_kalorycznosc} kcal`
                          : option.kalorycznosc || "opcja kcal"}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    onClick={saveUserDietPreference}
                    disabled={savingUserDiet || !accountSelectedDietCalorieId}
                    className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {savingUserDiet ? "Zapisywanie diety..." : "Zapisz wybor diety"}
                  </button>
                </div>
              </div>

              <div className="mt-6 border-t border-slate-200 pt-4">
                <p className="text-sm font-semibold text-slate-800">Zarzadzanie rodzina</p>
                <p className="mt-1 text-xs text-slate-600">Tworzenie rodziny, wysylanie zaproszen i opuszczenie rodziny.</p>

                <div className="mt-3 grid gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-sm font-semibold text-slate-800">Utworz rodzine</p>
                    <input
                      type="text"
                      value={familyName}
                      onChange={(event) => setFamilyName(event.target.value)}
                      placeholder="Nazwa rodziny"
                      className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={createFamily}
                      disabled={creatingFamily}
                      className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {creatingFamily ? "Tworzenie..." : "Utworz rodzine"}
                    </button>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-sm font-semibold text-slate-800">Wyslij zaproszenie do rodziny</p>
                    <input
                      type="email"
                      value={familyInviteEmail}
                      onChange={(event) => setFamilyInviteEmail(event.target.value)}
                      placeholder="email@example.com"
                      className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={sendFamilyInvitation}
                      disabled={sendingFamilyInvite}
                      className="mt-3 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {sendingFamilyInvite ? "Wysylanie..." : "Wyslij zaproszenie"}
                    </button>
                  </div>
                </div>

                <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-semibold text-slate-800">Opusc rodzine</p>
                  <p className="mt-1 text-xs text-slate-600">
                    Opcja dla czlonka rodziny. Zalozyciel rodziny nie moze opuscic rodziny tym przyciskiem.
                  </p>
                  <button
                    type="button"
                    onClick={leaveFamily}
                    disabled={leavingFamily}
                    className="mt-3 rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {leavingFamily ? "Opuszczanie..." : "Opusc rodzine"}
                  </button>
                </div>

                {familyMessage ? <p className="mt-3 text-sm text-slate-700">{familyMessage}</p> : null}
              </div>

              <div className="mt-6 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
                >
                  Wyloguj
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
