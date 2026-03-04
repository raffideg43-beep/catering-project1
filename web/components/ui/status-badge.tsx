import * as React from "react";

interface StatusBadgeProps {
    status: string;
    className?: string;
}

const STATUS_MAP: Record<string, { label: string; className: string }> = {
    // Hijau
    confirmed: { label: "Dikonfirmasi", className: "bg-green-100 text-green-700 ring-green-200" },
    paid: { label: "Lunas", className: "bg-green-100 text-green-700 ring-green-200" },
    ready: { label: "Siap", className: "bg-green-100 text-green-700 ring-green-200" },
    active: { label: "Aktif", className: "bg-green-100 text-green-700 ring-green-200" },
    dipotong: { label: "Dipotong", className: "bg-green-100 text-green-700 ring-green-200" },

    // Kuning
    processing: { label: "Diproses", className: "bg-yellow-100 text-yellow-700 ring-yellow-200" },
    pending: { label: "Menunggu", className: "bg-yellow-100 text-yellow-700 ring-yellow-200" },
    pending_regenerate: { label: "Diperbarui", className: "bg-yellow-100 text-yellow-700 ring-yellow-200" },
    generating: { label: "Diproses", className: "bg-yellow-100 text-yellow-700 ring-yellow-200" },
    unpaid: { label: "Belum Lunas", className: "bg-yellow-100 text-yellow-700 ring-yellow-200" },

    // Merah
    failed: { label: "Gagal", className: "bg-red-100 text-red-600 ring-red-200" },
    overdue: { label: "Terlambat", className: "bg-red-100 text-red-600 ring-red-200" },
    error: { label: "Error", className: "bg-red-100 text-red-600 ring-red-200" },
    cancelled: { label: "Dibatalkan", className: "bg-red-100 text-red-600 ring-red-200" },
    tidak_ada_menu: { label: "Tdk Ada Menu", className: "bg-red-100 text-red-600 ring-red-200" },

    // Abu
    draft: { label: "Draft", className: "bg-gray-100 text-gray-600 ring-gray-200" },
    not_generated: { label: "Belum Dibuat", className: "bg-gray-100 text-gray-600 ring-gray-200" },
    manual: { label: "Manual", className: "bg-gray-100 text-gray-600 ring-gray-200" },
};

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
    const key = (status || "").toLowerCase();
    const mapped = STATUS_MAP[key] ?? {
        label: status,
        className: "bg-gray-100 text-gray-600 ring-gray-200",
    };

    return (
        <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ring-1 ring-inset ${mapped.className} ${className}`}
        >
            {mapped.label}
        </span>
    );
}
