import * as React from "react";

type Trend = "up" | "down" | "neutral";

interface StatCardProps {
    title: string;
    value: string | React.ReactNode;
    subtitle?: string;
    icon: string;
    trend?: Trend;
    trendValue?: string;
    className?: string;
}

export function StatCard({
    title,
    value,
    subtitle,
    icon,
    trend,
    trendValue,
    className = "",
}: StatCardProps) {
    const trendColor =
        trend === "up"
            ? "text-green-600 bg-green-50"
            : trend === "down"
                ? "text-red-500 bg-red-50"
                : "text-gray-500 bg-gray-100";

    const trendSign = trend === "up" ? "↑" : trend === "down" ? "↓" : "—";

    return (
        <div
            className={`bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col gap-3 hover:shadow-md transition-shadow ${className}`}
        >
            <div className="flex items-start justify-between">
                <p className="text-sm font-medium text-gray-500">{title}</p>
                <span className="text-2xl">{icon}</span>
            </div>

            <div className="text-2xl font-bold text-gray-900 leading-tight">{value}</div>

            <div className="flex items-center justify-between">
                {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
                {trend && trendValue && (
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${trendColor}`}>
                        {trendSign} {trendValue}
                    </span>
                )}
            </div>
        </div>
    );
}
