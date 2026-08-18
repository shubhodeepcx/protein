"use client";

import React, { useEffect, useRef, useImperativeHandle } from "react";
import { createPluginUI } from "molstar/lib/mol-plugin-ui";
import { renderReact18 } from "molstar/lib/mol-plugin-ui/react18";
import { DefaultPluginUISpec } from "molstar/lib/mol-plugin-ui/spec";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { PluginCommands } from "molstar/lib/mol-plugin/commands";
import type { Structure } from "molstar/lib/mol-model/structure";
import {
  applyColoring,
  applyRepresentation,
  applySelection,
  loadStructureInto,
  type MolstarFormat,
} from "@/lib/molstar/actions";
import {
  buildResidueIndex,
  findIndexDrift,
  lociToResidueKey,
  EMPTY_RESIDUE_INDEX,
  type ResidueIndexMap,
} from "@/lib/molstar/residue-index";
import type {
  MolstarColoring,
  MolstarRepresentation,
} from "@/lib/molstar/theming";
import type { QueryChain } from "@/lib/residue";

export type { MolstarFormat, MolstarRepresentation, MolstarColoring };

export interface MolstarViewerRef {
  loadStructure(url: string, format?: MolstarFormat): Promise<void>;
  /** Keys are `"<chain>:<1-based position>"`, matching the sequence panel. */
  highlightResidues(keys: string[]): void;
  setRepresentation(type: MolstarRepresentation): void;
  setColoring(scheme: MolstarColoring): void;
  resetCamera(): void;
}

export interface MolstarViewerProps {
  className?: string;
  style?: React.CSSProperties;
  onReady?: () => void;
  /** Fires with a residue key on click, or `null` when empty space is clicked. */
  onResidueClick?: (key: string | null) => void;
  /** Optional: used only to warn when Mol*'s residue count drifts from the API's. */
  chains?: readonly QueryChain[];
}

const MolstarViewer = React.forwardRef<MolstarViewerRef, MolstarViewerProps>(
  function MolstarViewer(
    { className, style, onReady, onResidueClick, chains },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const pluginRef = useRef<PluginUIContext | null>(null);
    const structureRef = useRef<Structure | null>(null);
    const indexRef = useRef<ResidueIndexMap>(EMPTY_RESIDUE_INDEX);
    const onReadyRef = useRef(onReady);
    const onResidueClickRef = useRef(onResidueClick);
    const chainsRef = useRef(chains);

    // Keep refs in sync without re-running the init effect (which would tear
    // down and rebuild the WebGL context on every parent render).
    useEffect(() => {
      onReadyRef.current = onReady;
      onResidueClickRef.current = onResidueClick;
      chainsRef.current = chains;
    }, [onReady, onResidueClick, chains]);

    useEffect(() => {
      const target = containerRef.current;
      if (!target) return;

      let disposed = false;
      let pluginInstance: PluginUIContext | null = null;
      let clickSub: { unsubscribe(): void } | null = null;

      async function init() {
        const spec = DefaultPluginUISpec();
        const plugin = await createPluginUI({
          target: target!,
          render: renderReact18,
          spec: {
            ...spec,
            layout: {
              initial: {
                isExpanded: false,
                showControls: false,
                regionState: {
                  bottom: "hidden",
                  left: "hidden",
                  right: "hidden",
                  top: "hidden",
                },
              },
            },
          },
        });
        if (disposed) {
          plugin.dispose();
          return;
        }
        pluginInstance = plugin;
        pluginRef.current = plugin;

        // Direction 1 of the selection sync: 3D click -> store. `click` is a
        // BehaviorSubject that replays an empty seed value on subscribe;
        // swallowing it stops a spurious "clear selection" on mount.
        let seeded = false;
        clickSub = plugin.behaviors.interaction.click.subscribe((e) => {
          if (!seeded) {
            seeded = true;
            return;
          }
          onResidueClickRef.current?.(
            lociToResidueKey(e.current.loci, indexRef.current),
          );
        });

        onReadyRef.current?.();
      }

      // eslint-disable-next-line no-console
      init().catch((err) => console.error("Mol* init failed:", err));

      return () => {
        disposed = true;
        clickSub?.unsubscribe();
        pluginInstance?.dispose();
        pluginRef.current = null;
        structureRef.current = null;
        indexRef.current = EMPTY_RESIDUE_INDEX;
      };
    }, []);

    useImperativeHandle(ref, () => ({
      async loadStructure(url: string, format: MolstarFormat = "pdb") {
        const plugin = pluginRef.current;
        if (!plugin) return;

        structureRef.current = null;
        indexRef.current = EMPTY_RESIDUE_INDEX;

        const structure = await loadStructureInto(plugin, url, format);
        structureRef.current = structure;
        indexRef.current = structure
          ? buildResidueIndex(structure)
          : EMPTY_RESIDUE_INDEX;

        const expected = chainsRef.current;
        const drift = expected ? findIndexDrift(indexRef.current, expected) : [];
        if (drift.length > 0) {
          // eslint-disable-next-line no-console
          console.warn(
            "Residue numbering drift between Mol* and the API:",
            drift.join("; "),
          );
        }
      },

      highlightResidues(keys: string[]) {
        const plugin = pluginRef.current;
        const structure = structureRef.current;
        if (!plugin || !structure) return;
        applySelection(plugin, structure, keys, indexRef.current);
      },

      setRepresentation(type: MolstarRepresentation) {
        const plugin = pluginRef.current;
        if (!plugin) return;
        applyRepresentation(plugin, type);
      },

      setColoring(scheme: MolstarColoring) {
        const plugin = pluginRef.current;
        if (!plugin) return;
        applyColoring(plugin, scheme);
      },

      resetCamera() {
        const plugin = pluginRef.current;
        if (!plugin) return;
        PluginCommands.Camera.Reset(plugin, {});
      },
    }));

    return (
      <div
        ref={containerRef}
        className={className}
        style={{ position: "relative", width: "100%", height: "100%", ...style }}
      />
    );
  },
);

export default MolstarViewer;
