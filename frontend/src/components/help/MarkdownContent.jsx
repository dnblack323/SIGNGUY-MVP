import { Fragment } from "react";
import { Link } from "react-router-dom";
import { Info } from "lucide-react";

/**
 * Renders the small Markdown subset used by Help articles (headings, paragraphs, lists, quotes, bold,
 * italic, code, links) as React elements. Article text is never injected as HTML, and links are limited
 * to in-app paths and https URLs.
 */
const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*\s][^*]*\*)/g;

function isInternal(url) {
  return url.startsWith("/") && !url.startsWith("//");
}

function Inline({ text }) {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={i} className="rounded bg-muted px-1 py-0.5 text-[0.85em]">{part.slice(1, -1)}</code>;
    if (part.startsWith("[")) {
      const [, label, url] = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/) || [];
      if (label && isInternal(url)) return <Link key={i} to={url} className="text-primary underline underline-offset-2">{label}</Link>;
      if (label && url.startsWith("https://")) return <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2">{label}</a>;
      return <Fragment key={i}>{label || part}</Fragment>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function parseBlocks(markdown) {
  const blocks = [];
  let current = null;
  const flush = () => { if (current) blocks.push(current); current = null; };
  for (const raw of (markdown || "").replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const heading = line.match(/^(#{2,3})\s+(.*)$/);
    const bullet = line.match(/^\s*[-*]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+\.\s+(.*)$/);
    const quote = line.match(/^>\s?(.*)$/);
    if (!line.trim()) flush();
    else if (heading) { flush(); blocks.push({ type: `h${heading[1].length}`, text: heading[2] }); }
    else if (bullet) { if (current?.type !== "ul") { flush(); current = { type: "ul", items: [] }; } current.items.push(bullet[1]); }
    else if (numbered) { if (current?.type !== "ol") { flush(); current = { type: "ol", items: [] }; } current.items.push(numbered[1]); }
    else if (quote) { if (current?.type !== "quote") { flush(); current = { type: "quote", lines: [] }; } current.lines.push(quote[1]); }
    else if (current?.type === "p") current.lines.push(line.trim());
    else { flush(); current = { type: "p", lines: [line.trim()] }; }
  }
  flush();
  return blocks;
}

export default function MarkdownContent({ markdown, className = "" }) {
  return (
    <div className={`space-y-3 text-sm leading-relaxed ${className}`} data-testid="help-article-body">
      {parseBlocks(markdown).map((block, i) => {
        switch (block.type) {
          case "h2": return <h2 key={i} className="pt-3 text-lg font-semibold tracking-tight">{block.text}</h2>;
          case "h3": return <h3 key={i} className="pt-2 text-base font-semibold">{block.text}</h3>;
          case "ul": return <ul key={i} className="list-disc space-y-1 pl-5">{block.items.map((t, j) => <li key={j}><Inline text={t} /></li>)}</ul>;
          case "ol": return <ol key={i} className="list-decimal space-y-1 pl-5">{block.items.map((t, j) => <li key={j}><Inline text={t} /></li>)}</ol>;
          case "quote": return (
            <div key={i} className="flex gap-2 rounded-md border bg-muted/50 p-3" role="note">
              <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <p><Inline text={block.lines.join(" ")} /></p>
            </div>
          );
          default: return <p key={i}><Inline text={block.lines.join(" ")} /></p>;
        }
      })}
    </div>
  );
}
