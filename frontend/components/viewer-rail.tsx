"use client";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AnalyticsPanel } from "@/components/analytics-panel";
import { OverviewPanel } from "@/components/overview-panel";
import { SequencePanel } from "@/components/sequence-panel";

/**
 * The workspace's right rail (spec 4.1): Overview / Sequence / Analytics.
 *
 * Rendered twice by the viewer page — once as the `xl` side rail and once
 * stacked below the viewer at narrow widths — so it keeps its own tab state.
 */
export function ViewerRail({ proteinId }: { proteinId: string }) {
  return (
    <Tabs defaultValue="overview" className="flex h-full min-h-0 flex-col gap-0">
      <TabsList
        variant="line"
        className="h-9 w-full shrink-0 justify-start gap-1 border-b border-zinc-800 px-2"
      >
        <TabsTrigger value="overview" className="text-xs">
          Overview
        </TabsTrigger>
        <TabsTrigger value="sequence" className="text-xs">
          Sequence
        </TabsTrigger>
        <TabsTrigger value="analytics" className="text-xs">
          Analytics
        </TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="min-h-0 overflow-hidden">
        <OverviewPanel />
      </TabsContent>
      <TabsContent value="sequence" className="min-h-0 overflow-hidden">
        <SequencePanel />
      </TabsContent>
      <TabsContent value="analytics" className="min-h-0 overflow-hidden">
        <AnalyticsPanel proteinId={proteinId} />
      </TabsContent>
    </Tabs>
  );
}
