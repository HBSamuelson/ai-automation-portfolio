import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-border bg-card/80">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="font-display text-xl text-primary">
          BrightSmile Dental
        </Link>
        <nav className="flex gap-4 text-sm">
          <Link href="/#visits" className="hover:text-primary">Visits</Link>
          <Link href="/desk" className="hover:text-primary">Front desk</Link>
          <Link href="/report" className="hover:text-primary">Test report</Link>
          <a href="tel:+13035550140" className="hidden sm:inline hover:text-primary">(303) 555-0140</a>
        </nav>
      </div>
    </header>
  );
}
