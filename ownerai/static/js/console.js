/* Operations console behaviour: navigation, live feed, telemetry, activity feed.
 *
 * Everything shown here is real: the frame rate is measured in the browser,
 * the people counter and the confidence come from the server's face pipeline
 * and the activity feed is the owner's own event history.  No raw frame is
 * ever stored - the browser only sends single frames for analysis.
 */
(function () {
  "use strict";

  var api = window.OwnerAI;
  if (!api) {
    return;
  }

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $$(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function clear(node) {
    while (node && node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  var Console = {
    devices: [],
    events: [],
    stream: null,
    running: false,
    paused: false,
    recording: false,
    recordTimer: null,
    recordStart: 0,
    frames: 0,
    fps: 0,
    lastFpsAt: 0,
    analyseTimer: null,

    /* ---------------------------------------------------------- navigation */
    initTabs: function () {
      var buttons = $$("[data-console-tab]");
      buttons.forEach(function (button) {
        button.addEventListener("click", function () {
          var target = button.getAttribute("data-console-tab");
          Console.showTab(target);
        });
      });
      var openers = $$("[data-console-open-copilot], [data-console-open-panel], [data-console-show-events]");
      openers.forEach(function (button) {
        button.addEventListener("click", function () {
          var target = button.getAttribute("data-console-open-copilot")
            ? "copilot"
            : button.getAttribute("data-console-show-events")
              ? "events"
              : "copilot";
          Console.showTab(target);
        });
      });
    },

    showTab: function (name) {
      $$("[data-console-tab]").forEach(function (button) {
        button.setAttribute("aria-selected", button.getAttribute("data-console-tab") === name ? "true" : "false");
      });
      $$(".con-pane").forEach(function (pane) {
        pane.classList.toggle("active", pane.id === "pane-" + name);
      });
      var titles = {
        monitoring: ["Live Camera Operations", "Real-time multi-camera monitoring, motion and detection overlays"],
        copilot: ["Voice Copilot & Commands", "Speak to your assistant - deterministic commands, privacy first"],
        people: ["People Directory", "Consented biometric profiles of this installation"],
        events: ["Events & Alerts", "Everything your cameras recorded"],
        devices: ["Camera Devices", "Webcams, phones, wearables and IP cameras"],
        settings: ["Settings & Audit", "Account security, sessions and audit trail"]
      };
      var title = $(".con-title h1");
      var subtitle = $(".con-title p");
      if (title && titles[name]) {
        title.textContent = titles[name][0];
        subtitle.textContent = titles[name][1];
      }
    },

    /* --------------------------------------------------------------- clock */
    initClock: function () {
      var chip = $("[data-console-clock]");
      function tick() {
        if (!chip) {
          return;
        }
        var now = new Date();
        var pad = function (value) {
          return String(value).padStart(2, "0");
        };
        var days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        var months = [
          "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ];
        chip.textContent =
          days[now.getUTCDay()] + ", " + pad(now.getUTCDate()) + " " +
          months[now.getUTCMonth()] + " " + now.getUTCFullYear() + " " +
          pad(now.getUTCHours()) + ":" + pad(now.getUTCMinutes()) + ":" + pad(now.getUTCSeconds()) + " UTC";
      }
      tick();
      window.setInterval(tick, 1000);
    },

    /* ----------------------------------------------------------- live feed */
    initFeed: function () {
      var start = $("[data-console-pause]");
      if (start) {
        start.addEventListener("click", function () {
          Console.toggleFeed();
        });
      }
      var snapshot = $("[data-console-snapshot]");
      if (snapshot) {
        snapshot.addEventListener("click", function () {
          Console.capture("note", "Snapshot taken from the live feed");
        });
      }
      var record = $("[data-console-record]");
      if (record) {
        record.addEventListener("click", function () {
          Console.toggleRecord();
        });
      }
      var enroll = $("[data-console-enroll]");
      if (enroll) {
        enroll.addEventListener("click", function () {
          Console.quickEnroll();
        });
      }
      var voice = $("[data-console-voice]");
      if (voice) {
        voice.addEventListener("click", function () {
          var voiceApi = window.OwnerAIVoice;
          if (!voiceApi) {
            return;
          }
          if (!voiceApi.consented) {
            Console.showTab("copilot");
            var consent = $("[data-voice-consent]");
            if (consent) {
              consent.focus();
            }
            voiceApi.setStatus("Please enable voice input in the copilot panel first.");
            return;
          }
          voiceApi.toggleListening();
        });
      }
      var stop = $("[data-console-voice-stop]");
      if (stop) {
        stop.addEventListener("click", function () {
          if (window.OwnerAIVoice) {
            window.OwnerAIVoice.stopSpeaking();
          }
        });
      }
    },

    startFeed: function () {
      var video = $("[data-live-video]");
      var empty = $("[data-viewer-empty]");
      if (!video || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        Console.setLiveText("Live feed unavailable in this browser");
        return;
      }
      navigator.mediaDevices
        .getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false })
        .then(function (stream) {
          Console.stream = stream;
          video.srcObject = stream;
          Console.running = true;
          Console.paused = false;
          if (empty) {
            empty.hidden = true;
          }
          var button = $("[data-console-pause]");
          if (button) {
            button.textContent = "Pause";
          }
          Console.setLiveText("Live");
          Console.startFpsCounter(video);
          Console.startAnalysis();
          Console.updateMeta();
        })
        .catch(function (error) {
          var message =
            error && error.name === "NotAllowedError"
              ? "Camera permission denied - allow the camera to start the live feed."
              : "The camera could not be started.";
          Console.setLiveText(message);
          var empty = $("[data-viewer-empty]");
          if (empty) {
            empty.hidden = false;
            var strong = $("strong", empty);
            if (strong) {
              strong.textContent = message;
            }
          }
        });
    },

    toggleFeed: function () {
      if (!this.running) {
        this.startFeed();
        return;
      }
      this.paused = !this.paused;
      var video = $("[data-live-video]");
      var button = $("[data-console-pause]");
      if (this.paused) {
        if (video) {
          video.pause();
        }
        if (this.stream) {
          this.stream.getTracks().forEach(function (track) {
            track.enabled = false;
          });
        }
        this.setLiveText("Paused");
        if (button) {
          button.textContent = "Resume";
        }
      } else {
        if (video) {
          video.play();
        }
        if (this.stream) {
          this.stream.getTracks().forEach(function (track) {
            track.enabled = true;
          });
        }
        this.setLiveText("Live");
        if (button) {
          button.textContent = "Pause";
        }
      }
    },

    setLiveText: function (text) {
      var element = $("[data-pill-live-text]");
      if (element) {
        element.textContent = text;
      }
    },

    startFpsCounter: function (video) {
      this.frames = 0;
      this.lastFpsAt = performance.now();
      var self = this;
      var count = function () {
        self.frames += 1;
        var now = performance.now();
        var elapsed = now - self.lastFpsAt;
        if (elapsed >= 1000) {
          self.fps = (self.frames * 1000) / elapsed;
          self.frames = 0;
          self.lastFpsAt = now;
          var tile = $("[data-telemetry='fps']");
          if (tile) {
            tile.textContent = self.fps.toFixed(1) + " FPS";
          }
        }
        if (self.running) {
          window.requestAnimationFrame(count);
        }
      };
      window.requestAnimationFrame(count);
    },

    updateMeta: function () {
      var video = $("[data-live-video]");
      var meta = $("[data-viewer-meta]");
      if (!meta) {
        return;
      }
      var device = Console.devices[0];
      var name = device ? device.name : "Browser camera";
      var resolution = "1280x720";
      if (video && video.videoWidth) {
        resolution = video.videoWidth + "x" + video.videoHeight;
      }
      meta.textContent = name + " (" + resolution + ")";
      var chip = $("[data-stage-device-name]");
      var typeChip = $("[data-stage-device-type]");
      if (chip) {
        chip.textContent = name;
      }
      if (typeChip) {
        typeChip.textContent = device ? device.device_type : "webcam";
      }
    },

    /* ----------------------------------------------------------- analysis */
    startAnalysis: function () {
      var self = this;
      this.stopAnalysis();
      this.analyseTimer = window.setInterval(function () {
        self.analyseFrame(false);
      }, 3000);
      this.analyseFrame(true);
    },

    stopAnalysis: function () {
      if (this.analyseTimer) {
        window.clearInterval(this.analyseTimer);
        this.analyseTimer = null;
      }
    },

    captureFrame: function () {
      var video = $("[data-live-video]");
      if (!video || !video.videoWidth) {
        return null;
      }
      var canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      var context = canvas.getContext("2d");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      return { canvas: canvas, context: context, dataUrl: canvas.toDataURL("image/jpeg", 0.7) };
    },

    analyseFrame: function (force) {
      var self = this;
      var frame = this.captureFrame();
      if (!frame) {
        return;
      }
      this.updateLighting(frame.context, frame.canvas);
      if (!force && !this.recording) {
        // The periodic analysis keeps the telemetry tiles fresh.
      }
      api.apiFetch("/api/vision/analyse", {
        method: "POST",
        body: JSON.stringify({ image: frame.dataUrl })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The frame could not be analysed."));
            }
            self.applyAnalysis(body);
          });
        })
        .catch(function () {
          var pill = $("[data-pill-ai-state]");
          if (pill) {
            pill.textContent = "Unavailable";
          }
        });
    },

    applyAnalysis: function (analysis) {
      var people = $("[data-telemetry='people']");
      if (people) {
        people.textContent = analysis.faces + (analysis.faces === 1 ? " Person" : " People");
      }
      var confidence = $("[data-telemetry='confidence']");
      if (confidence) {
        confidence.textContent =
          analysis.confidence === null || analysis.confidence === undefined
            ? "--.-%"
            : (analysis.confidence * 100).toFixed(1) + "%";
      }
      var state = $("[data-pill-ai-state]");
      if (state) {
        state.textContent = analysis.faces > 0 ? "On" : "Idle";
      }
      var engine = $("[data-engine-info]");
      if (engine && analysis.engine) {
        engine.textContent = "Engine: " + analysis.engine;
      }
    },

    updateLighting: function (context, canvas) {
      try {
        var sample = document.createElement("canvas");
        sample.width = 32;
        sample.height = 32;
        var sampleContext = sample.getContext("2d");
        sampleContext.drawImage(canvas, 0, 0, 32, 32);
        var data = sampleContext.getImageData(0, 0, 32, 32).data;
        var total = 0;
        for (var i = 0; i < data.length; i += 4) {
          total += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
        }
        var luminance = total / (data.length / 4);
        var label = luminance > 170 ? "Bright" : luminance > 70 ? "Balanced ambient" : "Low light";
        var tile = $("[data-telemetry='lighting']");
        if (tile) {
          tile.textContent = label;
        }
      } catch (error) {
        /* the canvas may be tainted - ignore */
      }
    },

    /* ---------------------------------------------------------- recording */
    toggleRecord: function () {
      var self = this;
      var button = $("[data-console-record]");
      var pill = $("[data-pill-rec]");
      if (this.recording) {
        this.recording = false;
        if (this.recordTimer) {
          window.clearInterval(this.recordTimer);
          this.recordTimer = null;
        }
        if (pill) {
          pill.hidden = true;
        }
        if (button) {
          button.textContent = "Start Smooth Record";
        }
        this.setStatus("Recording stopped.");
        return;
      }
      if (!this.running) {
        this.startFeed();
        return;
      }
      this.recording = true;
      this.recordStart = Date.now();
      if (pill) {
        pill.hidden = false;
      }
      if (button) {
        button.textContent = "Stop Recording";
      }
      this.recordTimer = window.setInterval(function () {
        self.capture("motion", "Smooth record frame");
      }, 2000);
      this.setStatus("Recording started - only event metadata is stored, never the frames.");
    },

    capture: function (kind, summary) {
      var self = this;
      var frame = this.captureFrame();
      if (!frame) {
        this.setStatus("No frame available - start the live feed first.");
        return;
      }
      var device = this.devices[0];
      var deviceId = device ? device.id : null;
      if (!deviceId) {
        this.setStatus("Register a camera first so the event can be attributed.");
        return;
      }
      api.apiFetch("/api/vision/analyse", {
        method: "POST",
        body: JSON.stringify({ image: frame.dataUrl })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The frame could not be analysed."));
            }
            var detail =
              body.faces > 0
                ? body.owner_match
                  ? body.label + " matched (confidence " + (body.confidence * 100).toFixed(0) + "%)"
                  : body.faces + " face(s) detected - kept anonymous"
                : "no face detected";
            return api.apiFetch("/api/devices/" + deviceId + "/events", {
              method: "POST",
              body: JSON.stringify({
                kind: kind,
                summary: summary + " - " + detail,
                confidence: body.confidence === null ? 0 : body.confidence
              })
            });
          });
        })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The event could not be stored."));
            }
            self.setStatus("Event recorded.");
            Console.loadEvents();
          });
        })
        .catch(function (error) {
          self.setStatus(error.message || "The event could not be stored.");
        });
    },

    quickEnroll: function () {
      var self = this;
      var frame = this.captureFrame();
      if (!frame) {
        this.setStatus("No frame available - start the live feed first.");
        return;
      }
      var consent = $("[data-identity-consent]");
      if (!consent || !consent.checked) {
        this.showTab("people");
        this.setStatus("Please give explicit consent in the People Directory before enrolling.");
        if (consent) {
          consent.focus();
        }
        return;
      }
      var label = $("[data-identity-label]");
      var name = label && label.value ? label.value.trim() : "Owner";
      this.setStatus("Enrolling " + name + " from the live feed…");
      api.apiFetch("/api/identities", {
        method: "POST",
        body: JSON.stringify({ label: name, consent: true, images: [frame.dataUrl] })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The enrolment failed."));
            }
            self.setStatus("Enrolled " + body.label + " - the template is encrypted at rest.");
            if (window.dashboardReloadIdentities) {
              window.dashboardReloadIdentities();
            }
          });
        })
        .catch(function (error) {
          self.setStatus(error.message || "The enrolment failed.");
        });
    },

    setStatus: function (message) {
      var element = $("[data-voice-status]");
      if (element) {
        element.textContent = message;
      }
      api.announce(message);
    },

    /* ------------------------------------------------------- devices/events */
    loadDevices: function () {
      return api.apiFetch("/api/devices")
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The cameras could not be loaded."));
            }
            Console.devices = body;
            var online = body.filter(function (device) {
              return device.status === "active";
            }).length;
            var onlineChip = $("[data-online-count]");
            if (onlineChip) {
              onlineChip.textContent = String(online);
            }
            var plural = $("[data-online-plural]");
            if (plural) {
              plural.textContent = online === 1 ? "" : "s";
            }
            var count = $("[data-devices-count]");
            if (count) {
              count.textContent = body.length + " registered";
            }
            var counter = $("[data-count='devices']");
            if (counter) {
              counter.textContent = String(body.length);
            }
            Console.updateMeta();
            return body;
          });
        })
        .catch(function () {
          /* the panel keeps its placeholder */
        });
    },

    loadEvents: function () {
      return api.apiFetch("/api/events?limit=20")
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The events could not be loaded."));
            }
            Console.events = body;
            Console.renderActivity(body);
            var badge = $("[data-badge-events]");
            if (badge) {
              badge.textContent = String(body.length);
            }
            var alerts = $("[data-alert-count]");
            if (alerts) {
              alerts.textContent = String(
                body.filter(function (event) {
                  return event.kind === "alert";
                }).length
              );
            }
            var counter = $("[data-count='events']");
            if (counter) {
              counter.textContent = String(body.length);
            }
            var label = $("[data-events-count]");
            if (label) {
              label.textContent = body.length + " events";
            }
          });
        })
        .catch(function () {
          /* ignore */
        });
    },

    renderActivity: function (events) {
      var feed = $("[data-activity-feed]");
      if (!feed) {
        return;
      }
      clear(feed);
      if (!events.length) {
        var empty = document.createElement("div");
        empty.className = "con-empty";
        empty.textContent = "No activity yet.";
        feed.appendChild(empty);
        return;
      }
      events.forEach(function (event) {
        var item = document.createElement("div");
        item.className = "con-activity-item";
        var tag = document.createElement("span");
        tag.className = "con-tag" + (event.kind === "person" ? " owner" : "");
        tag.textContent = event.kind === "person" ? "Enrolled" : "Anonymous";
        var body = document.createElement("div");
        body.className = "body";
        var title = document.createElement("div");
        title.className = "title";
        title.textContent = event.summary || event.kind;
        var meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent =
          Math.round(event.confidence * 100) + "% • " + (event.device_name || "camera");
        body.appendChild(title);
        body.appendChild(meta);
        var time = document.createElement("span");
        time.className = "time";
        var date = new Date(event.occurred_at);
        time.textContent = isNaN(date.getTime())
          ? ""
          : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        item.appendChild(tag);
        item.appendChild(body);
        item.appendChild(time);
        feed.appendChild(item);
      });
    },

    /* --------------------------------------------------------- console search */
    initSearch: function () {
      var input = $("[data-console-search]");
      var results = $("[data-console-search-results]");
      if (!input || !results) {
        return;
      }
      var timer = null;
      input.addEventListener("input", function () {
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
          var query = input.value.trim();
          clear(results);
          if (query.length < 2) {
            return;
          }
          api.apiFetch("/api/search?q=" + encodeURIComponent(query))
            .then(function (response) {
              return api.readJson(response).then(function (body) {
                (body.hits || []).forEach(function (hit) {
                  var item = document.createElement("li");
                  item.className = "con-activity-item";
                  var tag = document.createElement("span");
                  tag.className = "con-tag";
                  tag.textContent = hit.type;
                  var bodyNode = document.createElement("div");
                  bodyNode.className = "body";
                  var title = document.createElement("div");
                  title.className = "title";
                  title.textContent = hit.title;
                  var meta = document.createElement("div");
                  meta.className = "meta";
                  meta.textContent = hit.snippet || "";
                  bodyNode.appendChild(title);
                  bodyNode.appendChild(meta);
                  item.appendChild(tag);
                  item.appendChild(bodyNode);
                  results.appendChild(item);
                });
              });
            })
            .catch(function () {
              clear(results);
            });
        }, 250);
      });
    }
  };

  window.OwnerAIConsole = Console;

  document.addEventListener("DOMContentLoaded", function () {
    if (document.body.dataset.owneraiConsoleReady === "1") {
      return;
    }
    document.body.dataset.owneraiConsoleReady = "1";
    Console.initTabs();
    Console.initClock();
    Console.initFeed();
    Console.initSearch();
    Console.loadDevices();
    Console.loadEvents();
    window.setInterval(Console.loadEvents, 20000);
  });
})();
