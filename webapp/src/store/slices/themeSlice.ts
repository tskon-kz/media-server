import { createSlice, type PayloadAction } from "@reduxjs/toolkit"

export type Appearance = "light" | "dark"
export type ThemeMode = "auto" | "light" | "dark"

interface ThemeState {
  mode: ThemeMode
  appearance: Appearance
}

const savedMode = localStorage.getItem("theme-mode") as ThemeMode | null
const initialMode: ThemeMode = savedMode === "light" || savedMode === "dark" ? savedMode : "auto"

const initialState: ThemeState = {
  mode: initialMode,
  appearance: "light",
}

const themeSlice = createSlice({
  name: "theme",
  initialState,
  reducers: {
    setMode(state, action: PayloadAction<{ mode: ThemeMode; appearance: Appearance }>) {
      state.mode = action.payload.mode
      state.appearance = action.payload.appearance
      localStorage.setItem("theme-mode", action.payload.mode)
    },
    setAppearance(state, action: PayloadAction<Appearance>) {
      state.appearance = action.payload
    },
  },
})

export const { setMode, setAppearance } = themeSlice.actions
export default themeSlice.reducer
