/* Dashboard behaviour: cameras, events, identities, assistant and security. */
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

  function formatDate(value) {
    if (!value) {
      return "";
    }
    var date = new Date(value);
    if (isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString();
  }

  /* ------------------------------------------------------------ devices */
  function renderDevices(devices) {
    var table = $("[data-devices-table]");
    var body = $("[data-devices-body]");
    var empty = $("[data-devices-empty]");
    var status = $("[data-panel-status='devices']");
    if (!body) {
      return;
    }
    clear(body);
    if (status) {
      status.hidden = true;
    }
    if (!devices.length) {
      if (table) {
        table.hidden = true;
      }
      if (empty) {
        empty.hidden = false;
      }
      return;
    }
    if (table) {
      table.hidden = false;
    }
    if (empty) {
      empty.hidden = true;
    }

    devices.forEach(function (device) {
      var row = document.createElement("tr");
      row.id = "device-" + device.id;

      var name = document.createElement("td");
      var label = document.createElement("strong");
      label.textContent = device.name;
      name.appendChild(label);
      if (device.location_label) {
        var where = document.createElement("div");
        where.className = "small muted";
        where.textContent = device.location_label;
        name.appendChild(where);
      }
      row.appendChild(name);

      var type = document.createElement("td");
      type.textContent = device.device_type;
      row.appendChild(type);

      var statusCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "status status-" + device.status;
      badge.textContent = device.status;
      statusCell.appendChild(badge);
      row.appendChild(statusCell);

      var actions = document.createElement("td");
      var deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "button button-danger button-small";
      deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", function () {
        if (!window.confirm("Delete “" + device.name + "” and its events?")) {
          return;
        }
        api.apiFetch("/api/devices/" + device.id, { method: "DELETE" }).then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              window.alert(api.describeError(body, "The camera could not be deleted."));
              return;
            }
            loadDevices();
            loadEvents();
          });
        });
      });
      actions.appendChild(deleteButton);

      if (device.has_stream_url) {
        var snapshot = document.createElement("button");
        snapshot.type = "button";
        snapshot.className = "button button-secondary button-small";
        snapshot.textContent = "Snapshot";
        snapshot.addEventListener("click", function () {
          window.open("/api/devices/" + device.id + "/snapshot", "_blank", "noopener");
        });
        actions.appendChild(snapshot);
      }
      row.appendChild(actions);
      body.appendChild(row);
    });
  }

  function loadDevices() {
    return api.apiFetch("/api/devices")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The cameras could not be loaded."));
          }
          renderDevices(body);
          return body;
        });
      })
      .then(function (devices) {
        var select = $("[data-event-device]");
        if (select) {
          var current = select.value;
          clear(select);
          devices.forEach(function (device) {
            var option = document.createElement("option");
            option.value = String(device.id);
            option.textContent = device.name;
            select.appendChild(option);
          });
          if (current) {
            select.value = current;
          }
        }
      })
      .catch(function (error) {
        var status = $("[data-panel-status='devices']");
        if (status) {
          status.textContent = error.message;
        }
      });
  }

  function initDeviceForm() {
    var form = $("[data-device-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-device-error]");
    var submit = $("[data-device-submit]");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      var payload = {
        name: form.elements.name.value.trim(),
        device_type: form.elements.device_type.value,
        location_label: form.elements.location_label.value.trim(),
        stream_url: form.elements.stream_url.value.trim() || null
      };
      if (submit) {
        submit.disabled = true;
      }
      api.apiFetch("/api/devices", { method: "POST", body: JSON.stringify(payload) })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The camera could not be added."));
            }
            form.reset();
            loadDevices();
            loadEvents();
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "The camera could not be added.", true);
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
          }
        });
    });
  }

  /* ------------------------------------------------------------- events */
  function renderEvents(events) {
    var list = $("[data-events-list]");
    var empty = $("[data-events-empty]");
    var status = $("[data-panel-status='events']");
    if (!list) {
      return;
    }
    clear(list);
    if (status) {
      status.hidden = true;
    }
    if (!events.length) {
      if (empty) {
        empty.hidden = false;
      }
      return;
    }
    if (empty) {
      empty.hidden = true;
    }
    events.forEach(function (event) {
      var item = document.createElement("li");
      item.className = "event-item";
      item.id = "event-" + event.id;
      var title = document.createElement("strong");
      title.textContent = event.kind + " · " + (event.device_name || "");
      var summary = document.createElement("div");
      summary.textContent = event.summary || "No summary";
      var meta = document.createElement("div");
      meta.className = "event-meta";
      meta.textContent = formatDate(event.occurred_at) + " · confidence " + event.confidence.toFixed(2);
      item.appendChild(title);
      item.appendChild(summary);
      item.appendChild(meta);
      list.appendChild(item);
    });
  }

  function loadEvents() {
    return api.apiFetch("/api/events?limit=20")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The events could not be loaded."));
          }
          renderEvents(body);
          var counter = $("[data-count='events']");
          if (counter) {
            counter.textContent = String(body.length);
          }
        });
      })
      .catch(function (error) {
        var status = $("[data-panel-status='events']");
        if (status) {
          status.textContent = error.message;
        }
      });
  }

  function initEventForm() {
    var form = $("[data-event-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-event-error]");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      var deviceId = form.elements.device_id.value;
      if (!deviceId) {
        api.setStatus(errorBox, "Register a camera first.", true);
        return;
      }
      var payload = {
        kind: form.elements.kind.value,
        summary: form.elements.summary.value.trim(),
        confidence: 0.5
      };
      api.apiFetch("/api/devices/" + deviceId + "/events", {
        method: "POST",
        body: JSON.stringify(payload)
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The event could not be recorded."));
            }
            form.reset();
            loadEvents();
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "The event could not be recorded.", true);
        });
    });
  }

  /* --------------------------------------------------------- identities */
  function renderIdentities(identities) {
    var list = $("[data-identities-list]");
    var empty = $("[data-identities-empty]");
    var status = $("[data-panel-status='identities']");
    if (!list) {
      return;
    }
    clear(list);
    if (status) {
      status.hidden = true;
    }
    if (!identities.length) {
      if (empty) {
        empty.hidden = false;
      }
      return;
    }
    if (empty) {
      empty.hidden = true;
    }
    identities.forEach(function (identity) {
      var item = document.createElement("li");
      item.className = "identity-item";
      item.id = "identity-" + identity.id;
      var title = document.createElement("strong");
      title.textContent = identity.label;
      var meta = document.createElement("div");
      meta.className = "small muted";
      meta.textContent =
        "consented " + formatDate(identity.consent_at) +
        (identity.withdrawn_at ? " · withdrawn" : "") +
        (identity.expires_at ? " · expires " + formatDate(identity.expires_at) : "");
      var withdraw = document.createElement("button");
      withdraw.type = "button";
      withdraw.className = "button button-danger button-small";
      withdraw.textContent = "Withdraw";
      withdraw.addEventListener("click", function () {
        if (!window.confirm("Withdraw consent and delete the template of “" + identity.label + "”?")) {
          return;
        }
        api.apiFetch("/api/identities/" + identity.id, { method: "DELETE" }).then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              window.alert(api.describeError(body, "The template could not be deleted."));
              return;
            }
            loadIdentities();
          });
        });
      });
      item.appendChild(title);
      item.appendChild(meta);
      item.appendChild(withdraw);
      list.appendChild(item);
    });
  }

  function loadIdentities() {
    return api.apiFetch("/api/identities")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The identities could not be loaded."));
          }
          renderIdentities(body);
        });
      })
      .catch(function (error) {
        var status = $("[data-panel-status='identities']");
        if (status) {
          status.textContent = error.message;
        }
      });
  }

  function readFileAsDataUrl(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        resolve(reader.result);
      };
      reader.onerror = function () {
        reject(new Error("The image could not be read."));
      };
      reader.readAsDataURL(file);
    });
  }

  function initIdentityForm() {
    var form = $("[data-identity-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-identity-error]");
    var submit = $("[data-identity-submit]");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      var consent = $("[data-identity-consent]");
      if (!consent || !consent.checked) {
        api.setStatus(errorBox, "Please give explicit consent before enrolling.", true);
        return;
      }
      var input = $("[data-identity-images]");
      var files = input && input.files ? Array.prototype.slice.call(input.files) : [];
      if (!files.length) {
        api.setStatus(errorBox, "Please choose at least one picture.", true);
        return;
      }
      if (files.length > 5) {
        api.setStatus(errorBox, "At most five pictures can be enrolled at once.", true);
        return;
      }
      Promise.all(files.map(readFileAsDataUrl))
        .then(function (images) {
          return api.apiFetch("/api/identities", {
            method: "POST",
            body: JSON.stringify({
              label: form.elements.label.value.trim(),
              consent: true,
              images: images
            })
          });
        })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The identity could not be enrolled."));
            }
            form.reset();
            loadIdentities();
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "The identity could not be enrolled.", true);
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
          }
        });
    });
  }

  /* ----------------------------------------------------------- assistant */
  function appendMessage(role, text) {
    var log = $("[data-chat-log]");
    if (!log) {
      return;
    }
    var bubble = document.createElement("div");
    bubble.className = "chat-message " + role;
    var who = document.createElement("span");
    who.className = "who";
    who.textContent = role === "user" ? "You" : "Assistant";
    var body = document.createElement("span");
    body.textContent = text;
    bubble.appendChild(who);
    bubble.appendChild(body);
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
  }

  function renderActions(actions) {
    var list = $("[data-chat-actions]");
    if (!list) {
      return;
    }
    clear(list);
    (actions || []).forEach(function (action) {
      var item = document.createElement("li");
      item.className = "identity-item";
      var text = document.createElement("div");
      text.textContent = action.message || "An action needs your confirmation.";
      var confirmButton = document.createElement("button");
      confirmButton.type = "button";
      confirmButton.className = "button button-small";
      confirmButton.textContent = "Confirm";
      confirmButton.addEventListener("click", function () {
        confirmButton.disabled = true;
        api.apiFetch("/api/chat/tools/" + encodeURIComponent(action.tool), {
          method: "POST",
          body: JSON.stringify({ arguments: action.arguments || {}, confirmed: true })
        })
          .then(function (response) {
            return api.readJson(response).then(function (body) {
              if (!response.ok) {
                throw new Error(api.describeError(body, "The action failed."));
              }
              item.remove();
              loadDevices();
            });
          })
          .catch(function (error) {
            confirmButton.disabled = false;
            window.alert(error.message || "The action failed.");
          });
      });
      item.appendChild(text);
      item.appendChild(confirmButton);
      list.appendChild(item);
    });
  }

  function initChat() {
    var form = $("[data-chat-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-chat-error]");
    var submit = $("[data-chat-submit]");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      var input = form.elements.message;
      var message = input.value.trim();
      if (!message) {
        return;
      }
      appendMessage("user", message);
      input.value = "";
      if (submit) {
        submit.disabled = true;
      }
      api.apiFetch("/api/chat", { method: "POST", body: JSON.stringify({ message: message }) })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The assistant is unavailable."));
            }
            appendMessage("assistant", body.reply);
            renderActions(body.pending_actions);
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "The assistant is unavailable.", true);
          appendMessage("assistant", "I could not answer that request.");
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
          }
        });
    });
  }

  /* ------------------------------------------------------------ security */
  function initPasswordForm() {
    var form = $("[data-password-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-password-error]");
    var statusBox = $("[data-password-status]");
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      api.setStatus(statusBox, "", false);
      api.apiFetch("/api/auth/password/change", {
        method: "POST",
        body: JSON.stringify({
          current_password: form.elements.current_password.value,
          new_password: form.elements.new_password.value
        })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "The password could not be changed."));
            }
            form.reset();
            api.setStatus(statusBox, "Your password was changed. Other sessions were signed out.", false);
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "The password could not be changed.", true);
        });
    });
  }

  function loadSessions() {
    var list = $("[data-sessions-list]");
    if (!list) {
      return;
    }
    api.apiFetch("/api/auth/sessions")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            return;
          }
          clear(list);
          body.forEach(function (session) {
            var item = document.createElement("li");
            item.className = "identity-item";
            var title = document.createElement("strong");
            title.textContent = formatDate(session.created_at);
            var meta = document.createElement("div");
            meta.className = "small muted";
            meta.textContent = "Last used " + formatDate(session.last_seen_at) +
              " · expires " + formatDate(session.expires_at) +
              " · " + (session.user_agent || "unknown client");
            var revoke = document.createElement("button");
            revoke.type = "button";
            revoke.className = "button button-secondary button-small";
            revoke.textContent = "Sign out this session";
            revoke.addEventListener("click", function () {
              api.apiFetch("/api/auth/sessions/" + session.id, { method: "DELETE" }).then(function () {
                loadSessions();
              });
            });
            item.appendChild(title);
            item.appendChild(meta);
            item.appendChild(revoke);
            list.appendChild(item);
          });
        });
      })
      .catch(function () {
        /* the panel simply stays empty */
      });
  }

  function initMfa() {
    var form = $("[data-mfa-form]");
    var setupButton = $("[data-mfa-setup]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-mfa-error]");
    var statusBox = $("[data-mfa-status]");
    if (setupButton) {
      setupButton.addEventListener("click", function () {
        api.setStatus(errorBox, "", false);
        api.apiFetch("/api/auth/mfa/setup", { method: "POST" })
          .then(function (response) {
            return api.readJson(response).then(function (body) {
              if (!response.ok) {
                throw new Error(api.describeError(body, "The secret could not be generated."));
              }
              api.setStatus(
                statusBox,
                "Add this secret to your authenticator app, then enter the code below: " + body.secret,
                false
              );
            });
          })
          .catch(function (error) {
            api.setStatus(errorBox, error.message || "The secret could not be generated.", true);
          });
      });
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      api.setStatus(errorBox, "", false);
      api.setStatus(statusBox, "", false);
      api.apiFetch("/api/auth/mfa/enable", {
        method: "POST",
        body: JSON.stringify({ code: form.elements.code.value.trim() })
      })
        .then(function (response) {
          return api.readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(api.describeError(body, "Two-factor authentication could not be enabled."));
            }
            form.reset();
            api.setStatus(
              statusBox,
              "Two-factor authentication is enabled. Backup codes: " + (body.backup_codes || []).join(", "),
              false
            );
          });
        })
        .catch(function (error) {
          api.setStatus(errorBox, error.message || "Two-factor authentication could not be enabled.", true);
        });
    });
  }

  /* -------------------------------------------------------------- boot */
  document.addEventListener("DOMContentLoaded", function () {
    initDeviceForm();
    initEventForm();
    initIdentityForm();
    initChat();
    initPasswordForm();
    initMfa();
    loadDevices();
    loadEvents();
    loadIdentities();
    loadSessions();
    window.setInterval(loadEvents, 30000);
  });
})();
