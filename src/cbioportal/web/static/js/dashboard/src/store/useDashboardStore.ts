import { create } from 'zustand'

export interface ClinicalDataFilter {
  attributeId: string;
  values: { value?: string; start?: number; end?: number }[];
}

export interface MutationFilter {
  genes: string[];
}

export interface DashboardFilters {
  clinicalDataFilters: ClinicalDataFilter[];
  mutationFilter: MutationFilter;
}

interface DashboardState {
  studyId: string;
  filters: DashboardFilters;
  
  // Actions
  setStudyId: (id: string) => void;
  updateClinicalFilter: (attributeId: string, values: { value?: string; start?: number; end?: number }[]) => void;
  updateMutationFilter: (genes: string[]) => void;
  clearFilters: () => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  studyId: '',
  filters: {
    clinicalDataFilters: [],
    mutationFilter: { genes: [] }
  },

  setStudyId: (id) => set({ studyId: id }),

  updateClinicalFilter: (attributeId, values) => set((state) => {
    // Remove existing filter for this attribute if it exists
    const otherFilters = state.filters.clinicalDataFilters.filter(
      f => f.attributeId !== attributeId
    );
    
    // If no values provided, we effectively removed the filter
    const newClinicalFilters = values.length > 0 
      ? [...otherFilters, { attributeId, values }]
      : otherFilters;

    return {
      filters: {
        ...state.filters,
        clinicalDataFilters: newClinicalFilters
      }
    };
  }),

  updateMutationFilter: (genes) => set((state) => ({
    filters: {
      ...state.filters,
      mutationFilter: { genes }
    }
  })),

  clearFilters: () => set({
    filters: {
      clinicalDataFilters: [],
      mutationFilter: { genes: [] }
    }
  })
}));
