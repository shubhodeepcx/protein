/**
 * Mol* plugin construction, kept out of `components/molstar-viewer.tsx` for the
 * same reason `lib/molstar/actions.ts` is: none of it is React, and the
 * component is meant to stay a thin ref-forwarding shell (AGENTS.md section 3
 * caps components at 200 LOC).
 */

import { createPluginUI } from "molstar/lib/mol-plugin-ui";
import { renderReact18 } from "molstar/lib/mol-plugin-ui/react18";
import { DefaultPluginUISpec } from "molstar/lib/mol-plugin-ui/spec";
import type { PluginUIContext } from "molstar/lib/mol-plugin-ui/context";

/**
 * Creates a plugin with every built-in Mol* panel hidden.
 *
 * ProteoLens drives representation, coloring, and selection from its own
 * toolbar and rail, so Mol*'s controls would be a second, desynchronised set of
 * the same knobs. Only the canvas is kept.
 */
export async function createViewerPlugin(
  target: HTMLElement,
): Promise<PluginUIContext> {
  const spec = DefaultPluginUISpec();
  return createPluginUI({
    target,
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
}
