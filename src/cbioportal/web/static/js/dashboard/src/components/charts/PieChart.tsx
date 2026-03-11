import React, { useMemo } from 'react';
import { VictoryPie, VictoryLabel } from 'victory';
import numeral from 'numeral';
import { getColorForString } from '../../Colors';

interface PieChartData {
  value: string;
  count: number;
  color?: string;
}

interface PieChartProps {
  data: PieChartData[];
  width: number;
  height: number;
  onSliceClick?: (value: string) => void;
  selectedValues?: string[];
}

export function formatPieChartNumber(n: number) {
  return numeral(n)
    .format('0.[0]a')
    .replace(/([km])$/, (m) => m.toUpperCase());
}

const PieChart: React.FC<PieChartProps> = ({ data, width, height, onSliceClick, selectedValues = [] }) => {
  const totalCount = useMemo(() => data.reduce((acc, d) => acc + d.count, 0), [data]);
  const padding = 20;
  const radius = Math.min(width, height) / 2 - padding;
  
  const label = (d: { datum: PieChartData }) => {
    const ratio = d.datum.count / totalCount;
    return ratio > 0.25 ? formatPieChartNumber(d.datum.count) : '';
  };

  return (
    <div className="flex items-center justify-center h-full w-full">
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
        <VictoryPie
          standalone={false}
          width={width}
          height={height}
          padding={padding}
          data={data}
          x="value"
          y="count"
          colorScale={data.map((d) => d.color || getColorForString(d.value))}
          radius={radius}
          innerRadius={0} 
          labelRadius={radius / 3}
          labels={label}
          labelComponent={
            <VictoryLabel 
              style={{ fill: 'white', fontSize: 13, fontWeight: 'bold' }} 
              textAnchor="middle" 
              verticalAnchor="middle" 
            />
          }
          style={{
            data: {
              stroke: ({ datum }) => selectedValues.includes(datum.value) ? '#000' : 'white',
              strokeWidth: ({ datum }) => selectedValues.includes(datum.value) ? 2 : 0.5,
              opacity: ({ datum }) => (selectedValues.length === 0 || selectedValues.includes(datum.value)) ? 1 : 0.4,
              cursor: 'pointer',
            },
          }}
          labelPosition="centroid"
          events={[{
            target: "data",
            eventHandlers: {
              onClick: () => {
                return [
                  {
                    target: "data",
                    mutation: (props) => {
                      if (onSliceClick) {
                        onSliceClick(props.datum.value);
                      }
                      return null;
                    }
                  }
                ];
              }
            }
          }]}
        />
      </svg>
    </div>
  );
};

export default PieChart;
