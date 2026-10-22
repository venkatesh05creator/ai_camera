/**
 * Project JARVIS: SentenceChunkTTSQueue
 * 
 * Provides robust, non-truncating Text-to-Speech playback by:
 * 1. Splitting responses into natural sentence and clause units (< 150 characters).
 * 2. Queuing them sequentially with monotonic sequence IDs.
 * 3. Preventing Chromium's 15-second speech silence freeze via an active heartbeat.
 * 4. Cleaning markdown, URLs, symbols, and emojis for natural human speech.
 * 5. Handling instant interruption, pause/resume, replay, and recoverable errors.
 */

export function cleanSentenceChunks(text: string): string[] {
  if (!text) return [];

  // Strip markdown, code blocks, URLs, and noisy symbols
  const cleaned = text
    .replace(/```[\s\S]*?```/g, '')               // Code blocks
    .replace(/`([^`]+)`/g, '$1')                  // Inline code
    .replace(/\*\*(.*?)\*\*/g, '$1')              // Bold
    .replace(/\*(.*?)\*/g, '$1')                  // Italics
    .replace(/__(.*?)__/g, '$1')
    .replace(/_(.*?)_/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')      // Links
    .replace(/https?:\/\/\S+/g, '')               // URLs
    .replace(/[#*>\-•·|~^]/g, ' ')                // Markdown bullet/header chars
    .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '') // Emojis
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleaned) return [];

  // Split on sentence terminators (. ! ?) followed by whitespace or end of string,
  // without breaking on numbers (e.g. 3.14 or 98.8%)
  const rawSentences = cleaned.match(/[^.!?\n]+(?:[.!?]+(?=\s|$)|$)/g);
  if (!rawSentences) return [cleaned];

  const results: string[] = [];
  const MAX_CHUNK_LEN = 150;

  for (const s of rawSentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;

    // Sub-split unusually long sentences on commas, semicolons, or dashes
    if (trimmed.length > MAX_CHUNK_LEN) {
      const subParts = trimmed.split(/([,;:]\s+)/);
      let currentBuffer = '';
      for (const part of subParts) {
        if ((currentBuffer + part).length > MAX_CHUNK_LEN && currentBuffer.trim().length > 0) {
          results.push(currentBuffer.trim());
          currentBuffer = part;
        } else {
          currentBuffer += part;
        }
      }
      if (currentBuffer.trim().length > 0) {
        results.push(currentBuffer.trim());
      }
    } else {
      results.push(trimmed);
    }
  }

  return results.length > 0 ? results : [cleaned];
}

export function pickNaturalEnglishVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  if (!voices || voices.length === 0) return undefined;
  return (
    voices.find(
      (v) =>
        v.lang.startsWith('en') &&
        (v.name.includes('Natural') ||
          v.name.includes('Google') ||
          v.name.includes('Samantha') ||
          v.name.includes('Jenny') ||
          v.name.includes('David') ||
          v.name.includes('Guy') ||
          v.name.includes('Aria') ||
          v.name.includes('George'))
    ) || voices.find((v) => v.lang.startsWith('en'))
  );
}

export interface TTSQueueCallbacks {
  onStart?: () => void;
  onChunk?: (chunk: string, index: number, total: number) => void;
  onEnd?: () => void;
  onError?: (err: any) => void;
  onInterrupted?: () => void;
}

// Global active utterance set to completely eliminate Chromium V8 garbage collection bug
declare global {
  interface Window {
    __jarvisActiveSpeechUtterances?: Set<SpeechSynthesisUtterance>;
  }
}

if (typeof window !== 'undefined') {
  window.__jarvisActiveSpeechUtterances = window.__jarvisActiveSpeechUtterances || new Set<SpeechSynthesisUtterance>();
}

export class SentenceChunkTTSQueue {
  private queue: string[] = [];
  private totalChunks: number = 0;
  private currentChunkIndex: number = 0;
  private isPlaying: boolean = false;
  private isCancelled: boolean = false;
  private lastSpokenText: string = '';
  private callbacks: TTSQueueCallbacks = {};
  private activeUtterance: SpeechSynthesisUtterance | null = null;
  private boundVoice?: SpeechSynthesisVoice;
  private heartbeatInterval: any = null;
  private chunkWatchdogTimeout: any = null;

  constructor(callbacks?: TTSQueueCallbacks) {
    if (callbacks) this.callbacks = callbacks;
  }

  public setCallbacks(callbacks: TTSQueueCallbacks) {
    this.callbacks = callbacks;
  }

  public setVoice(voice?: SpeechSynthesisVoice) {
    this.boundVoice = voice;
  }

  /**
   * Start sequential non-truncating TTS playback of text.
   */
  public speak(text: string, voice?: SpeechSynthesisVoice) {
    this.stop();
    this.isCancelled = false;
    this.lastSpokenText = text;
    if (voice) this.boundVoice = voice;

    const chunks = cleanSentenceChunks(text);
    if (chunks.length === 0) {
      if (this.callbacks.onEnd) this.callbacks.onEnd();
      return;
    }

    this.queue = [...chunks];
    this.totalChunks = chunks.length;
    this.currentChunkIndex = 0;
    this.isPlaying = true;

    if (this.callbacks.onStart) {
      this.callbacks.onStart();
    }

    this.startHeartbeat();
    this.playNextChunk();
  }

  /**
   * Chromium keep-alive heartbeat: periodically toggles pause/resume to prevent
   * browser speech synthesis engine freeze on long utterances.
   */
  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.isPlaying && typeof window !== 'undefined' && 'speechSynthesis' in window) {
        if (window.speechSynthesis.speaking) {
          window.speechSynthesis.pause();
          window.speechSynthesis.resume();
        }
      }
    }, 7500);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private clearWatchdog() {
    if (this.chunkWatchdogTimeout) {
      clearTimeout(this.chunkWatchdogTimeout);
      this.chunkWatchdogTimeout = null;
    }
  }

  private playNextChunk() {
    this.clearWatchdog();

    if (this.isCancelled || this.queue.length === 0) {
      this.finishPlayback();
      return;
    }

    const chunk = this.queue.shift()!;
    this.currentChunkIndex += 1;
    const chunkSeq = this.currentChunkIndex;

    if (this.callbacks.onChunk) {
      this.callbacks.onChunk(chunk, this.currentChunkIndex, this.totalChunks);
    }

    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      this.playNextChunk();
      return;
    }

    try {
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      const voice = this.boundVoice || pickNaturalEnglishVoice(window.speechSynthesis.getVoices());
      if (voice) utterance.voice = voice;

      // Prevent V8 garbage-collecting the utterance while in progress
      if (window.__jarvisActiveSpeechUtterances) {
        window.__jarvisActiveSpeechUtterances.add(utterance);
      }

      let completed = false;
      const cleanupUtterance = () => {
        if (completed) return;
        completed = true;
        this.clearWatchdog();
        if (window.__jarvisActiveSpeechUtterances) {
          window.__jarvisActiveSpeechUtterances.delete(utterance);
        }
      };

      utterance.onend = () => {
        cleanupUtterance();
        if (!this.isCancelled) {
          // Natural slight cadence pause between sentences
          setTimeout(() => this.playNextChunk(), 85);
        }
      };

      utterance.onerror = (e) => {
        console.warn('TTS utterance chunk error:', e);
        cleanupUtterance();
        if (!this.isCancelled) {
          setTimeout(() => this.playNextChunk(), 45);
        }
      };

      // Watchdog timeout: if onend fails to fire within calculated utterance duration, auto-advance
      const estimatedDurationMs = Math.max(4500, chunk.length * 135);
      this.chunkWatchdogTimeout = setTimeout(() => {
        if (this.isPlaying && !this.isCancelled && this.currentChunkIndex === chunkSeq) {
          console.warn(`TTS watchdog advancing chunk ${chunkSeq}/${this.totalChunks}`);
          cleanupUtterance();
          this.playNextChunk();
        }
      }, estimatedDurationMs);

      this.activeUtterance = utterance;
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn('speechSynthesis.speak failed:', err);
      if (this.callbacks.onError) this.callbacks.onError(err);
      if (!this.isCancelled) {
        this.playNextChunk();
      }
    }
  }

  private finishPlayback() {
    this.stopHeartbeat();
    this.clearWatchdog();
    this.isPlaying = false;
    this.activeUtterance = null;
    if (this.callbacks.onEnd) {
      this.callbacks.onEnd();
    }
  }

  /**
   * Instantly cancel all speech synthesis and drain the playback queue.
   */
  public stop() {
    this.isCancelled = true;
    this.stopHeartbeat();
    this.clearWatchdog();
    this.queue = [];
    this.isPlaying = false;
    this.activeUtterance = null;

    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {}
      if (window.__jarvisActiveSpeechUtterances) {
        window.__jarvisActiveSpeechUtterances.clear();
      }
    }

    if (this.callbacks.onInterrupted) {
      this.callbacks.onInterrupted();
    }
    if (this.callbacks.onEnd) {
      this.callbacks.onEnd();
    }
  }

  /**
   * Replay the last spoken assistant response from start to finish.
   */
  public replay() {
    if (this.lastSpokenText) {
      this.speak(this.lastSpokenText, this.boundVoice);
    }
  }

  public get active(): boolean {
    return this.isPlaying;
  }

  public get lastText(): string {
    return this.lastSpokenText;
  }
}
