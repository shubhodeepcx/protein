import { Upload, Search, Atom } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { HealthPill } from "@/components/health-pill";
import { DropZone } from "@/components/drop-zone";

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Top header */}
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border/60 bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <Atom className="size-5 text-primary" aria-hidden />
          <span className="font-heading text-lg font-semibold tracking-tight">
            ProteoLens
          </span>
          <Badge variant="outline" className="ml-1 text-[10px] uppercase">
            P2
          </Badge>
        </div>

        <Separator orientation="vertical" className="h-6" />

        <div className="flex max-w-xl flex-1 items-center">
          <label
            htmlFor="global-search"
            className="sr-only"
          >
            Search proteins, chains, or residues
          </label>
          <div className="relative w-full">
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
            <input
              id="global-search"
              type="search"
              disabled
              placeholder="Search proteins, chains, residues…  (wired in P5)"
              className="h-8 w-full rounded-md border border-input bg-muted/40 pr-3 pl-8 text-xs text-muted-foreground placeholder:text-muted-foreground/70 focus-visible:outline-none disabled:cursor-not-allowed"
            />
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <HealthPill />
          <Button size="sm" disabled>
            <Upload aria-hidden />
            Upload
          </Button>
        </div>
      </header>

      {/* 3-column workspace shell */}
      <main className="grid flex-1 grid-cols-[18rem_1fr_24rem] overflow-hidden">
        {/* Left sidebar */}
        <aside className="flex w-72 flex-col border-r border-border/60 bg-card/30">
          <div className="flex items-center justify-between px-4 py-3">
            <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Chains &amp; residues
            </h2>
            <Badge variant="secondary" className="text-[10px]">
              empty
            </Badge>
          </div>
          <Separator />
          <ScrollArea className="flex-1">
            <div className="space-y-3 p-4 text-xs text-muted-foreground">
              <p>
                The chain tree and residue filters render here once a protein
                is loaded.
              </p>
              <p className="leading-relaxed">
                Upload a PDB / mmCIF or import from RCSB, AlphaFold, or UniProt
                in <span className="font-medium text-foreground">P2</span> and{" "}
                <span className="font-medium text-foreground">P5</span>.
              </p>
            </div>
          </ScrollArea>
        </aside>

        {/* Center viewer area */}
        <section className="flex flex-col bg-background">
          <div className="flex h-10 items-center gap-2 border-b border-border/60 px-4 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Viewer</span>
            <Separator orientation="vertical" className="h-4" />
            <span>No protein loaded &mdash; drop a file to start</span>
          </div>
          <div className="flex flex-1 items-center justify-center p-6">
            <DropZone />
          </div>
        </section>

        {/* Right tabbed panel */}
        <aside className="flex w-96 flex-col border-l border-border/60 bg-card/30">
          <Tabs defaultValue="overview" className="flex h-full flex-col gap-0">
            <TabsList className="m-3 w-[calc(100%-1.5rem)] shrink-0">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="sequence">Sequence</TabsTrigger>
              <TabsTrigger value="analytics">Analytics</TabsTrigger>
            </TabsList>
            <Separator />
            <ScrollArea className="flex-1">
              <TabsContent value="overview" className="m-0 p-4">
                <PanelPlaceholder
                  title="Overview"
                  body="Metric cards (MW, residues, atoms, chains) arrive in P3."
                />
              </TabsContent>
              <TabsContent value="sequence" className="m-0 p-4">
                <PanelPlaceholder
                  title="Sequence"
                  body="Per-chain sequence panel with click-to-highlight sync arrives in P4."
                />
              </TabsContent>
              <TabsContent value="analytics" className="m-0 p-4">
                <PanelPlaceholder
                  title="Analytics"
                  body="Composition, secondary structure, and hydrophobicity charts arrive in P3."
                />
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </aside>
      </main>
    </div>
  );
}

function PanelPlaceholder({ title, body }: { title: string; body: string }) {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
        <CardDescription>Coming in P3 / P4</CardDescription>
      </CardHeader>
      <CardContent className="text-xs leading-relaxed text-muted-foreground">
        {body}
      </CardContent>
    </Card>
  );
}
