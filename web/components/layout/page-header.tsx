import * as React from "react";

interface PageHeaderProps {
    title: string;
    subtitle?: string;
    actions?: React.ReactNode;
    backHref?: string;
    backLabel?: string;
}

export function PageHeader({
    title,
    subtitle,
    actions,
    backHref,
    backLabel = "Kembali",
}: PageHeaderProps) {
    return (
        <div className="mb-6">
            {backHref && (
                <a
                    href={backHref}
                    className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-3 transition-colors"
                >
                    ← {backLabel}
                </a>
            )}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
                    {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
                </div>
                {actions && (
                    <div className="flex flex-wrap items-center gap-2">{actions}</div>
                )}
            </div>
        </div>
    );
}
