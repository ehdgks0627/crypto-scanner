import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { chartPalette, chartTheme } from "./chartTheme";

export function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="chart-card">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function DonutChartCard({ title, data }: { title: string; data: Array<{ name: string; value: number }> }) {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <ChartCard title={title}>
      <div className="donut-chart-body">
        <ResponsiveContainer width="100%" height={210}>
          <PieChart>
            <Pie data={data} innerRadius={55} outerRadius={80} dataKey="value" nameKey="name" paddingAngle={3} isAnimationActive={false}>
              {data.map((entry, index) => (
                <Cell key={entry.name} fill={chartPalette[index % chartPalette.length]} />
              ))}
            </Pie>
            <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className="chart-center-value">
              {total}
            </text>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <div className="chart-legend chart-legend--stack">
          {data.map((entry, index) => (
            <span key={entry.name}>
              <i style={{ background: chartPalette[index % chartPalette.length] }} />
              {entry.name} {entry.value}
            </span>
          ))}
        </div>
      </div>
    </ChartCard>
  );
}

export function BarChartCard({ title, data }: { title: string; data: Array<{ name: string; value: number }> }) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 12 }}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" />
          <YAxis dataKey="name" type="category" width={110} />
          <Tooltip />
          <Bar dataKey="value" fill={chartTheme.primary} radius={[0, chartTheme.radius, chartTheme.radius, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function TrendChartCard({ data }: { data: Array<{ name: string; critical: number; total: number }> }) {
  return (
    <ChartCard title="시간대별 트렌드">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="critical" stroke={chartTheme.critical} strokeWidth={2} isAnimationActive={false} />
          <Line type="monotone" dataKey="total" stroke={chartTheme.primary} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
