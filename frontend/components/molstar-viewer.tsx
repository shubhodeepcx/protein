"use client";

import React, { useEffect, useRef, useImperativeHandle } from "react";
import { createPluginUI } from "molstar/lib/mol-plugin-ui";
import { renderReact18 } from "molstar/lib/mol-plugin-ui/react18";
import { DefaultPluginUISpec } from "molstar/lib/mol-plugin-ui/spec";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";
import { PluginCommands } from "molstar/lib/mol-plugin/commands";

export type MolstarFormat = "pdb" | "mmcif";

export type MolstarRepresentation =
  | "cartoon"
  | "surface"
  | "stick"
  | "ball-stick"
  | "spacefill";

export type MolstarColoring =
  | "chain"
  | "ss"
  | "hydrophobicity"
  | "plddt"
  | "residueType";

export interface MolstarViewerRef {
  loadStructure(url: string, format?: MolstarFormat): Promise<void>;
  setRepresentation(type: MolstarRepresentation): void;
  setColoring(scheme: MolstarColoring): void;
  resetCamera(): void;
}

export interface MolstarViewerProps {
  className?: string;
  style?: React.CSSProperties;
  onReady?: () => void;
}

const MolstarViewer = React.forwardRef<MolstarViewerRef, MolstarViewerProps>(
  function MolstarViewer({ className, style, onReady }, ref) {
    const containerRef = useRef<HTMLDivElement>(null);
    const pluginRef = useRef<PluginUIContext | null>(null);
    const onReadyRef = useRef(onReady);
    // Keep ref in sync without re-running the init effect.
    useEffect(() => {
      onReadyRef.current = onReady;
    }, [onReady]);

    useEffect(() => {
      const target = containerRef.current;
      if (!target) return;

      let disposed = false;
      let pluginInstance: PluginUIContext | null = null;

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
        onReadyRef.current?.();
      }

      init().catch((err) => {
        // eslint-disable-next-line no-console
        console.error("Mol* init failed:", err);
      });

      return () => {
        disposed = true;
        pluginInstance?.dispose();
        pluginRef.current = null;
      };
    }, []);

    useImperativeHandle(ref, () => ({
      async loadStructure(url: string, format: MolstarFormat = "pdb") {
        const plugin = pluginRef.current;
        if (!plugin) return;

        await plugin.clear();

        const data = await plugin.builders.data.download(
          { url, isBinary: false },
          { state: { isGhost: true } },
        );

        const trajectory = await plugin.builders.structure.parseTrajectory(
          data,
          format === "mmcif" ? "mmcif" : "pdb",
        );

        await plugin.builders.structure.hierarchy.applyPreset(
          trajectory,
          "default",
        );
      },

      setRepresentation(_type: MolstarRepresentation) {
        // Imperative representation switching is wired in P4 alongside the
        // selection slice.
      },

      setColoring(_scheme: MolstarColoring) {
        // Imperative coloring is wired in P4 alongside the selection slice.
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
