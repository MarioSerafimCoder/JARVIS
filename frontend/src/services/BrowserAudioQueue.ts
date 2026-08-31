import type { VoiceEvent } from '../types'

type QueueCallbacks = {
  started: (queueId: string) => void
  finished: (queueId: string) => void
  interrupted: (queueId: string) => void
  state: (value: 'SPEAKING' | 'LISTENING') => void
}

type AudioFactory = (url: string) => HTMLAudioElement
type QueueItem = { event: VoiceEvent; url: string }

function audioBlob(value: string, mime = 'audio/wav') {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index)
  return new Blob([bytes], { type: mime })
}

/** A strict FIFO queue: one browser audio element may play at a time. */
export class BrowserAudioQueue {
  private queued: QueueItem[] = []
  private active?: { item: QueueItem; audio: HTMLAudioElement }
  private epoch = 0

  constructor(private callbacks: QueueCallbacks, private audioFactory: AudioFactory = url => new Audio(url)) {}

  get isPlaying() { return Boolean(this.active) }

  enqueue(event: VoiceEvent) {
    if (!event.audio || !event.queue_id) return
    this.queued.push({ event, url: URL.createObjectURL(audioBlob(event.audio, event.mime_type)) })
    void this.drain()
  }

  cancelAll() {
    this.epoch += 1
    for (const item of this.queued.splice(0)) {
      URL.revokeObjectURL(item.url)
      this.callbacks.interrupted(item.event.queue_id!)
    }
    if (this.active) {
      const { item, audio } = this.active
      this.active = undefined
      audio.pause(); audio.src = ''
      URL.revokeObjectURL(item.url)
      this.callbacks.interrupted(item.event.queue_id!)
    }
    this.callbacks.state('LISTENING')
  }

  private async drain() {
    if (this.active || !this.queued.length) return
    const epoch = this.epoch
    const item = this.queued.shift()!
    const audio = this.audioFactory(item.url)
    this.active = { item, audio }
    try {
      await audio.play()
      if (epoch !== this.epoch) return
      this.callbacks.state('SPEAKING')
      this.callbacks.started(item.event.queue_id!)
      await new Promise<void>(resolve => { audio.onended = () => resolve(); audio.onerror = () => resolve() })
      if (epoch === this.epoch) this.callbacks.finished(item.event.queue_id!)
    } finally {
      URL.revokeObjectURL(item.url)
      if (this.active?.item === item) this.active = undefined
      if (epoch === this.epoch) {
        if (!this.queued.length) this.callbacks.state('LISTENING')
        void this.drain()
      }
    }
  }
}
