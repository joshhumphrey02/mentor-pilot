import { useCallback, useEffect, useRef, useState } from 'react'

// The Web Speech API is not in TypeScript's DOM types, and Safari and Chrome
// still expose it under a vendor prefix. Only what is used here is described.
interface RecognitionResult {
  isFinal: boolean
  0: { transcript: string }
}
interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: { resultIndex: number; results: ArrayLike<RecognitionResult> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}
type RecognitionConstructor = new () => Recognition

function getRecognition(): RecognitionConstructor | null {
  const scope = window as unknown as {
    SpeechRecognition?: RecognitionConstructor
    webkitSpeechRecognition?: RecognitionConstructor
  }
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null
}

/**
 * Dictation into a text field, where the browser supports it. Typing on a
 * phone is slow, and some learners explain better out loud.
 */
export function useSpeechInput(onText: (text: string) => void, lang = 'en-ZA') {
  const [listening, setListening] = useState(false)
  const recognition = useRef<Recognition | null>(null)
  const supported = getRecognition() !== null

  useEffect(() => () => recognition.current?.stop(), [])

  const toggle = useCallback(() => {
    if (recognition.current) {
      recognition.current.stop()
      return
    }
    const Constructor = getRecognition()
    if (!Constructor) return
    const session = new Constructor()
    session.lang = lang
    session.continuous = true
    session.interimResults = false
    session.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        if (result?.isFinal) onText(result[0].transcript.trim())
      }
    }
    const done = () => {
      recognition.current = null
      setListening(false)
    }
    session.onend = done
    session.onerror = done
    recognition.current = session
    setListening(true)
    session.start()
  }, [lang, onText])

  return { supported, listening, toggle }
}
