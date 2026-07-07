import { createSlice, type PayloadAction } from "@reduxjs/toolkit"
import type { SearchResult } from "@/types"

interface SearchState {
  query: string
  results: SearchResult[] | null
  loading: boolean
  page: number
  total: number
}

const initialState: SearchState = {
  query: "",
  results: null,
  loading: false,
  page: 1,
  total: 0,
}

const searchSlice = createSlice({
  name: "search",
  initialState,
  reducers: {
    setQuery(state, action: PayloadAction<string>) {
      state.query = action.payload
    },
    setLoading(state, action: PayloadAction<boolean>) {
      state.loading = action.payload
    },
    setResults(state, action: PayloadAction<{ results: SearchResult[]; total: number; page: number }>) {
      state.results = action.payload.results
      state.total = action.payload.total
      state.page = action.payload.page
    },
    clearSearch(state) {
      state.query = ""
      state.results = null
      state.total = 0
      state.page = 1
      state.loading = false
    },
  },
})

export const { setQuery, setLoading, setResults, clearSearch } = searchSlice.actions
export default searchSlice.reducer
