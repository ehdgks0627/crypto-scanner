import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

const palette = ["#b42318", "#b54708", "#175cd3", "#067647", "#6941c6", "#0e9384"];

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
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={210}>
        <PieChart>
          <Pie data={data} innerRadius={55} outerRadius={80} dataKey="value" nameKey="name" paddingAngle={3}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={palette[index % palette.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div className="chart-legend">
        {data.map((entry, index) => (
          <span key={entry.name}>
            <i style={{ background: palette[index % palette.length] }} />
            {entry.name} {entry.value}
          </span>
        ))}
      </div>
    </ChartCard>
  );
}

export function BarChartCard({ title, data }: { title: string; data: Array<{ name: string; value: number }> }) {
  return (
    <ChartCard title={title}>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 12 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" />
          <YAxis dataKey="name" type="category" width={110} />
          <Tooltip />
          <Bar dataKey="value" fill="#175cd3" radius={[0, 4, 4, 0]} />
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
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="critical" stroke="#b42318" strokeWidth={2} />
          <Line type="monotone" dataKey="total" stroke="#175cd3" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
