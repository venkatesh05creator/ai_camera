/* Voice interface: speech recognition (input) and speech synthesis (output).
 *
 * Privacy
 * - The audio never reaches this server.  The browser performs the speech
 *   recognition and sends the resulting text, exactly like a typed message.
 * - Some browsers implement the recognition in the cloud (Chrome sends the
 *   audio to the browser vendor).  That is why the microphone is only used
 *   after an explicit consent and why the notice is shown next to the button.
 * - Transcripts are not written to the browser storage.  They are stored in
 *   the owner's conversation history on the server, like any other message.
 */
(function () {
  "use strict";

  var api = window.OwnerAI;
  if (!api) {
    return;
  }

  var CONSENT_KEY = "ownerai-voice-consent";
  var SPEAK_KEY = "ownerai-voice-speak";
  var CONFIDENCE_THRESHOLD = 0.7;

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $$(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function readStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      /* storage may be disabled */
    }
  }

  var Voice = {
    recognition: null,
    recognitionSupported: false,
    synthesisSupported: false,
    consented: false,
    speakReplies: true,
    listening: false,
    language: "en-US",

    init: function () {
      var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      this.recognitionSupported = Boolean(Recognition);
      this.synthesisSupported = Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
      this.consented = readStorage(CONSENT_KEY) === "1";
      this.speakReplies = readStorage(SPEAK_KEY) !== "0";

      var consentButton = $("[data-voice-consent]");
      var micButton = $("[data-voice-mic]");
      var speakToggle = $("[data-voice-speak-toggle]");
      var status = $("[data-voice-status]");
      var notice = $("[data-voice-notice]");
      var unsupported = $("[data-voice-unsupported]");

      if (!this.recognitionSupported && unsupported) {
        unsupported.hidden = false;
      }
      if (notice) {
        notice.hidden = this.consented || !this.recognitionSupported;
      }
      if (consentButton) {
        consentButton.hidden = this.consented;
        consentButton.addEventListener("click", function () {
          Voice.consented = true;
          writeStorage(CONSENT_KEY, "1");
          consentButton.hidden = true;
          if (notice) {
            notice.hidden = true;
          }
          Voice.setStatus("Voice input is enabled. Use the microphone button to speak.");
          if (micButton) {
            micButton.disabled = false;
          }
        });
      }
      if (micButton) {
        micButton.disabled = !this.consented || !this.recognitionSupported;
        micButton.addEventListener("click", function () {
          Voice.toggleListening();
        });
      }
      if (speakToggle) {
        var speakToggles = $$("[data-voice-speak-toggle]");
        speakToggles.forEach(function (toggle) {
          if (toggle.type === "checkbox") {
            toggle.checked = this.speakReplies;
          } else {
            toggle.setAttribute("aria-pressed", this.speakReplies ? "true" : "false");
          }
          toggle.addEventListener("click", function (event) {
            if (toggle.type === "checkbox") {
              Voice.speakReplies = toggle.checked;
            } else {
              event.preventDefault();
              Voice.speakReplies = !Voice.speakReplies;
              toggle.setAttribute("aria-pressed", Voice.speakReplies ? "true" : "false");
            }
            writeStorage(SPEAK_KEY, Voice.speakReplies ? "1" : "0");
            speakToggles.forEach(function (other) {
              if (other === toggle) {
                return;
              }
              if (other.type === "checkbox") {
                other.checked = Voice.speakReplies;
              } else {
                other.setAttribute("aria-pressed", Voice.speakReplies ? "true" : "false");
              }
            });
            if (!Voice.speakReplies) {
              Voice.stopSpeaking();
            }
          });
        }, this);
      }
      this.setStatus(
        this.consented
          ? "Voice input is enabled."
          : "Voice input is disabled until you enable it."
      );
    },

    setStatus: function (message) {
      var status = $("[data-voice-status]");
      if (status) {
        status.textContent = message || "";
      }
      api.announce(message);
    },

    toggleListening: function () {
      if (this.listening) {
        this.stopListening();
        return;
      }
      this.startListening();
    },

    startListening: function () {
      if (!this.recognitionSupported || !this.consented) {
        return;
      }
      var self = this;
      var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!this.recognition) {
        this.recognition = new Recognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.maxAlternatives = 1;
      }
      this.recognition.lang = this.language;
      this.recognition.onstart = function () {
        self.listening = true;
        self.setMicState(true);
        self.setStatus("Listening… speak now.");
      };
      this.recognition.onresult = function (event) {
        var result = null;
        for (var i = event.results.length - 1; i >= 0; i -= 1) {
          if (event.results[i].isFinal) {
            result = event.results[i][0];
            break;
          }
        }
        if (!result) {
          return;
        }
        self.handleTranscript(result.transcript, result.confidence);
      };
      this.recognition.onerror = function (event) {
        self.listening = false;
        self.setMicState(false);
        self.setStatus(self.describeError(event.error));
      };
      this.recognition.onend = function () {
        self.listening = false;
        self.setMicState(false);
      };
      try {
        this.recognition.start();
        this.stopSpeaking();
      } catch (error) {
        this.setStatus("The microphone could not be started.");
      }
    },

    stopListening: function () {
      if (this.recognition) {
        try {
          this.recognition.stop();
        } catch (error) {
          /* already stopped */
        }
      }
      this.listening = false;
      this.setMicState(false);
    },

    setMicState: function (active) {
      var micButton = $("[data-voice-mic]");
      if (micButton) {
        micButton.setAttribute("aria-pressed", active ? "true" : "false");
        micButton.classList.toggle("is-listening", active);
        micButton.setAttribute(
          "aria-label",
          active ? "Stop listening" : "Start voice input"
        );
      }
      var panel = $("[data-voice-panel]");
      if (panel) {
        panel.classList.toggle("is-listening", active);
      }
    },

    describeError: function (code) {
      if (code === "not-allowed" || code === "service-not-allowed") {
        return "The microphone is blocked. Allow microphone access for this site and try again.";
      }
      if (code === "no-speech") {
        return "I did not hear anything. Please try again.";
      }
      if (code === "audio-capture") {
        return "No microphone was found.";
      }
      if (code === "network") {
        return "The speech service could not be reached.";
      }
      if (code === "aborted") {
        return "Voice input was stopped.";
      }
      return "Voice input failed (" + code + ").";
    },

    handleTranscript: function (transcript, confidence) {
      var text = (transcript || "").trim();
      if (!text) {
        this.setStatus("I did not catch that. Please try again.");
        return;
      }
      var input = $("[data-chat-input]");
      if (input) {
        input.value = text;
      }
      var certain = typeof confidence === "number" && confidence >= CONFIDENCE_THRESHOLD;
      if (certain) {
        this.setStatus("Heard: " + text);
        this.submitCommand(text);
        return;
      }
      this.setStatus(
        "Heard: “" + text + "”. Please check the text and press send, or speak again."
      );
      if (input) {
        input.focus();
      }
    },

    submitCommand: function (text) {
      var self = this;
      var input = $("[data-chat-input]");
      if (input) {
        input.value = "";
      }
      this.speak("Working on it");
      api.apiFetch("/api/voice/command", {
        method: "POST",
        body: JSON.stringify({ text: text, language: this.language })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The command failed."));
            }
            self.handleCommand(body, text);
          });
        })
        .catch(function (error) {
          self.setStatus(error.message || "The command failed.");
        });
    },

    handleCommand: function (body, transcript) {
      var answer = body.answer || "";
      if (body.client_resolved) {
        answer = this.resolveLocally(body, answer);
      }
      this.appendToChat(transcript, answer);
      if (body.speak !== false) {
        this.speak(answer);
      }
      this.setStatus("Answer: " + answer);
    },

    resolveLocally: function (body, fallback) {
      var action = body.action || {};
      if (action.type === "set_theme" && api.setTheme) {
        api.setTheme(action.theme);
        return "The " + action.theme + " theme is active.";
      }
      if (action.type === "describe_appearance") {
        var theme = api.currentTheme ? api.currentTheme() : "light";
        var colour = this.backgroundColour();
        return (
          "The current theme is " + theme + " and the background colour is " + colour + "."
        );
      }
      if (action.type === "navigate" && action.url) {
        window.location.href = action.url;
        return "Opening the " + action.url.replace("/", "").replace("-", " ") + ".";
      }
      if (action.type === "scroll_top") {
        var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
        return "Back at the top of the page.";
      }
      if (action.type === "stop_speaking") {
        this.stopSpeaking();
        return "Stopped.";
      }
      return fallback;
    },

    backgroundColour: function () {
      var styles = window.getComputedStyle(document.body);
      var colour = styles.backgroundColor || "";
      var match = /rgba?\((\d+),\s*(\d+),\s*(\d+)/.exec(colour);
      if (match) {
        return (
          "rgb(" + match[1] + ", " + match[2] + ", " + match[3] + ")"
        );
      }
      return colour || "unknown";
    },

    appendToChat: function (question, answer) {
      var log = $("[data-chat-log]");
      if (!log) {
        return;
      }
      var user = document.createElement("div");
      user.className = "chat-message user";
      var userWho = document.createElement("span");
      userWho.className = "who";
      userWho.textContent = "You (voice)";
      var userText = document.createElement("span");
      userText.textContent = question;
      user.appendChild(userWho);
      user.appendChild(userText);
      log.appendChild(user);

      var bot = document.createElement("div");
      bot.className = "chat-message assistant";
      var botWho = document.createElement("span");
      botWho.className = "who";
      botWho.textContent = "Assistant";
      var botText = document.createElement("span");
      botText.textContent = answer;
      bot.appendChild(botWho);
      bot.appendChild(botText);
      log.appendChild(bot);
      log.scrollTop = log.scrollHeight;
    },

    speak: function (text) {
      if (!this.synthesisSupported || !this.speakReplies || !text) {
        return;
      }
      try {
        window.speechSynthesis.cancel();
        var utterance = new window.SpeechSynthesisUtterance(text);
        utterance.lang = this.language;
        utterance.rate = 1;
        utterance.pitch = 1;
        var voices = window.speechSynthesis.getVoices() || [];
        for (var i = 0; i < voices.length; i += 1) {
          if (voices[i].lang && voices[i].lang.indexOf(this.language.split("-")[0]) === 0) {
            utterance.voice = voices[i];
            break;
          }
        }
        window.speechSynthesis.speak(utterance);
      } catch (error) {
        /* speech synthesis is a progressive enhancement */
      }
    },

    stopSpeaking: function () {
      if (this.synthesisSupported) {
        try {
          window.speechSynthesis.cancel();
        } catch (error) {
          /* ignore */
        }
      }
    }
  };

  window.OwnerAIVoice = Voice;

  document.addEventListener("DOMContentLoaded", function () {
    if (document.body.dataset.owneraiVoiceReady === "1") {
      return;
    }
    document.body.dataset.owneraiVoiceReady = "1";
    Voice.init();
  });
})();
