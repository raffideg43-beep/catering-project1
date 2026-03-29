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
            className={`bg-white rounded-2xl shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] border border-gray-100/80 p-5 flex flex-col gap-3 hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:-translate-y-0.5 transition-all duration-300 ${className}`}
        >
            <div className="flex items-start justify-between">
                <p className="text-sm font-semibold text-gray-500 tracking-tight">{title}</p>
                <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-xl shadow-inner border border-gray-100/50">
                    {icon}
                </div>
            </div>

            <div className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900 leading-tight mt-1">{value}</div>

            <div className="flex items-center justify-between mt-1">
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
