import React from 'react'

interface ChartWidgetProps {
  id: string
  title: string
}

const ChartWidget: React.FC<ChartWidgetProps> = ({ id, title }) => {
  return (
    <div className="flex flex-col h-full w-full bg-white border border-[#d3d3d3] rounded-[3px] shadow-none overflow-hidden group">
      {/* Header matching cBioPortal .name style */}
      <div className="drag-handle relative flex items-center justify-center h-[20px] bg-[#f5f5f5] border-b border-[#d3d3d3] cursor-move">
        <span className="text-[11px] font-bold text-[#333] truncate px-4">
          {title}
        </span>
        
        {/* Controls - absolute positioned to the right like cBioPortal */}
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

      {/* Content Area */}
      <div className="flex-1 relative flex items-center justify-center overflow-hidden">
        <div className="text-[#999] italic text-[11px]">
          {id}
        </div>
        
        {/* Resize handle visual hint (cBioPortal has a small handle icon at bottom right) */}
        <div className="absolute bottom-0.5 right-0.5 pointer-events-none opacity-40">
           <svg width="6" height="6" viewBox="0 0 6 6" fill="none" xmlns="http://www.w3.org/2000/svg">
             <path d="M6 6L0 6L6 0L6 6Z" fill="#666"/>
           </svg>
        </div>
      </div>
      
      {/* Footer search area placeholder */}
      {id.includes('type') || id.includes('genes') ? (
        <div className="p-1 border-t border-gray-100 bg-white">
           <div className="border border-[#ccc] rounded-[2px] px-1 py-0.5 flex items-center">
             <span className="text-[10px] text-[#999]">Search...</span>
           </div>
        </div>
      ) : null}
    </div>
  )
}

export default ChartWidget
