/**
 * Project JARVIS: Central AudioSessionManager
 * 
 * Strict authoritative state machine controlling:
 * - Microphone capture & Speech-to-Text (ASR)
 * - Text-to-Speech (TTS) playback via SentenceChunkTTSQueue
 * - Acoustic echo cancellation & self-feedback loop prevention
 * - Hands-free continuous interaction & wake-word gating
 */

import { SentenceChunkTTSQueue, pickNaturalEnglishVoice } from './ttsQueue';

export type AudioState =
  | 'IDLE'
  | 'LISTENING'
  | 'USER_SPEECH_DETECTED'
  | 'PROCESSING'
  | 'SPEAKING'
  | 'WAITING_FOR_NEXT_COMMAND'
  | 'INTERRUPTED'
  | 'STOPPED'
  | 'PERMISSION_DENIED'
  | 'ERROR';

export interface AudioSessionCallbacks {
  onStateChange: (state: AudioState, message?: string) => void;
  onTranscript: (transcript: string, isFinal: boolean) => void;
  onCommandReady: (command: string) => void;
  onError: (error: string) => void;
}

export class AudioSessionManager {
  private static instance: AudioSessionManager | null = null;

  private state: AudioState = 'IDLE';
  private callbacks: AudioSessionCallbacks | null = null;
  private recognition: any = null;
  private mediaStream: MediaStream | null = null;
  private ttsQueue: SentenceChunkTTSQueue;

  private isHandsFree: boolean = false;
  private wakeWordRequired: boolean = false;
  private wakeWord: string = 'jarvis';

  // Echo cancellation & self-feedback suppression buffers
  private recentAssistantUtterances: string[] = [];
  private acousticTailTimeout: any = null;
  private restartListeningTimeout: any = null;
  private activeCommandPromise: Promise<void> | null = null;

  private constructor() {
    this.ttsQueue = new SentenceChunkTTSQueue({
      onStart: () => {
        this.handleTTSStart();
      },
      onEnd: () => {
        this.handleTTSEnd();
      },
      onError: (err) => {
        console.warn('[AudioSessionManager] TTS error:', err);
        this.handleTTSEnd();
      },
      onInterrupted: () => {
        this.transitionTo('INTERRUPTED');
      },
    });

    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = () => {
        const voices = window.speechSynthesis.getVoices();
        const bestVoice = pickNaturalEnglishVoice(voices);
        if (bestVoice) {
          this.ttsQueue.setVoice(bestVoice);
        }
      };
    }
  }

  public static getInstance(): AudioSessionManager {
    if (!AudioSessionManager.instance) {
      AudioSessionManager.instance = new AudioSessionManager();
    }
    return AudioSessionManager.instance;
  }

  public registerCallbacks(callbacks: AudioSessionCallbacks) {
    this.callbacks = callbacks;
    callbacks.onStateChange(this.state);
  }

  public getState(): AudioState {
    return this.state;
  }

  public isHandsFreeActive(): boolean {
    return this.isHandsFree;
  }

  public setHandsFree(enabled: boolean) {
    this.isHandsFree = enabled;
    if (enabled) {
      if (this.state === 'IDLE' || this.state === 'STOPPED') {
        this.startListening();
      }
    } else {
      if (this.state === 'LISTENING' || this.state === 'WAITING_FOR_NEXT_COMMAND') {
        this.stopListening();
        this.transitionTo('IDLE');
      }
    }
  }

  public setWakeWordEnabled(enabled: boolean) {
    this.wakeWordRequired = enabled;
  }

  /**
   * Request microphone with hardware/browser echo-cancellation and noise suppression
   */
  public async initializeMicrophone(): Promise<boolean> {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone mediaDevices API not supported');
      }

      if (!this.mediaStream) {
        this.mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: { ideal: true },
            noiseSuppression: { ideal: true },
            autoGainControl: { ideal: true },
          },
        });
      }
      return true;
    } catch (err: any) {
      console.error('[AudioSessionManager] Microphone initialization failed:', err);
      this.transitionTo('PERMISSION_DENIED', 'Microphone access denied or unavailable.');
      return false;
    }
  }

  /**
   * Start listening for user speech
   */
  public async startListening() {
    if (this.state === 'SPEAKING' || this.state === 'PROCESSING') {
      return;
    }

    this.clearTimeouts();

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      this.transitionTo('ERROR', 'Web Speech API is not supported in this browser.');
      return;
    }

    // Ensure audio device is initialized
    const hasMic = await this.initializeMicrophone();
    if (!hasMic) return;

    if (this.recognition) {
      try {
        this.recognition.onresult = null;
        this.recognition.onerror = null;
        this.recognition.onend = null;
        this.recognition.abort();
      } catch {
        // ignore
      }
      this.recognition = null;
    }

    try {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = 'en-US';
      this.recognition.continuous = false; // Turn-based single command capture
      this.recognition.interimResults = true;
      this.recognition.maxAlternatives = 1;

      this.recognition.onstart = () => {
        this.transitionTo('LISTENING');
      };

      this.recognition.onspeechstart = () => {
        if (this.state === 'LISTENING') {
          this.transitionTo('USER_SPEECH_DETECTED');
        }
      };

      this.recognition.onresult = (event: any) => {
        // Drop any results if Jarvis is speaking
        if (this.state === 'SPEAKING' || this.state === 'PROCESSING') {
          return;
        }

        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const item = event.results[i];
          const text = item[0]?.transcript || '';
          if (item.isFinal) {
            finalTranscript += text;
          } else {
            interimTranscript += text;
          }
        }

        const candidate = (finalTranscript || interimTranscript).trim();
        if (!candidate) return;

        // Anti-echo check: Verify transcript is not Jarvis's own acoustic echo
        if (this.isAcousticSelfEcho(candidate)) {
          console.warn('[AudioSessionManager] Dropped acoustic self-echo:', candidate);
          return;
        }

        if (this.callbacks) {
          this.callbacks.onTranscript(candidate, Boolean(finalTranscript));
        }

        if (finalTranscript) {
          this.handleValidatedSpeech(finalTranscript.trim());
        }
      };

      this.recognition.onerror = (event: any) => {
        if (event.error === 'no-speech') {
          // In hands-free mode, seamlessly restart
          if (this.isHandsFree && this.state !== 'SPEAKING' && this.state !== 'PROCESSING') {
            this.scheduleRestartListening(200);
            return;
          }
        } else if (event.error === 'aborted') {
          // Expected when aborted during state transitions
          return;
        } else if (event.error === 'not-allowed') {
          this.transitionTo('PERMISSION_DENIED', 'Microphone access denied.');
          return;
        }

        console.warn('[AudioSessionManager] ASR error:', event.error);
        if (this.isHandsFree && this.state !== 'SPEAKING') {
          this.scheduleRestartListening(400);
        } else {
          this.transitionTo('ERROR', `Recognition error: ${event.error}`);
        }
      };

      this.recognition.onend = () => {
        if (this.state === 'USER_SPEECH_DETECTED' || this.state === 'LISTENING') {
          if (this.isHandsFree) {
            this.scheduleRestartListening(300);
          } else {
            this.transitionTo('IDLE');
          }
        }
      };

      this.recognition.start();
    } catch (err: any) {
      console.error('[AudioSessionManager] Failed to start speech recognition:', err);
      if (this.isHandsFree) {
        this.scheduleRestartListening(500);
      }
    }
  }

  public stopListening() {
    this.clearTimeouts();
    if (this.recognition) {
      try {
        this.recognition.onresult = null;
        this.recognition.onerror = null;
        this.recognition.onend = null;
        this.recognition.abort();
      } catch {
        // ignore
      }
      this.recognition = null;
    }
    if (this.state === 'LISTENING' || this.state === 'USER_SPEECH_DETECTED') {
      this.transitionTo('STOPPED');
    }
  }

  /**
   * Speak Jarvis response while locking microphone to prevent feedback
   */
  public speakResponse(text: string) {
    if (!text || !text.trim()) return;

    // Record utterance for echo-detection
    this.recordAssistantUtterance(text);

    // Stop listening before TTS begins
    this.stopListening();
    this.transitionTo('SPEAKING');

    // Trigger TTS
    this.ttsQueue.speak(text);
  }

  public interrupt() {
    this.clearTimeouts();
    this.ttsQueue.stop();
    this.stopListening();
    this.transitionTo('INTERRUPTED');

    // If hands-free, recover to listening after a pause
    if (this.isHandsFree) {
      this.scheduleRestartListening(600);
    } else {
      this.transitionTo('IDLE');
    }
  }

  /**
   * Called when TTS begins speaking
   */
  private handleTTSStart() {
    this.stopListening();
    this.transitionTo('SPEAKING');
  }

  /**
   * Called when TTS finishes speaking
   */
  private handleTTSEnd() {
    // Acoustic tail delay: Wait 550ms for room reverb and speaker tail to dissipate
    this.clearTimeouts();
    this.acousticTailTimeout = setTimeout(() => {
      if (this.isHandsFree) {
        this.transitionTo('WAITING_FOR_NEXT_COMMAND');
        this.startListening();
      } else {
        this.transitionTo('IDLE');
      }
    }, 550);
  }

  private handleValidatedSpeech(rawSpeech: string) {
    let cleanCommand = rawSpeech.trim();

    // Check wake-word if required
    if (this.wakeWordRequired) {
      const lower = cleanCommand.toLowerCase();
      if (!lower.includes(this.wakeWord)) {
        // Wake-word missing, continue listening
        if (this.isHandsFree) {
          this.scheduleRestartListening(250);
        }
        return;
      }
      // Extract command after wake word
      const parts = lower.split(this.wakeWord);
      cleanCommand = parts.slice(1).join(' ').trim();
      if (!cleanCommand) {
        this.speakResponse('Yes, I am listening.');
        return;
      }
    }

    this.transitionTo('PROCESSING');
    this.stopListening();

    if (this.callbacks) {
      this.callbacks.onCommandReady(cleanCommand);
    }
  }

  private recordAssistantUtterance(text: string) {
    const cleaned = text
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .trim();
    if (!cleaned) return;

    this.recentAssistantUtterances.push(cleaned);
    // Keep last 15 spoken fragments
    if (this.recentAssistantUtterances.length > 15) {
      this.recentAssistantUtterances.shift();
    }
  }

  /**
   * Compares incoming transcript with recently spoken Jarvis output
   */
  private isAcousticSelfEcho(transcript: string): boolean {
    const normInput = transcript
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .trim();
    if (!normInput || normInput.length < 4) return false;

    for (const spoken of this.recentAssistantUtterances) {
      if (spoken.includes(normInput) || normInput.includes(spoken)) {
        return true;
      }
      // Word overlap token ratio
      const inputWords = new Set(normInput.split(/\s+/));
      const spokenWords = new Set(spoken.split(/\s+/));
      let matches = 0;
      for (const w of inputWords) {
        if (spokenWords.has(w) && w.length > 2) matches++;
      }
      const similarity = matches / Math.max(1, inputWords.size);
      if (similarity > 0.65) {
        return true;
      }
    }
    return false;
  }

  private scheduleRestartListening(delayMs: number) {
    this.clearTimeouts();
    this.restartListeningTimeout = setTimeout(() => {
      if (this.isHandsFree && this.state !== 'SPEAKING' && this.state !== 'PROCESSING') {
        this.startListening();
      }
    }, delayMs);
  }

  private clearTimeouts() {
    if (this.acousticTailTimeout) {
      clearTimeout(this.acousticTailTimeout);
      this.acousticTailTimeout = null;
    }
    if (this.restartListeningTimeout) {
      clearTimeout(this.restartListeningTimeout);
      this.restartListeningTimeout = null;
    }
  }

  private transitionTo(newState: AudioState, message?: string) {
    this.state = newState;
    if (this.callbacks) {
      this.callbacks.onStateChange(newState, message);
    }
  }
}
