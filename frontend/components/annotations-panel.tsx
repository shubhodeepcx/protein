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
import { FunctionalRegionsPanel } from "@/components/functional-regions-panel";

/**
 * Annotations tab: biological annotation from UniProtKB (P6), and functional
 * regions and binding pockets (A5).
 *
 * Every section is conditional on its own data. A protein with no resolvable
 * UniProt accession — a plain upload, usually — is a successful, empty
 * response, and gets an explanation rather than an error: nothing is broken,
 * there is simply nothing to show.
 *
 * A5 changed one thing about that: an unresolved accession is no longer the
 * whole story, because the bound ligands and the surface profile are measured
 * from the coordinate file and exist whether or not UniProt knows this
 * protein. So the "no annotations" case is now a notice at the top of a panel
 * that still has content, rather than a full-height dead end.
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
      <div className="flex h-full flex-col overflow-y-auto">
        <div className="flex items-start gap-2 border-b border-zinc-800 px-3 py-3">
          <Info className="mt-0.5 size-4 shrink-0 text-zinc-500" aria-hidden />
          <div>
            <p className="text-xs text-zinc-400">
              No UniProt annotations for this structure.
            </p>
            <p className="text-[11px] leading-relaxed text-zinc-500">
              {annotations.resolution_note} What follows is measured from the
              coordinate file itself.
            </p>
          </div>
        </div>
        <FunctionalRegionsPanel proteinId={proteinId} />
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
      <FunctionalRegionsPanel proteinId={proteinId} />
      <FeatureSections a={annotations} />

      <p className="px-3 py-3 text-[10px] leading-relaxed text-zinc-600">
        {annotations.resolution_note} Annotation data from UniProtKB.
      </p>
    </div>
  );
}
