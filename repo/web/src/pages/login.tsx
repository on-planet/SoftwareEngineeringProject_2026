import { useRouter } from "next/router";
import React, { useEffect } from "react";

export default function LoginRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    void router.replace("/auth?mode=login");
  }, [router]);

  return null;
}
