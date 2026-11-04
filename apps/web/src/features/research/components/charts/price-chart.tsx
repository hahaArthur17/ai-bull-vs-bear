import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useId } from "react";
import type { PricePoint } from "@/lib/contracts/research";
import { money, marketDate } from "@/lib/format/market";

export default function PriceChart({
  points,
  compact = false,
}: {
  points: PricePoint[];
  compact?: boolean;
}) {
  const gradient = useId().replace(/:/g, "");
  return (
    <div
      className={compact ? "h-36 w-full" : "h-64 w-full sm:h-72"}
      role="img"
      aria-label={`Synthetic closing prices, ${marketDate(points[0].date)} to ${marketDate(points.at(-1)!.date)}. ${compact ? "Open research for a data table." : "A data table is available below."}`}
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <AreaChart data={points} margin={{ left: 0, right: 8, top: 12, bottom: 0 }}>
          <defs>
            <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.12} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 5" />
          <XAxis
            dataKey="date"
            tickFormatter={(date: string) =>
              new Date(date).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                timeZone: "UTC",
              })
            }
            tickLine={false}
            axisLine={false}
            minTickGap={compact ? 65 : 40}
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            dy={8}
            hide={compact}
          />
          <YAxis
            hide={compact}
            tickLine={false}
            axisLine={false}
            domain={["auto", "auto"]}
            tickFormatter={(value: number) => `$${value.toFixed(0)}`}
            tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
            width={48}
          />
          <Tooltip
            formatter={(value) => [money(Number(value)), "Close"]}
            labelFormatter={(date) => marketDate(String(date))}
            contentStyle={{
              borderRadius: 10,
              border: "1px solid var(--border)",
              background: "var(--card)",
              fontSize: 12,
            }}
            cursor={{ stroke: "var(--primary)", strokeDasharray: "3 3" }}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke="var(--primary)"
            strokeWidth={2}
            fill={`url(#${gradient})`}
            isAnimationActive={false}
            activeDot={{ r: 4, fill: "var(--primary)", stroke: "var(--card)", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
