import React, { useRef, useState, useLayoutEffect, useEffect } from 'react'
import useResizeObserver from '@react-hook/resize-observer'
import PieChart from './charts/PieChart'
import TableChart from './charts/TableChart'
import BarChart from './charts/BarChart'
import { useDashboardStore } from '../store/useDashboardStore'

interface ChartWidgetProps {
  id: string
  title: string
}

const ChartWidget: React.FC<ChartWidgetProps> = ({ id, title }) => {
  const target = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState<DOMRectReadOnly | null>(null)
  const [data, setData] = useState<any>(null)
  const [chartType, setChartType] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const studyId = useDashboardStore(state => state.studyId)
  const filters = useDashboardStore(state => state.filters)
  const updateClinicalFilter = useDashboardStore(state => state.updateClinicalFilter)
  const updateMutationFilter = useDashboardStore(state => state.updateMutationFilter)

  useLayoutEffect(() => {
    if (target.current) {
      setSize(target.current.getBoundingClientRect())
    }
  }, [])

  useResizeObserver(target, (entry) => setSize(entry.contentRect))

  // Fetch data when filters or studyId changes
  useEffect(() => {
    if (!studyId) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        let endpoint = '/study/summary/chart/clinical';
        const formData = new FormData();
        formData.append('study_id', studyId);
        formData.append('filter_json', JSON.stringify(filters));

        if (id === 'mutated-genes') {
          endpoint = '/study/summary/chart/mutated-genes';
        } else if (id === 'cna-genes') {
          endpoint = '/study/summary/chart/cna-genes';
        } else if (id === 'sv-genes') {
          endpoint = '/study/summary/chart/sv-genes';
        } else if (id === 'diagnosis-age' || id === 'AGE') {
          endpoint = '/study/summary/chart/age';
        } else {
          formData.append('attribute_id', id);
        }

        const response = await fetch(`${endpoint}?format=json`, {
          method: 'POST',
          body: formData
        });
        
        if (response.ok) {
          const json = await response.json();
          const result = json.data || json;
          const type = json.chart_type || (id.includes('genes') ? 'table' : (id === 'diagnosis-age' || id === 'AGE' ? 'bar' : 'pie'));
          
          setChartType(type);
          if (Array.isArray(result) && result.length > 0) {
            setData(result);
          } else {
            setData(null);
          }
        } else {
          throw new Error(`Server returned ${response.status}`);
        }
      } catch (err) {
        console.warn(`ChartWidget(${id}): Fetch failed, using fallback data.`, err);
        setError(err instanceof Error ? err.message : 'Unknown error');
        
        // Fallback Mock Data
        if (id === 'CANCER_TYPE') {
          setChartType('table');
          setData([
            { value: 'Non-Small Cell Lung Cancer', count: 7809 },
            { value: 'Colorectal Cancer', count: 5543 },
            { value: 'Breast Cancer', count: 5368 },
            { value: 'Prostate Cancer', count: 3211 },
            { value: 'Pancreatic Cancer', count: 3109 },
          ]);
        } else if (id === 'GENDER' || id === 'SEX') {
          setChartType('pie');
          setData([
            { value: 'Male', count: 12000 },
            { value: 'Female', count: 13000 },
          ]);
        } else if (id === 'mutated-genes') {
          setChartType('table');
          setData([
            { gene: 'TP53', n_mut: 12450, n_samples: 12000, freq: 48.5 },
            { gene: 'TTN', n_mut: 9800, n_samples: 9500, freq: 38.2 },
            { gene: 'MUC16', n_mut: 7600, n_samples: 7200, freq: 29.1 },
            { gene: 'CSMD3', n_mut: 6500, n_samples: 6100, freq: 24.5 },
          ]);
        } else if (id === 'diagnosis-age' || id === 'AGE') {
          setChartType('bar');
          setData([
            { x: '30-40', y: 1500 },
            { x: '40-50', y: 3200 },
            { x: '50-60', y: 4800 },
            { x: '60-70', y: 4100 },
          ]);
        } else {
          setData(null);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [studyId, id, filters]);

  const onInteraction = (value: string) => {
    if (id === 'mutated-genes') {
      const currentGenes = filters.mutationFilter.genes;
      const newGenes = currentGenes.includes(value) 
        ? currentGenes.filter(g => g !== value)
        : [...currentGenes, value];
      updateMutationFilter(newGenes);
    } else {
      const currentFilter = filters.clinicalDataFilters.find(f => f.attributeId === id);
      const currentValues = currentFilter ? currentFilter.values.map(v => v.value) : [];
      
      const newValues = currentValues.includes(value)
        ? currentValues.filter(v => v !== value)
        : [...currentValues, value];
        
      updateClinicalFilter(id, newValues.map(v => ({ value: v })));
    }
  };

  const isPie = chartType === 'pie';
  const isTable = chartType === 'table';
  const isBar = chartType === 'bar';

  // Get selected values for highlighting
  const selectedValues = id === 'mutated-genes' 
    ? filters.mutationFilter.genes 
    : (filters.clinicalDataFilters.find(f => f.attributeId === id)?.values.map(v => v.value as string) || []);

  return (
    <div className="flex flex-col h-full w-full bg-white border border-[#d3d3d3] rounded-[3px] shadow-none overflow-hidden group">
      <div className="drag-handle relative flex items-center justify-center h-[20px] bg-[#f5f5f5] border-b border-[#d3d3d3] cursor-move flex-shrink-0">
        <span className="text-[11px] font-bold text-[#333] truncate px-4">
          {title}
        </span>
        
        <div className="absolute right-0 top-0 h-full flex items-center pr-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button className="p-0.5 text-[#999] hover:text-[#333] transition-colors">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <button className="p-0.5 text-[#999] hover:text-red-500 transition-colors ml-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div ref={target} className="flex-1 relative overflow-hidden bg-white">
        {loading && !data ? (
          <div className="flex items-center justify-center h-full w-full">
            <div className="animate-pulse text-[#999] text-[10px]">Loading...</div>
          </div>
        ) : (Array.isArray(data) && data.length > 0) ? (
          <>
            {isPie && size && <PieChart data={data} width={size.width} height={size.height} onSliceClick={onInteraction} selectedValues={selectedValues} />}
            {isTable && <TableChart data={data} totalCount={25000} onRowClick={onInteraction} selectedValues={selectedValues} />}
            {isBar && size && <BarChart data={data} width={size.width} height={size.height} />}
            {!isPie && !isTable && !isBar && (
               <div className="flex items-center justify-center h-full w-full text-[10px] text-[#999]">
                 Widget type not mapped: {id} ({chartType})
               </div>
            )}
          </>
        ) : (
          <div className="flex items-center justify-center h-full w-full">
            <div className="text-[#999] italic text-[11px]">
              {error ? `Error: ${error}` : `No data for ${id}`}
            </div>
          </div>
        )}
        
        <div className="absolute bottom-0.5 right-0.5 pointer-events-none opacity-40 z-20">
           <svg width="6" height="6" viewBox="0 0 6 6" fill="none" xmlns="http://www.w3.org/2000/svg">
             <path d="M6 6L0 6L6 0L6 6Z" fill="#666"/>
           </svg>
        </div>
      </div>
      
      {(isTable || id.includes('type') || id.includes('genes')) ? (
        <div className="p-1 border-t border-gray-100 bg-white flex-shrink-0">
           <div className="border border-[#ccc] rounded-[2px] px-1 py-0.5 flex items-center">
             <span className="text-[10px] text-[#999]">Search...</span>
           </div>
        </div>
      ) : null}
    </div>
  )
}

export default ChartWidget
