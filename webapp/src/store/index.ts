import { configureStore } from "@reduxjs/toolkit"
import { useDispatch, useSelector } from "react-redux"
import searchReducer from "./slices/searchSlice"
import themeReducer from "./slices/themeSlice"

export const store = configureStore({
  reducer: {
    search: searchReducer,
    theme: themeReducer,
  },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch

export const useAppDispatch = () => useDispatch<AppDispatch>()
export const useAppSelector = <T>(selector: (state: RootState) => T): T => useSelector(selector)
