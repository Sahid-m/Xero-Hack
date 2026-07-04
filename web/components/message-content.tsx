"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MessageContent({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
        strong: ({ children }) => (
          <strong className="font-semibold text-zinc-100">{children}</strong>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 list-decimal space-y-1.5 pl-5 last:mb-0">{children}</ol>
        ),
        ul: ({ children }) => (
          <ul className="mb-3 list-disc space-y-1.5 pl-5 last:mb-0">{children}</ul>
        ),
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        hr: () => <hr className="my-4 border-white/10" />,
        table: ({ children }) => (
          <div className="my-3 overflow-x-auto rounded-lg ring-1 ring-white/[0.08]">
            <table className="w-full min-w-[280px] border-collapse text-left text-xs">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-zinc-800/80 text-zinc-200">{children}</thead>
        ),
        tbody: ({ children }) => <tbody className="divide-y divide-white/[0.06]">{children}</tbody>,
        tr: ({ children }) => <tr className="hover:bg-white/[0.02]">{children}</tr>,
        th: ({ children }) => (
          <th className="px-3 py-2 font-medium whitespace-nowrap">{children}</th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 text-zinc-400 whitespace-nowrap">{children}</td>
        ),
        code: ({ className, children }) => {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <code className="my-2 block overflow-x-auto rounded-lg bg-zinc-950/80 p-3 text-xs text-zinc-300">
                {children}
              </code>
            );
          }
          return (
            <code className="rounded bg-zinc-800/80 px-1.5 py-0.5 text-[0.85em] text-teal-200">
              {children}
            </code>
          );
        },
        h3: ({ children }) => (
          <h3 className="mb-2 mt-4 text-sm font-semibold text-zinc-100 first:mt-0">{children}</h3>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
