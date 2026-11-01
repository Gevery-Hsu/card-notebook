import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
export function Markdown({ body }: { body: string }) {
  return <div className="note-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
    a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img: ({ alt }) => <span>{alt || '[图片]'}</span>,
  }}>{body}</ReactMarkdown></div>
}
