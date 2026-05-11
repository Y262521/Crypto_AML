import DatePicker from 'react-datepicker'
import { Calendar, Filter, X } from 'lucide-react'

type Props = {
  startDate: Date | null
  endDate: Date | null
  onChangeStart: (d: Date | null) => void
  onChangeEnd: (d: Date | null) => void
  onApply: () => void
  onClear: () => void
  disabled?: boolean
}

export function DateRangeFilter({
  startDate,
  endDate,
  onChangeStart,
  onChangeEnd,
  onApply,
  onClear,
  disabled,
}: Props) {
  return (
    <div className="glass glass-hover w-full p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
        <div className="grid flex-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-400">Start date</label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <DatePicker
                selected={startDate}
                onChange={onChangeStart}
                selectsStart
                startDate={startDate}
                endDate={endDate}
                className="input pl-10"
                placeholderText="Select start"
                disabled={disabled}
              />
            </div>
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-gray-400">End date</label>
            <div className="relative">
              <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
              <DatePicker
                selected={endDate}
                onChange={onChangeEnd}
                selectsEnd
                startDate={startDate}
                endDate={endDate}
                minDate={startDate ?? undefined}
                className="input pl-10"
                placeholderText="Select end"
                disabled={disabled}
              />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-primary" onClick={onApply} disabled={disabled}>
            <Filter className="h-4 w-4" />
            Apply filter
          </button>
          <button type="button" className="btn-ghost" onClick={onClear} disabled={disabled}>
            <X className="h-4 w-4" />
            Clear
          </button>
        </div>
      </div>
    </div>
  )
}

