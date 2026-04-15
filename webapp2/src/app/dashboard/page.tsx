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
  }, [router]);

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

  const tabContent = useMemo(() => {
    switch (activeTab) {
      case "tablica":
        return "Podglad diety i kalorycznosci calej rodziny.";
      case "diety":
        return "Po lewej masz liste diet, a w centrum posilki z backendu po 10 na strone.";
      case "kalendarz":
        return "Tutaj bedzie kalendarz posilkow i zaplanowanych zdarzen.";
      case "lista-zakupow":
        return "Tutaj bedzie lista zakupow do odhaczenia.";
      case "magazyn":
        return "Tutaj bedzie stan magazynu produktow.";
      case "konto":
        return "Tutaj bedzie profil konta i ustawienia uzytkownika.";
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

  return (
    <main className="min-h-screen bg-slate-50 p-6 text-slate-900">
      <section className="mx-auto w-full max-w-6xl rounded-2xl border border-slate-200 bg-white shadow-sm">
        <header className="border-b border-slate-200 p-4">
          <h1 className="text-xl font-semibold">Dieta Studencka</h1>
          <p className="mt-1 text-sm text-slate-600">Panel glowny po zalogowaniu.</p>
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
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}
