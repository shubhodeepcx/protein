import Link from "next/link";
import {
  Upload,
  Search,
  Atom,
  Database,
  FileDown,
  Boxes,
  ArrowRight,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
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
import {
  DATA_SOURCES,
  DataSourceCard,
  RAIL_TABS,
  RailTabPreview,
} from "@/components/rail-tab-preview";

/** Left-rail entry points. Every one of these is a route that exists today. */
const QUICK_ACTIONS = [
  {
    href: "/viewer/demo",
    icon: Boxes,
    title: "Open the demo structure",
    body: "Crambin (1CRN) — 46 residues, one chain, bundled with the server.",
  },
  {
    href: "/search",
    icon: Database,
    title: "Search the databases",
    body: "RCSB PDB, AlphaFold DB and UniProt in one query, then import a hit.",
  },
  {
    href: "#upload",
    icon: FileDown,
    title: "Drop a PDB or mmCIF file",
    body: "Parsed server-side into chains, residues, atoms and molecular weight.",
  },
] as const;

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
          <Link href="#upload" className={buttonVariants({ size: "sm" })}>
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
        {/* Left sidebar — the chain tree's home once a structure is open. */}
        <aside className="hidden w-full flex-col border-r border-border/60 bg-card/30 md:flex xl:w-72">
          <div className="flex items-center justify-between px-4 py-2.5">
            <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Chains &amp; residues
            </h2>
            <Badge variant="secondary" className="text-[10px]">
              no structure
            </Badge>
          </div>
          <Separator />
          <ScrollArea className="flex-1">
            <nav
              data-testid="quick-actions"
              className="flex flex-col gap-1.5 p-3"
            >
              {QUICK_ACTIONS.map(({ href, icon: Icon, title, body }) => (
                <Link
                  key={href}
                  href={href}
                  className="group rounded-md border border-border/60 bg-background/40 px-3 py-2 transition-colors hover:border-border hover:bg-accent/40"
                >
                  <span className="flex items-center gap-1.5 text-xs font-medium">
                    <Icon className="size-3.5 text-primary" aria-hidden />
                    {title}
                    <ArrowRight
                      className="ml-auto size-3 opacity-0 transition-opacity group-hover:opacity-100"
                      aria-hidden
                    />
                  </span>
                  <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
                    {body}
                  </span>
                </Link>
              ))}
            </nav>
            <Separator />
            <p className="p-3 text-[11px] leading-relaxed text-muted-foreground">
              With a structure open this rail becomes its chain tree: one row
              per chain with residue count, share of the structure and
              composition, expanding to residue-range chips that highlight
              straight into the 3D view.
            </p>
          </ScrollArea>
        </aside>

        {/* Center viewer area */}
        <section className="flex flex-col bg-background">
          <div className="flex h-10 items-center gap-2 border-b border-border/60 px-4 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Viewer</span>
            <Separator orientation="vertical" className="h-4" />
            <span>No protein loaded &mdash; drop a file to start</span>
            <Link
              href="/viewer/demo"
              className="ml-auto text-xs text-primary hover:underline"
            >
              Open the demo instead
            </Link>
          </div>
          {/* `molecular-field` is a CSS-only backdrop defined in globals.css.
              It lives here and nowhere near the viewer route, so it cannot
              interfere with the Mol* canvas. */}
          <div className="molecular-field flex-1 overflow-y-auto">
            <div
              id="upload"
              className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-6 py-8"
            >
              <DropZone />

              <section aria-labelledby="sources-heading">
                <h2
                  id="sources-heading"
                  className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
                >
                  Wired to
                </h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {DATA_SOURCES.map((source) => (
                    <DataSourceCard key={source.name} source={source} />
                  ))}
                </div>
              </section>
            </div>
          </div>
        </section>

        {/* Right tabbed panel — desktop only (xl+). Mirrors the five tabs the
            viewer's rail actually renders. */}
        <aside className="hidden w-96 flex-col border-l border-border/60 bg-card/30 xl:flex">
          <Tabs defaultValue="overview" className="flex h-full flex-col gap-0">
            <TabsList className="m-2 w-[calc(100%-1rem)] shrink-0 gap-0.5">
              {RAIL_TABS.map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="px-1.5 text-[11px]"
                >
                  {tab.title}
                </TabsTrigger>
              ))}
            </TabsList>
            <Separator />
            <ScrollArea className="flex-1">
              {RAIL_TABS.map((tab) => (
                <TabsContent key={tab.value} value={tab.value} className="m-0 p-3">
                  <RailTabPreview tab={tab} />
                </TabsContent>
              ))}
            </ScrollArea>
          </Tabs>
        </aside>
      </main>
    </div>
  );
}
