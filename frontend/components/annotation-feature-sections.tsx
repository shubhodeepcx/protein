"use client";

import type {
  CrossReference,
  DiseaseAssociation,
  ProteinAnnotations,
  SequenceFeature,
  SubcellularLocation,
} from "@/lib/types";
import { formatRange, omimUrl } from "@/lib/annotation-links";
import { AnnotationSection, Outbound } from "@/components/annotation-section";

function FeatureList({ features }: { features: SequenceFeature[] }) {
  return (
    <ul className="space-y-1">
      {features.map((feature, i) => (
        <li key={i} className="flex items-baseline gap-2 text-[11px] leading-relaxed">
          <span className="w-20 shrink-0 font-mono tabular-nums text-zinc-500">
            {formatRange(feature.start, feature.end)}
          </span>
          <span className="text-zinc-300">
            {feature.type}
            {feature.description && (
              <span className="text-zinc-500"> · {feature.description}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Subcellular Location — where the protein is found, plus UniProt's note. */
export function SubcellularLocationSection({
  locations,
  notes,
}: {
  locations: SubcellularLocation[];
  notes: string[];
}) {
  return (
    <AnnotationSection title="Subcellular Location" count={locations.length}>
      <ul className="space-y-1">
        {locations.map((location, i) => (
          <li key={i} className="text-[11px] leading-relaxed text-zinc-300">
            {location.location}
            {location.topology && (
              <span className="text-zinc-500"> · {location.topology}</span>
            )}
          </li>
        ))}
      </ul>
      {notes.map((note, i) => (
        <p key={i} className="mt-2 text-[11px] leading-relaxed text-zinc-500">
          {note}
        </p>
      ))}
    </AnnotationSection>
  );
}

/** Transmembrane — membrane spans and the topological domains between them. */
export function TransmembraneSection({ features }: { features: SequenceFeature[] }) {
  return (
    <AnnotationSection title="Transmembrane" count={features.length}>
      <FeatureList features={features} />
    </AnnotationSection>
  );
}

/** Involvement in disease. */
export function DiseaseSection({ diseases }: { diseases: DiseaseAssociation[] }) {
  return (
    <AnnotationSection title="Disease" count={diseases.length}>
      <ul className="space-y-2">
        {diseases.map((disease, i) => (
          <li
            key={i}
            className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-medium text-zinc-200">
                {disease.name}
              </span>
              {disease.acronym && (
                <span className="shrink-0 text-[10px] uppercase tracking-wide text-zinc-500">
                  {disease.acronym}
                </span>
              )}
            </div>
            {disease.description && (
              <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
                {disease.description}
              </p>
            )}
            {disease.mim_id && (
              <p className="mt-1 text-[11px]">
                <Outbound href={omimUrl(disease.mim_id)}>
                  OMIM {disease.mim_id}
                </Outbound>
              </p>
            )}
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}

/** PTM / Processing — the free-text comment and the positional features. */
export function PtmSection({
  notes,
  features,
}: {
  notes: string[];
  features: SequenceFeature[];
}) {
  return (
    <AnnotationSection title="PTM / Processing" count={features.length || undefined}>
      {notes.map((note, i) => (
        <p key={i} className="mb-2 text-[11px] leading-relaxed text-zinc-400">
          {note}
        </p>
      ))}
      {features.length > 0 && <FeatureList features={features} />}
    </AnnotationSection>
  );
}

/** Cross-references — Reactome / BioCyc / SIGNOR / NDEx / proteomes. */
export function CrossReferencesSection({ refs }: { refs: CrossReference[] }) {
  const groups = new Map<string, CrossReference[]>();
  for (const ref of refs) {
    groups.set(ref.database, [...(groups.get(ref.database) ?? []), ref]);
  }

  return (
    <AnnotationSection title="Cross-references" count={refs.length}>
      {[...groups].map(([database, entries]) => (
        <div key={database} className="mt-2 first:mt-0">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            {database}
          </div>
          <ul className="space-y-1">
            {entries.map((ref) => (
              <li key={ref.id} className="text-[11px] leading-relaxed">
                <Outbound href={ref.url}>{ref.id}</Outbound>
                {ref.description && (
                  <span className="ml-1 text-zinc-400">{ref.description}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </AnnotationSection>
  );
}

/** Every section that reads from the feature/comment half of the payload. */
export function FeatureSections({ a }: { a: ProteinAnnotations }) {
  return (
    <>
      {a.subcellular_locations.length > 0 && (
        <SubcellularLocationSection
          locations={a.subcellular_locations}
          notes={a.subcellular_location_notes}
        />
      )}
      {a.transmembrane.length > 0 && (
        <TransmembraneSection features={a.transmembrane} />
      )}
      {a.diseases.length > 0 && <DiseaseSection diseases={a.diseases} />}
      {(a.ptm.length > 0 || a.ptm_features.length > 0) && (
        <PtmSection notes={a.ptm} features={a.ptm_features} />
      )}
      {a.cross_references.length > 0 && (
        <CrossReferencesSection refs={a.cross_references} />
      )}
    </>
  );
}
