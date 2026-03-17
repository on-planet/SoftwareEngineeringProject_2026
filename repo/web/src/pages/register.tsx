import { useRouter } from "next/router";
import React, { useEffect } from "react";

export default function RegisterRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    void router.replace("/auth?mode=register");
  }, [router]);

  return null;
}
