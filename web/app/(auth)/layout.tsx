"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/auth";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Redirect jika sudah login
    if (isAuthenticated()) {
      router.push("/dashboard");
    }
    setIsReady(true);
  }, [router]);

  if (!isReady) {
    return <div>Loading...</div>;
  }

  return <div className="min-h-screen bg-gray-50">{children}</div>;
}
