import { afterEach, describe, expect, it, vi } from 'vitest'
import { BrowserAudioQueue } from './BrowserAudioQueue'

class FakeAudio {
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  src = ''
  pause = vi.fn()
  play = vi.fn(async () => undefined)
}

describe('BrowserAudioQueue', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('reproduz em FIFO e só anuncia estados confirmados pelo elemento de áudio', async () => {
    vi.stubGlobal('atob', () => 'a')
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => `blob:${Math.random()}`), revokeObjectURL: vi.fn() })
    const audios: FakeAudio[] = []
    const events: string[] = []
    const queue = new BrowserAudioQueue({
      started: id => events.push(`start:${id}`), finished: id => events.push(`finish:${id}`),
      interrupted: id => events.push(`interrupt:${id}`), state: value => events.push(value),
    }, () => { const audio = new FakeAudio(); audios.push(audio); return audio as unknown as HTMLAudioElement })
    queue.enqueue({ type: 'tts_chunk', queue_id: 'one', audio: 'YQ==' })
    queue.enqueue({ type: 'tts_chunk', queue_id: 'two', audio: 'YQ==' })
    await Promise.resolve(); await Promise.resolve()
    expect(audios).toHaveLength(1)
    expect(events).toContain('start:one')
    audios[0].onended?.(); await Promise.resolve(); await Promise.resolve()
    expect(audios).toHaveLength(2)
    audios[1].onended?.(); await Promise.resolve(); await Promise.resolve()
    expect(events).toEqual(expect.arrayContaining(['finish:one', 'start:two', 'finish:two', 'LISTENING']))
  })
})
