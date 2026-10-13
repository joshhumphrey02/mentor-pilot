import { ArrowUpIcon, ImagePlusIcon, Loader2Icon, MicIcon, XIcon } from 'lucide-react'
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { toast } from 'sonner'

import { uploadPhoto } from '@/features/workspace/api'
import { useSpeechInput } from '@/hooks/use-speech-input'
import { errorMessage } from '@/lib/api/errors'
import { cn } from '@/lib/utils'

const MAX_LENGTH = 4000
const DEFAULT_PHOTO_MESSAGE = 'Here is a photo. What do you think?'

interface ComposerProps {
  projectId: string
  onSend: (text: string, attachmentIds?: string[]) => void
  /** True while the mentor is replying: typing is allowed, sending is not. */
  busy: boolean
  suggestions: string[]
}

interface Photo {
  /** Null while the upload is still in flight. */
  id: string | null
  preview: string
}

const tool =
  'grid size-11 shrink-0 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground'

export function Composer({ projectId, onSend, busy, suggestions }: ComposerProps) {
  const [text, setText] = useState('')
  const [photo, setPhoto] = useState<Photo | null>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const uploading = photo !== null && photo.id === null
  const canSend = (text.trim().length > 0 || photo?.id) && !busy && !uploading

  const speech = useSpeechInput(
    useCallback((heard: string) => setText((current) => `${current} ${heard}`.trim()), []),
  )

  // Free the preview image when it is replaced or the composer goes away.
  useEffect(() => {
    const url = photo?.preview
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [photo?.preview])

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!canSend) return
    onSend(text.trim() || DEFAULT_PHOTO_MESSAGE, photo?.id ? [photo.id] : [])
    setText('')
    setPhoto(null)
    // Keep the keyboard open on phones: sending should not dismiss it.
    input.current?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends with a physical keyboard. On touch screens Enter makes a
    // new line, because there is a send button under the thumb and no Shift.
    const touch = window.matchMedia('(pointer: coarse)').matches
    if (event.key === 'Enter' && !event.shiftKey && !touch && !event.nativeEvent.isComposing) {
      submit()
      event.preventDefault()
    }
  }

  const onPick = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = '' // so choosing the same photo again still fires
    if (!file) return
    const preview = URL.createObjectURL(file)
    setPhoto({ id: null, preview })
    try {
      const uploaded = await uploadPhoto(projectId, file)
      setPhoto((current) => (current?.preview === preview ? { id: uploaded.id, preview } : current))
    } catch (error) {
      setPhoto((current) => (current?.preview === preview ? null : current))
      toast.error(errorMessage(error))
    }
  }

  return (
    <div className="border-t bg-background/95 backdrop-blur">
      <div className="mx-auto w-full max-w-3xl px-safe pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        {suggestions.length > 0 && !busy && (
          <ul
            aria-label="Suggested replies"
            className="-mx-4 mb-2 flex gap-2 overflow-x-auto px-4 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0"
          >
            {suggestions.map((suggestion) => (
              <li key={suggestion} className="shrink-0">
                <button
                  type="button"
                  onClick={() => onSend(suggestion)}
                  className="min-h-11 rounded-full border bg-card px-4 text-sm font-medium text-secondary-foreground hover:border-primary hover:bg-secondary"
                >
                  {suggestion}
                </button>
              </li>
            ))}
          </ul>
        )}

        <form
          onSubmit={submit}
          className="rounded-3xl border bg-card p-1.5 shadow-soft focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30"
        >
          {photo && (
            <div className="relative m-1.5 mb-0 inline-block">
              <img
                src={photo.preview}
                alt="Ready to send"
                className={cn('size-20 rounded-xl border object-cover', uploading && 'opacity-50')}
              />
              {uploading && (
                <span role="status" className="absolute inset-0 grid place-items-center">
                  <Loader2Icon aria-hidden="true" className="size-6 animate-spin" />
                  <span className="sr-only">Uploading photo</span>
                </span>
              )}
              <button
                type="button"
                aria-label="Remove photo"
                onClick={() => setPhoto(null)}
                className="absolute -top-3 -right-3 grid size-8 place-items-center rounded-full border bg-background shadow-soft"
              >
                <XIcon aria-hidden="true" className="size-4" />
              </button>
            </div>
          )}

          <div className="flex items-end gap-1">
            <input
              ref={picker}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              tabIndex={-1}
              aria-hidden="true"
              onChange={onPick}
            />
            <button
              type="button"
              className={tool}
              aria-label="Add a photo of your sketch, circuit or setup"
              onClick={() => picker.current?.click()}
            >
              <ImagePlusIcon aria-hidden="true" className="size-5" />
            </button>

            <label htmlFor="chat-input" className="sr-only">
              Message your mentor
            </label>
            <textarea
              id="chat-input"
              ref={input}
              value={text}
              rows={1}
              maxLength={MAX_LENGTH}
              placeholder="Message your mentor"
              enterKeyHint="send"
              onChange={(event) => setText(event.target.value)}
              onKeyDown={onKeyDown}
              // 16px text stops iOS zooming in on focus. The field grows with
              // its content up to about six lines, then scrolls.
              className="field-sizing-content max-h-40 min-h-11 flex-1 resize-none bg-transparent px-1 py-2.5 text-base outline-none placeholder:text-muted-foreground"
            />

            {speech.supported && (
              <button
                type="button"
                className={cn(tool, speech.listening && 'bg-danger-soft text-danger')}
                aria-label={speech.listening ? 'Stop listening' : 'Speak your message'}
                aria-pressed={speech.listening}
                onClick={speech.toggle}
              >
                <MicIcon aria-hidden="true" className={cn('size-5', speech.listening && 'animate-pulse')} />
              </button>
            )}
            <button
              type="submit"
              disabled={!canSend}
              aria-label="Send message"
              className={cn(
                'grid size-11 shrink-0 place-items-center rounded-full transition-colors',
                canSend
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              <ArrowUpIcon aria-hidden="true" className="size-5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
