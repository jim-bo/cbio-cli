import React, { useState, useEffect } from 'react'
import { Responsive, WidthProvider, Layout } from 'react-grid-layout'
import ChartWidget from './components/ChartWidget'
import { useDashboardStore } from './store/useDashboardStore'

const ResponsiveGridLayout = WidthProvider(Responsive)

interface AppProps {
  studyId: string
}

const App: React.FC<AppProps> = ({ studyId }) => {
  const setStudyId = useDashboardStore(state => state.setStudyId);
  const filters = useDashboardStore(state => state.filters);

  // Initialize studyId in store
  useEffect(() => {
    if (studyId) {
      console.log('App: Setting studyId', studyId);
      setStudyId(studyId);
    }
  }, [studyId, setStudyId]);

  const [layout, setLayout] = useState<Layout[]>([
    { i: 'mutated-genes', x: 0, y: 0, w: 4, h: 4 },
    { i: 'cna-genes', x: 4, y: 0, w: 4, h: 4 },
    { i: 'sv-genes', x: 8, y: 0, w: 4, h: 4 },
    { i: 'CANCER_TYPE', x: 0, y: 4, w: 4, h: 4 },
    { i: 'diagnosis-age', x: 4, y: 4, w: 4, h: 4 },
    { i: 'GENDER', x: 8, y: 4, w: 4, h: 4 },
    { i: 'tmb-fga', x: 0, y: 8, w: 4, h: 6 },
  ])

  const onLayoutChange = (currentLayout: Layout[]) => {
    setLayout(currentLayout)
  }

  const clinicalFilters = filters?.clinicalDataFilters || [];

  return (
    <div className="w-full bg-gray-50 p-4 min-h-screen">
      {/* Filter Summary Bar */}
      {clinicalFilters.length > 0 && (
        <div className="mb-4 p-2 bg-blue-50 border border-blue-100 rounded text-xs flex items-center space-x-2">
          <span className="font-bold text-blue-700">Filters:</span>
          {clinicalFilters.map(f => (
            <span key={f.attributeId} className="bg-white px-2 py-1 rounded border border-blue-200">
              {f.attributeId}: {Array.isArray(f.values) ? f.values.map(v => v.value || `${v.start}-${v.end}`).join(', ') : ''}
            </span>
          ))}
        </div>
      )}

      <ResponsiveGridLayout
        className="layout"
        layouts={{ lg: layout, md: layout, sm: layout, xs: layout, xxs: layout }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={30}
        draggableHandle=".drag-handle"
        onLayoutChange={onLayoutChange}
      >
        {layout.map((item) => (
          <div key={item.i}>
            <ChartWidget id={item.i} title={item.i.replace(/-/g, ' ').replace(/_/g, ' ').toUpperCase()} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  )
}

export default App
