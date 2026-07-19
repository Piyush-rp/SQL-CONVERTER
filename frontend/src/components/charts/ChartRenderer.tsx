import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { ChartSpec, ExecutionResult } from "@/types/api";

const SERIES_COLORS = ["#d3910f", "#57697d", "#e8a934", "#3c4a5b", "#f2c463", "#7c8fa3"];

function toRecords(execution: ExecutionResult): Record<string, unknown>[] {
  return execution.rows.map((row) =>
    Object.fromEntries(execution.columns.map((col, i) => [col, row[i]]))
  );
}

export function ChartRenderer({ chartSpec, execution }: { chartSpec: ChartSpec; execution: ExecutionResult }) {
  if (chartSpec.chart_type === "none" || execution.rows.length === 0) {
    return null;
  }

  const data = toRecords(execution);

  if (chartSpec.chart_type === "table") {
    return null; // the results table is rendered separately - nothing to chart
  }

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/60 p-4">
      {chartSpec.title && <p className="mb-3 text-xs font-medium text-ink-400">{chartSpec.title}</p>}
      <ResponsiveContainer width="100%" height={260}>
        {chartSpec.chart_type === "bar" ? (
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
            <XAxis dataKey={chartSpec.x_key ?? undefined} tick={{ fill: "#7c8fa3", fontSize: 11 }} />
            <YAxis tick={{ fill: "#7c8fa3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#161c25", border: "1px solid #2a3441", borderRadius: 6, fontSize: 12 }} />
            {chartSpec.y_keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
            {chartSpec.y_keys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={SERIES_COLORS[i % SERIES_COLORS.length]} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        ) : chartSpec.chart_type === "line" ? (
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3441" />
            <XAxis dataKey={chartSpec.x_key ?? undefined} tick={{ fill: "#7c8fa3", fontSize: 11 }} />
            <YAxis tick={{ fill: "#7c8fa3", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#161c25", border: "1px solid #2a3441", borderRadius: 6, fontSize: 12 }} />
            {chartSpec.y_keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
            {chartSpec.y_keys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth={2} dot={false} />
            ))}
          </LineChart>
        ) : (
          <PieChart>
            <Pie
              data={data}
              dataKey={chartSpec.y_keys[0]}
              nameKey={chartSpec.x_key ?? undefined}
              innerRadius={55}
              outerRadius={90}
              paddingAngle={2}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ background: "#161c25", border: "1px solid #2a3441", borderRadius: 6, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
          </PieChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
