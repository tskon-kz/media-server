import { createSlice, type PayloadAction } from "@reduxjs/toolkit"
import type { SearchResult } from "@/types"

interface SearchState {
  query: string
  results: SearchResult[] | null
  loading: boolean
  pending: string[]
  page: number
}

const initialState: SearchState = {
  query: "",
  results: null,
  loading: false,
  pending: [],
  page: 1,
}

const bySeeders = (a: SearchResult, b: SearchResult) => b.seeders - a.seeders

const searchSlice = createSlice({
  name: "search",
  initialState,
  reducers: {
    setQuery(state, action: PayloadAction<string>) {
      state.query = action.payload
    },
    startSearch(state) {
      state.results = []
      state.loading = true
      state.pending = []
      state.page = 1
    },
    setPending(state, action: PayloadAction<string[]>) {
      state.pending = action.payload
    },
    appendResults(state, action: PayloadAction<SearchResult[]>) {
      state.results = [...(state.results ?? []), ...action.payload].sort(bySeeders)
    },
    finishSearch(state) {
      state.loading = false
      state.pending = []
    },
    setPage(state, action: PayloadAction<number>) {
      state.page = action.payload
    },
    clearSearch(state) {
      state.query = ""
      state.results = null
      state.loading = false
      state.pending = []
      state.page = 1
    },
  },
})

export const { setQuery, startSearch, setPending, appendResults, finishSearch, setPage, clearSearch } = searchSlice.actions
export default searchSlice.reducer
