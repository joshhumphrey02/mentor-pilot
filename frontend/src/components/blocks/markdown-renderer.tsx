import 'katex/dist/katex.min.css'

import { type ComponentProps, useEffect, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

/**
 * The full Markdown renderer (GitHub tables and lists, KaTeX maths, highlighted
 * code). It is a separate chunk, loaded the first time a message needs it, so
 * the libraries stay out of the initial download.
 */

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [html, setHtml] = useState<string | null>(null)

  useEffect(() => {
    let current = true
    // The highlighter is heavier still, so it loads only when a message
    // actually contains a code block. Until then the code shows unstyled.
    void import('shiki/bundle/web')
      .then(({ codeToHtml }) =>
        codeToHtml(code, {
          lang: language,
          themes: { light: 'github-light', dark: 'github-dark' },
          defaultColor: false,
        }),
      )
      .then((result) => current && setHtml(result))
      .catch(() => undefined) // unknown language: keep the plain version
    return () => {
      current = false
    }
  }, [code, language])

  if (html) {
    // Safe: shiki escapes the code and emits only its own span markup.
    return <div className="code-block" dangerouslySetInnerHTML={{ __html: html }} />
  }
  return (
    <pre className="code-block">
      <code>{code}</code>
    </pre>
  )
}

const components: Components = {
  a: ({ node: _node, children, ...props }: ComponentProps<'a'> & { node?: unknown }) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
  pre: ({ children }) => <>{children}</>,
  code: ({ className, children }) => {
    const text = String(children ?? '')
    const language = /language-([\w-]+)/.exec(className ?? '')?.[1]
    // Fenced blocks have a language or span lines; everything else is inline.
    if (!language && !text.includes('\n')) return <code className="inline-code">{children}</code>
    return <CodeBlock code={text.replace(/\n$/, '')} language={language ?? 'text'} />
  },
  table: ({ node: _node, ...props }: ComponentProps<'table'> & { node?: unknown }) => (
    // Wide tables scroll inside themselves instead of widening the page.
    <div className="table-scroll">
      <table {...props} />
    </div>
  ),
}

export default function MarkdownRenderer({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={components}
      // Images only come through vetted gallery blocks, never from model text.
      disallowedElements={['img']}
    >
      {text}
    </ReactMarkdown>
  )
}
