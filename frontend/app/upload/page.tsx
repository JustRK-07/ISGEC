"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useModals } from "@/lib/store";

export default function UploadPage() {
  const openUpload = useModals((s) => s.openUpload);
  const router = useRouter();

  useEffect(() => {
    openUpload();
  }, [openUpload]);

  return (
    <div style={{ padding: 40 }}>
      <p>Opening upload dialog…</p>
      <button type="button" onClick={() => router.push("/")}>← Back to landing</button>
    </div>
  );
}
