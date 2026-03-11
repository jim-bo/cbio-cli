import React from 'react';
import { VictoryChart, VictoryBar, VictoryAxis, VictoryTooltip, VictoryTheme } from 'victory';
import { CBIOPORTAL_COLORS } from '../../Colors';

interface BarChartData {
  x: string | number;
  y: number;
}

interface BarChartProps {
  data: BarChartData[];
  width: number;
  height: number;
  title?: string;
}

const BarChart: React.FC<BarChartProps> = ({ data, width, height }) => {
  const TILT_ANGLE = -45; // Negative for standard cBioPortal tilt
  const BAR_COLOR = '#2986E2'; // cBioPortal primary blue

  return (
    <div className="flex items-center justify-center h-full w-full">
      <VictoryChart
        width={width}
        height={height}
        padding={{ top: 20, bottom: 50, left: 50, right: 20 }}
        domainPadding={{ x: 20 }}
      >
        <VictoryAxis
          style={{
            tickLabels: { 
              fontSize: 10, 
              angle: TILT_ANGLE, 
              textAnchor: 'end',
              padding: 5
            },
            axis: { stroke: '#333' },
            ticks: { stroke: '#333', size: 5 }
          }}
        />
        <VictoryAxis
          dependentAxis
          style={{
            tickLabels: { fontSize: 10, padding: 5 },
            axis: { stroke: '#333' },
            grid: { stroke: '#f0f0f0' }
          }}
          tickFormat={(t) => Math.round(t).toLocaleString()}
        />
        <VictoryBar
          data={data}
          style={{
            data: { 
              fill: BAR_COLOR,
              width: 15,
              cursor: 'pointer'
            }
          }}
          labelComponent={
            <VictoryTooltip
              flyoutStyle={{ fill: 'white', stroke: '#d3d3d3' }}
              style={{ fontSize: 10 }}
            />
          }
          labels={({ datum }) => `${datum.x}: ${datum.y}`}
        />
      </VictoryChart>
    </div>
  );
};

export default BarChart;
