import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-semibold text-zinc-900 dark:text-zinc-50">
      {children}
    </strong>
  ),
  ul: ({ children }) => (
    <ul className="flex list-disc flex-col gap-1 pl-5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="flex list-decimal flex-col gap-1 pl-5">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  h1: ({ children }) => <h3 className="font-semibold">{children}</h3>,
  h2: ({ children }) => <h3 className="font-semibold">{children}</h3>,
  h3: ({ children }) => <h3 className="font-semibold">{children}</h3>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium underline underline-offset-2"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-[0.85em] dark:bg-zinc-800">
      {children}
    </code>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-zinc-200 px-2 py-1.5 font-medium dark:border-zinc-800">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-zinc-100 px-2 py-1.5 dark:border-zinc-900">
      {children}
    </td>
  ),
};

export function Markdown({ children }: { children: string }) {
  return (
    <div className="flex flex-col gap-3 text-sm text-zinc-800 dark:text-zinc-200">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
