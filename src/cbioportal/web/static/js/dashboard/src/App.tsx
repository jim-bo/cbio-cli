import React, { useState } from 'react'
import { Responsive, WidthProvider, Layout } from 'react-grid-layout'
import ChartWidget from './components/ChartWidget'

const ResponsiveGridLayout = WidthProvider(Responsive)

interface AppProps {
  studyId: string
}

const App: React.FC<AppProps> = ({ studyId }) => {
  const [layout, setLayout] = useState<Layout[]>([
    { i: 'mutated-genes', x: 0, y: 0, w: 4, h: 4 },
    { i: 'cna-genes', x: 4, y: 0, w: 4, h: 4 },
    { i: 'sv-genes', x: 8, y: 0, w: 4, h: 4 },
    { i: 'cancer-type', x: 0, y: 4, w: 4, h: 4 },
    { i: 'gender', x: 4, y: 4, w: 4, h: 4 },
    { i: 'tmb-fga', x: 8, y: 4, w: 4, h: 6 },
  ])

  const onLayoutChange = (currentLayout: Layout[]) => {
    setLayout(currentLayout)
    // Optional: save to local storage or API
  }

  return (
    <div className="w-full bg-gray-50 p-4">
      <ResponsiveGridLayout
        className="layout"
        layouts={{ lg: layout }}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={30}
        draggableHandle=".drag-handle"
        onLayoutChange={onLayoutChange}
      >
        {layout.map((item) => (
          <div key={item.i}>
            <ChartWidget id={item.i} title={item.i.replace('-', ' ').replace('_', ' ').toUpperCase()} />
          </div>
        ))}
      </ResponsiveGridLayout>
    </div>
  )
}

export default App
