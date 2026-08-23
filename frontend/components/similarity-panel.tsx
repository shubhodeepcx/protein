"use client";

import { useEffect } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { useStore } from "@/lib/store";
import { AnnotationSection } from "@/components/annotation-section";
import { BlastRunner } from "@/components/blast-runner";
import { SimilarProteinsSection } from "@/components/similar-proteins-section";

/**
 * Similarity tab (P8): "what else looks like this protein?", answered twice.
 *
 * * **UniRef homologs** — precomputed by UniProt, so they are on screen
 *   immediately. No job, no wait.
 * * **BLAST** — computed on demand at EBI against a database you choose, with
 *   alignment statistics UniRef does not carry. Takes 30 s to several minutes.
 *
 * The homolog section loads on mount; BLAST only runs when asked, because it
 * costs EBI real compute and nobody should spend it by opening a tab.
 */
export function SimilarityPanel({ proteinId }: { proteinId: string }) {
  const current = useStore((s) => s.current);
  const loaded = useStore((s) => s.similar);
  const loading = useStore((s) => s.similarLoading);
  const error = useStore((s) => s.similarError);
  const loadSimilar = useStore((s) => s.loadSimilar);

  useEffect(() => {
    if (!proteinId) return;
    void loadSimilar(proteinId);
  }, [proteinId, loadSimilar]);

  // The payload carries the uid it was built for, so a leftover response from
  // the previously viewed protein can never render under this one. No extra
  // state needed — the server already tells us who the answer is about.
  const similar = loaded?.id === proteinId ? loaded : null;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <AnnotationSection
        title="Homologs (UniRef)"
        count={similar?.members.length}
      >
        {loading && !similar && (
          <p className="flex items-center gap-2 text-[11px] text-zinc-500">
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Looking up the UniRef cluster&hellip;
          </p>
        )}
        {error && !similar && (
          <p
            role="alert"
            className="flex items-start gap-1.5 text-[11px] text-red-400"
          >
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Homologs failed: {error.message}
          </p>
        )}
        {similar && <SimilarProteinsSection data={similar} />}
      </AnnotationSection>

      <AnnotationSection title="BLAST search">
        <BlastRunner proteinId={proteinId} chains={current?.chains ?? []} />
      </AnnotationSection>

      <p className="px-3 py-3 text-[10px] leading-relaxed text-zinc-600">
        Homologs from UniProt&rsquo;s UniRef clusters. BLAST searches run on
        EBI&rsquo;s NCBI BLAST service, which uses the same NCBI algorithms.
      </p>
    </div>
  );
}
