"use client";

import { useEffect } from "react";
import { Loader2, AlertCircle, Info } from "lucide-react";
import { useStore } from "@/lib/store";
import { FeatureSections } from "@/components/annotation-feature-sections";
import {
  CatalyticActivitySection,
  FunctionSection,
  GeneOntologySection,
  KeywordsSection,
  NamesSection,
} from "@/components/annotation-function-sections";

/**
 * Annotations tab: biological annotation from UniProtKB (P6).
 *
 * Every section is conditional on its own data. A protein with no resolvable
 * UniProt accession — a plain upload, usually — is a successful, empty
 * response, and gets an explanation rather than an error: nothing is broken,
 * there is simply nothing to show.
 */
export function AnnotationsPanel({ proteinId }: { proteinId: string }) {
  const annotations = useStore((s) => s.annotations);
  const loading = useStore((s) => s.annotationsLoading);
  const error = useStore((s) => s.annotationsError);
  const loadAnnotations = useStore((s) => s.loadAnnotations);

  useEffect(() => {
    if (!proteinId) return;
    void loadAnnotations(proteinId);
  }, [proteinId, loadAnnotations]);

  if (loading && !annotations) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-500">
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="ml-2 text-xs">Fetching annotations&hellip;</span>
      </div>
    );
  }

  if (error && !annotations) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-2 px-4 text-center"
      >
        <AlertCircle className="size-6 text-red-400" aria-hidden />
        <p className="text-xs text-red-400">Annotations failed: {error.message}</p>
      </div>
    );
  }

  if (!annotations) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center">
        <p className="text-xs text-zinc-500">Load a protein to see annotations.</p>
      </div>
    );
  }

  if (!annotations.accession_resolved) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
        <Info className="size-5 text-zinc-500" aria-hidden />
        <p className="text-xs text-zinc-400">No UniProt annotations for this structure.</p>
        <p className="text-[11px] leading-relaxed text-zinc-500">
          {annotations.resolution_note}
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <NamesSection a={annotations} />
      {annotations.function.length > 0 && (
        <FunctionSection paragraphs={annotations.function} />
      )}
      {annotations.catalytic_activity.length > 0 && (
        <CatalyticActivitySection activities={annotations.catalytic_activity} />
      )}
      {(annotations.gene_ontology.molecular_function.length > 0 ||
        annotations.gene_ontology.biological_process.length > 0 ||
        annotations.gene_ontology.cellular_component.length > 0) && (
        <GeneOntologySection go={annotations.gene_ontology} />
      )}
      {annotations.keywords.length > 0 && (
        <KeywordsSection keywords={annotations.keywords} />
      )}
      <FeatureSections a={annotations} />

      <p className="px-3 py-3 text-[10px] leading-relaxed text-zinc-600">
        {annotations.resolution_note} Annotation data from UniProtKB.
      </p>
    </div>
  );
}
