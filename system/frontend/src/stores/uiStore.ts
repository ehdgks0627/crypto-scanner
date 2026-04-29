import { create } from "zustand";

type Theme = "light" | "dark";

type UiState = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const initialTheme = (localStorage.getItem("pqc-theme") as Theme | null) ?? "light";

export const useUiStore = create<UiState>((set, get) => ({
  theme: initialTheme,
  setTheme: (theme) => {
    localStorage.setItem("pqc-theme", theme);
    document.documentElement.dataset.theme = theme;
    set({ theme });
  },
  toggleTheme: () => {
    const next = get().theme === "dark" ? "light" : "dark";
    localStorage.setItem("pqc-theme", next);
    document.documentElement.dataset.theme = next;
    set({ theme: next });
  }
}));

document.documentElement.dataset.theme = initialTheme;
