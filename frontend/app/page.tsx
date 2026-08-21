import Link from "next/link";
import { Upload, Search, Atom, Database } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
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
            MVP
          </Badge>
        </div>

        <Separator orientation="vertical" className="h-6" />

        <div className="flex max-w-xl flex-1 items-center">
          {/* Entry point to the P5 database search page. */}
          <Link
            href="/search"
            className="relative flex h-8 w-full items-center rounded-md border border-input bg-muted/40 pr-3 pl-8 text-xs text-muted-foreground transition-colors hover:border-border hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2"
              aria-hidden
            />
            Search RCSB PDB, AlphaFold DB, or UniProt&hellip;
          </Link>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <HealthPill />
          <Link
            href="/search"
            className={buttonVariants({ size: "sm", variant: "secondary" })}
          >
            <Database aria-hidden />
            Databases
          </Link>
          <Link
            href="#upload"
            className={buttonVariants({ size: "sm" })}
          >
            <Upload aria-hidden />
            Upload
          </Link>
        </div>
      </header>

      {/* Responsive workspace shell.
          - mobile (<md): single column, both side panels hidden
          - tablet (md..xl): left rail + center, right panel hidden
          - desktop (xl+): full three-column layout */}
      <main className="grid flex-1 grid-cols-1 overflow-hidden md:grid-cols-[16rem_1fr] xl:grid-cols-[18rem_1fr_24rem]">
        {/* Left sidebar — hidden on mobile, narrower on tablet */}
        <aside className="hidden w-full flex-col border-r border-border/60 bg-card/30 md:flex xl:w-72">
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
                Load a protein to explore its chains, sequence, and analytics
                side by side with the 3D structure.
              </p>
              <p className="leading-relaxed">
                Upload a PDB / mmCIF file, or import a structure from RCSB PDB,
                AlphaFold DB, or UniProt.
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
          <div
            id="upload"
            className="flex flex-1 items-center justify-center p-6"
          >
            <DropZone />
          </div>
        </section>

        {/* Right tabbed panel — desktop only (xl+) */}
        <aside className="hidden w-96 flex-col border-l border-border/60 bg-card/30 xl:flex">
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
                  body="Metric cards — MW, residues, atoms, chains — appear here once a protein is loaded."
                />
              </TabsContent>
              <TabsContent value="sequence" className="m-0 p-4">
                <PanelPlaceholder
                  title="Sequence"
                  body="The per-chain sequence panel, with click-to-highlight sync to the 3D view, appears here once a protein is loaded."
                />
              </TabsContent>
              <TabsContent value="analytics" className="m-0 p-4">
                <PanelPlaceholder
                  title="Analytics"
                  body="Composition, secondary-structure, and hydrophobicity charts appear here once a protein is loaded."
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
        <CardDescription>No protein loaded</CardDescription>
      </CardHeader>
      <CardContent className="text-xs leading-relaxed text-muted-foreground">
        {body}
      </CardContent>
    </Card>
  );
}
