import React from 'react';
import { getColorForString } from '../../Colors';

interface TableChartData {
  value?: string;
  gene?: string;
  count?: number;
  n_samples?: number;
  freq?: string | number;
  color?: string;
}

interface TableChartProps {
  data: TableChartData[];
  totalCount: number;
  onRowClick?: (value: string) => void;
  selectedValues?: string[];
}

const TableChart: React.FC<TableChartProps> = ({ data, totalCount, onRowClick, selectedValues = [] }) => {
  if (!Array.isArray(data)) return null;

  return (
    <div className="w-full h-full overflow-auto bg-white">
      <table className="w-full text-[11px] border-collapse">
        <thead className="sticky top-0 bg-white border-b border-gray-200 z-10">
          <tr className="text-[#333] font-bold">
            <th className="px-2 py-1 text-left font-bold"></th>
            <th className="px-2 py-1 text-right font-bold w-16">#</th>
            <th className="px-2 py-1 text-right font-bold w-16">
              <div className="flex items-center justify-end">
                Freq <span className="ml-1 text-[8px]">▼</span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {data.map((item, idx) => {
            const label = item.gene || item.value || `Unknown ${idx}`;
            const count = item.n_samples ?? item.count ?? 0;
            const freqVal = typeof item.freq === 'number' ? item.freq.toFixed(1) + '%' : (item.freq || ((count / totalCount) * 100).toFixed(1) + '%');
            const barWidth = (count / (totalCount || 1)) * 100;
            const color = item.color || getColorForString(label);
            const isSelected = selectedValues.includes(label);
            
            return (
              <tr 
                key={`${label}-${idx}`} 
                className={`hover:bg-gray-50 group cursor-pointer ${isSelected ? 'bg-blue-50/30' : ''}`}
                onClick={() => onRowClick && onRowClick(label)}
              >
                <td className="px-2 py-1.5 flex items-center space-x-2 min-w-0">
                  <div 
                    className="w-3 h-3 flex-shrink-0" 
                    style={{ backgroundColor: color }}
                  />
                  <span className={`truncate ${isSelected ? 'font-bold text-blue-700' : 'text-[#333]'}`} title={label}>
                    {label}
                  </span>
                </td>
                <td className="px-2 py-1.5 text-right text-[#333] tabular-nums">
                  <div className="flex items-center justify-end space-x-2">
                    <input 
                      type="checkbox" 
                      className="w-3 h-3 rounded-sm border-gray-300 text-blue-600 focus:ring-blue-500" 
                      checked={isSelected}
                      readOnly 
                    />
                    <span className={isSelected ? 'font-bold' : ''}>{count.toLocaleString()}</span>
                  </div>
                </td>
                <td className="px-2 py-1.5 text-right text-[#333] relative">
                  <div 
                    className="absolute inset-y-1 right-0 bg-blue-50 opacity-20 pointer-events-none" 
                    style={{ width: `${Math.min(100, barWidth)}%` }}
                  />
                  <span className="relative z-10">{freqVal}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default TableChart;
