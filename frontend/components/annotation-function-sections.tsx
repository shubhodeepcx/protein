"use client";

import type {
  CatalyticActivity,
  GeneOntology,
  GoTerm,
  KeywordEntry,
  ProteinAnnotations,
} from "@/lib/types";
import {
  chebiUrl,
  ecUrl,
  goUrl,
  rheaUrl,
  taxonomyUrl,
  uniprotUrl,
} from "@/lib/annotation-links";
import { AnnotationSection, Chip, Field, Outbound } from "@/components/annotation-section";

/** Names & Origin — protein/gene names, organism, lineage, source entry. */
export function NamesSection({ a }: { a: ProteinAnnotations }) {
  return (
    <AnnotationSection title="Names & Origin">
      <div className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2">
        {a.protein_name && <Field label="Protein" value={a.protein_name} />}
        {a.gene_names.length > 0 && (
          <Field label="Gene" value={a.gene_names.join(", ")} />
        )}
        {a.organism && (
          <Field
            label="Organism"
            value={
              a.taxon_id !== null ? (
                <Outbound href={taxonomyUrl(a.taxon_id)}>
                  <em className="not-italic">{a.organism}</em>
                </Outbound>
              ) : (
                a.organism
              )
            }
          />
        )}
        {a.accession && (
          <Field
            label="UniProt"
            value={
              <Outbound href={uniprotUrl(a.accession)}>
                {a.entry_name ?? a.accession}
              </Outbound>
            }
          />
        )}
      </div>
      {a.lineage.length > 0 && (
        <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
          {a.lineage.join(" › ")}
        </p>
      )}
    </AnnotationSection>
  );
}

/** Function — the free-text FUNCTION comment, in full. */
export function FunctionSection({ paragraphs }: { paragraphs: string[] }) {
  return (
    <AnnotationSection title="Function">
      <div className="space-y-2">
        {paragraphs.map((text, i) => (
          <p key={i} className="text-xs leading-relaxed text-zinc-300">
            {text}
          </p>
        ))}
      </div>
    </AnnotationSection>
  );
}

/** Catalytic Activity — reaction text plus its Rhea / EC / ChEBI identifiers. */
export function CatalyticActivitySection({
  activities,
}: {
  activities: CatalyticActivity[];
}) {
  return (
    <AnnotationSection title="Catalytic Activity" count={activities.length}>
      <ul className="space-y-3">
        {activities.map((activity, i) => (
          <li
            key={i}
            className="rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2"
          >
            {activity.reaction && (
              <p className="font-mono text-[11px] leading-relaxed text-zinc-200">
                {activity.reaction}
              </p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
              {activity.ec_number && (
                <Outbound href={ecUrl(activity.ec_number)}>
                  EC {activity.ec_number}
                </Outbound>
              )}
              {activity.rhea_ids.map((id) => (
                <Outbound key={id} href={rheaUrl(id)}>
                  {id}
                </Outbound>
              ))}
              {activity.chebi_ids.map((id) => (
                <Outbound key={id} href={chebiUrl(id)}>
                  {id}
                </Outbound>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </AnnotationSection>
  );
}

function GoAspect({ label, terms }: { label: string; terms: GoTerm[] }) {
  if (terms.length === 0) return null;
  return (
    <div className="mt-2 first:mt-0">
      <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <ul className="space-y-1">
        {terms.map((term) => (
          <li key={term.id} className="text-[11px] leading-relaxed text-zinc-300">
            <Outbound href={goUrl(term.id)}>{term.id}</Outbound>{" "}
            <span>{term.term}</span>
            {term.evidence && (
              <span className="ml-1 text-zinc-500">({term.evidence})</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Gene Ontology, grouped by the ontology's three aspects. */
export function GeneOntologySection({ go }: { go: GeneOntology }) {
  const count =
    go.molecular_function.length +
    go.biological_process.length +
    go.cellular_component.length;

  return (
    <AnnotationSection title="Gene Ontology" count={count}>
      <GoAspect label="Molecular function" terms={go.molecular_function} />
      <GoAspect label="Biological process" terms={go.biological_process} />
      <GoAspect label="Cellular component" terms={go.cellular_component} />
    </AnnotationSection>
  );
}

/** Keywords, grouped by the category UniProt files each one under. */
export function KeywordsSection({ keywords }: { keywords: KeywordEntry[] }) {
  const groups = new Map<string, KeywordEntry[]>();
  for (const keyword of keywords) {
    const category = keyword.category ?? "Other";
    groups.set(category, [...(groups.get(category) ?? []), keyword]);
  }

  return (
    <AnnotationSection title="Keywords" count={keywords.length}>
      {[...groups].map(([category, entries]) => (
        <div key={category} className="mt-2 first:mt-0">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-zinc-500">
            {category}
          </div>
          <div className="flex flex-wrap gap-1">
            {entries.map((keyword) => (
              <Chip key={keyword.id ?? keyword.name}>{keyword.name}</Chip>
            ))}
          </div>
        </div>
      ))}
    </AnnotationSection>
  );
}
