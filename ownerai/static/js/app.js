/* Owner-Only AI Camera Assistant - shared front-end behaviour.
 *
 * No inline scripts, no third-party resources, no tracking.  The only state
 * kept in the browser is the theme preference and the cookie consent choice,
 * neither of which contains personal information.
 */
(function () {
  "use strict";

  var THEME_KEY = "ownerai-theme";
  var CONSENT_COOKIE = "ownerai_consent";
  // The session cookie is HttpOnly and therefore never read by the front-end.
  var CSRF_COOKIE = "ownerai_csrf";

  /* ------------------------------------------------------------ helpers */
  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $$(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function readCookie(name) {
    var parts = document.cookie ? document.cookie.split(";") : [];
    for (var i = 0; i < parts.length; i += 1) {
      var pair = parts[i].trim();
      if (pair.indexOf(name + "=") === 0) {
        return decodeURIComponent(pair.slice(name.length + 1));
      }
    }
    return "";
  }

  function writeCookie(name, value, days) {
    var maxAge = Math.round(days * 24 * 60 * 60);
    var secure = window.location.protocol === "https:" ? "; Secure" : "";
    document.cookie = name + "=" + encodeURIComponent(value) + "; path=/; max-age=" + maxAge +
      "; SameSite=Lax" + secure;
  }

  function announce(message) {
    var region = $("[data-live-region]");
    if (region) {
      region.textContent = message;
    }
  }

  function apiFetch(url, options) {
    var opts = options || {};
    var headers = opts.headers || {};
    var method = (opts.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      var token = readCookie(CSRF_COOKIE);
      if (token) {
        headers["X-CSRF-Token"] = token;
      }
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    opts.headers = headers;
    opts.credentials = "same-origin";
    return fetch(url, opts);
  }

  function readJson(response) {
    return response.json().catch(function () {
      return {};
    });
  }

  function describeError(payload, fallback) {
    if (!payload) {
      return fallback;
    }
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (payload.detail && typeof payload.detail === "object") {
      var parts = [];
      Object.keys(payload.detail).forEach(function (key) {
        var value = payload.detail[key];
        if (Array.isArray(value)) {
          parts.push(value.join(", "));
        } else {
          parts.push(String(value));
        }
      });
      if (parts.length) {
        return parts.join(" ");
      }
    }
    if (payload.details && Array.isArray(payload.details)) {
      return payload.details
        .map(function (item) {
          return item.field ? item.field + ": " + item.message : item.message;
        })
        .join("; ");
    }
    return fallback;
  }

  function setStatus(element, message, isError) {
    if (!element) {
      return;
    }
    if (!message) {
      element.hidden = true;
      element.textContent = "";
      element.classList.remove("alert-error");
      return;
    }
    element.hidden = false;
    element.textContent = message;
    element.classList.toggle("alert-error", Boolean(isError));
  }

  /* -------------------------------------------------------------- theme */
  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === "light" || theme === "dark") {
      root.setAttribute("data-theme", theme);
    } else {
      root.removeAttribute("data-theme");
    }
    var toggle = $("[data-theme-toggle]");
    if (toggle) {
      var isDark = theme === "dark" ||
        (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      toggle.setAttribute("aria-pressed", isDark ? "true" : "false");
      toggle.setAttribute("aria-label", isDark ? "Switch to the light theme" : "Switch to the dark theme");
      var icon = $("[data-theme-icon]", toggle);
      if (icon) {
        icon.textContent = isDark ? "☀" : "☾";
      }
    }
  }

  function currentTheme() {
    var stored = document.documentElement.getAttribute("data-theme");
    if (stored) {
      return stored;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function setTheme(theme) {
    if (theme !== "light" && theme !== "dark") {
      return;
    }
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch (error) {
      /* storage may be disabled - the theme still works for this page */
    }
    applyTheme(theme);
  }

  function initTheme() {
    var stored = null;
    try {
      stored = window.localStorage.getItem(THEME_KEY);
    } catch (error) {
      stored = null;
    }
    // Pages may request a different default (the console is dark by default).
    var pageDefault = document.body ? document.body.dataset.defaultTheme : "";
    applyTheme(stored || pageDefault || "system");

    var toggle = $("[data-theme-toggle]");
    if (!toggle) {
      return;
    }
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      setTheme(next);
      announce(next === "dark" ? "Dark theme enabled" : "Light theme enabled");
    });
  }

  /* ----------------------------------------------------- cookie consent */
  function initCookieBanner() {
    var banner = $("[data-cookie-banner]");
    if (!banner) {
      return;
    }
    var choice = readCookie(CONSENT_COOKIE);
    if (choice) {
      banner.hidden = true;
      return;
    }
    banner.hidden = false;

    var detail = $("[data-cookie-detail]");
    var settingsButton = $("[data-cookie-settings]");
    if (settingsButton && detail) {
      settingsButton.addEventListener("click", function () {
        var expanded = settingsButton.getAttribute("aria-expanded") === "true";
        settingsButton.setAttribute("aria-expanded", expanded ? "false" : "true");
        detail.hidden = expanded;
      });
    }

    function decide(value) {
      writeCookie(CONSENT_COOKIE, value, 180);
      banner.hidden = true;
      announce(value === "accepted" ? "Cookie preferences saved" : "Essential cookies only");
    }

    var accept = $("[data-cookie-accept]");
    if (accept) {
      accept.addEventListener("click", function () {
        decide("accepted");
      });
    }
    var reject = $("[data-cookie-reject]");
    if (reject) {
      reject.addEventListener("click", function () {
        decide("essential");
      });
    }
  }

  /* ------------------------------------------------------- back to top */
  function initBackToTop() {
    var button = $("[data-back-to-top]");
    if (!button) {
      return;
    }
    var ticking = false;
    function update() {
      var offset = window.scrollY || document.documentElement.scrollTop || 0;
      if (offset > 400) {
        button.hidden = false;
        button.classList.add("visible");
      } else {
        button.classList.remove("visible");
        button.hidden = true;
      }
      ticking = false;
    }
    window.addEventListener(
      "scroll",
      function () {
        if (!ticking) {
          window.requestAnimationFrame(update);
          ticking = true;
        }
      },
      { passive: true }
    );
    button.addEventListener("click", function () {
      var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
      var main = $("#main");
      if (main) {
        main.focus({ preventScroll: true });
      }
      announce("Back at the top of the page");
    });
    update();
  }

  /* --------------------------------------------------------- navigation */
  function initNav() {
    var toggle = $("[data-nav-toggle]");
    var nav = $("#primary-nav");
    if (!toggle || !nav) {
      return;
    }
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", open ? "false" : "true");
      nav.classList.toggle("open", !open);
    });
  }

  /* ------------------------------------------------------ contact dialog */
  function initContact() {
    var dialog = $("[data-contact-dialog]");
    if (!dialog) {
      return;
    }
    var form = $("[data-contact-form]");
    var status = $("[data-contact-status]");
    var openButtons = $$("[data-contact-open]");
    var closeButton = $("[data-contact-close]");

    openButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        if (typeof dialog.showModal === "function") {
          dialog.showModal();
        } else {
          dialog.setAttribute("open", "");
        }
        setStatus(status, "", false);
      });
    });

    if (closeButton) {
      closeButton.addEventListener("click", function () {
        if (typeof dialog.close === "function") {
          dialog.close();
        } else {
          dialog.removeAttribute("open");
        }
      });
    }

    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) {
        dialog.close();
      }
    });

    if (!form) {
      return;
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var submit = $("[data-contact-submit]", form);
      var payload = {
        email: form.elements.email.value.trim(),
        subject: form.elements.subject.value.trim(),
        message: form.elements.message.value.trim(),
        website: form.elements.website ? form.elements.website.value : ""
      };
      if (submit) {
        submit.disabled = true;
      }
      setStatus(status, "Sending…", false);
      apiFetch("/api/contact", { method: "POST", body: JSON.stringify(payload) })
        .then(function (response) {
          return readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(describeError(body, "The message could not be sent."));
            }
            form.reset();
            setStatus(status, body.message || "Thank you - your message has been received.", false);
            announce("Your message was sent");
          });
        })
        .catch(function (error) {
          setStatus(status, error.message || "The message could not be sent.", true);
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
          }
        });
    });
  }

  /* -------------------------------------------------------------- search */
  function initSearch() {
    var form = $("[data-search-form]");
    var input = $("[data-search-input]");
    var results = $("[data-search-results]");
    if (!form || !input || !results) {
      return;
    }
    var timer = null;
    var lastQuery = "";

    function hide() {
      results.hidden = true;
      results.innerHTML = "";
    }

    function render(hits, query) {
      results.innerHTML = "";
      if (!hits.length) {
        var empty = document.createElement("li");
        empty.className = "search-empty";
        empty.textContent = 'No results for "' + query + '".';
        results.appendChild(empty);
        results.hidden = false;
        return;
      }
      hits.slice(0, 12).forEach(function (hit) {
        var item = document.createElement("li");
        var link = document.createElement("a");
        link.href = hit.url;
        var type = document.createElement("span");
        type.className = "hit-type";
        type.textContent = hit.type;
        var title = document.createElement("strong");
        title.textContent = hit.title;
        var snippet = document.createElement("span");
        snippet.className = "hit-snippet";
        snippet.textContent = hit.snippet || "";
        link.appendChild(type);
        link.appendChild(document.createElement("br"));
        link.appendChild(title);
        link.appendChild(snippet);
        item.appendChild(link);
        results.appendChild(item);
      });
      results.hidden = false;
    }

    function run() {
      var query = input.value.trim();
      if (query.length < 2) {
        hide();
        return;
      }
      if (query === lastQuery) {
        return;
      }
      lastQuery = query;
      apiFetch("/api/search?q=" + encodeURIComponent(query))
        .then(function (response) {
          return readJson(response).then(function (body) {
            render(body.hits || [], query);
          });
        })
        .catch(function () {
          hide();
        });
    }

    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(run, 250);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hide();
        input.blur();
      }
    });

    form.addEventListener("submit", function (event) {
      var query = input.value.trim();
      if (!query) {
        event.preventDefault();
        return;
      }
      if (window.location.pathname === "/dashboard") {
        event.preventDefault();
        window.location.href = "/dashboard?q=" + encodeURIComponent(query);
      }
    });

    document.addEventListener("click", function (event) {
      if (!form.contains(event.target)) {
        hide();
      }
    });
  }

  /* --------------------------------------------------------- sign out */
  function initLogout() {
    var button = $("[data-logout]");
    if (!button) {
      return;
    }
    button.addEventListener("click", function () {
      button.disabled = true;
      apiFetch("/api/auth/logout", { method: "POST" })
        .then(function () {
          window.location.href = "/";
        })
        .catch(function () {
          button.disabled = false;
        });
    });
  }

  /* ------------------------------------------------------ auth forms */
  function initAuthForms() {
    var form = $("[data-auth-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-auth-error]", form);
    var statusBox = $("[data-auth-status]", form);
    var submit = $("[data-auth-submit]", form);
    var mode = form.getAttribute("data-auth-mode");

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(errorBox, "", false);
      setStatus(statusBox, "", false);
      var payload = {
        email: form.elements.email.value.trim(),
        password: form.elements.password.value
      };
      if (mode === "register") {
        payload.display_name = form.elements.display_name ? form.elements.display_name.value.trim() : "";
      }
      if (submit) {
        submit.disabled = true;
      }
      var url = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      apiFetch(url, { method: "POST", body: JSON.stringify(payload) })
        .then(function (response) {
          return readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(describeError(body, "The request failed."));
            }
            if (body.mfa_required) {
              setStatus(statusBox, "Enter the code from your authenticator app to finish signing in.", false);
              window.location.href = "/dashboard?mfa=required";
              return;
            }
            window.location.href = "/dashboard";
          });
        })
        .catch(function (error) {
          setStatus(errorBox, error.message || "The request failed.", true);
        })
        .finally(function () {
          if (submit) {
            submit.disabled = false;
          }
        });
    });
  }

  function initForgotForm() {
    var form = $("[data-forgot-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-forgot-error]", form);
    var statusBox = $("[data-forgot-status]", form);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(errorBox, "", false);
      apiFetch("/api/auth/password/forgot", {
        method: "POST",
        body: JSON.stringify({ email: form.elements.email.value.trim() })
      })
        .then(function (response) {
          return readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(describeError(body, "The request failed."));
            }
            setStatus(statusBox, body.message || "If that account exists, a reset link has been sent.", false);
          });
        })
        .catch(function (error) {
          setStatus(errorBox, error.message || "The request failed.", true);
        });
    });
  }

  function initResetForm() {
    var form = $("[data-reset-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-reset-error]", form);
    var statusBox = $("[data-reset-status]", form);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(errorBox, "", false);
      apiFetch("/api/auth/password/reset", {
        method: "POST",
        body: JSON.stringify({
          token: form.elements.token.value,
          password: form.elements.password.value
        })
      })
        .then(function (response) {
          return readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(describeError(body, "The request failed."));
            }
            setStatus(statusBox, "Your password was changed. You can sign in now.", false);
            window.setTimeout(function () {
              window.location.href = "/login";
            }, 1200);
          });
        })
        .catch(function (error) {
          setStatus(errorBox, error.message || "The request failed.", true);
        });
    });
  }

  function initVerifyForm() {
    var form = $("[data-verify-form]");
    if (!form) {
      return;
    }
    var errorBox = $("[data-verify-error]", form);
    var statusBox = $("[data-verify-status]", form);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setStatus(errorBox, "", false);
      apiFetch("/api/auth/email/verify", {
        method: "POST",
        body: JSON.stringify({ token: form.elements.token.value })
      })
        .then(function (response) {
          return readJson(response).then(function (body) {
            if (!response.ok) {
              throw new Error(describeError(body, "The confirmation failed."));
            }
            setStatus(statusBox, "Your address is confirmed.", false);
          });
        })
        .catch(function (error) {
          setStatus(errorBox, error.message || "The confirmation failed.", true);
        });
    });
  }

  /* ------------------------------------------------------------- boot */
  // The shared helpers are published immediately (not only on DOMContentLoaded)
  // so that other scripts - for example the voice interface - can rely on
  // them regardless of the order in which the deferred scripts run.
  window.OwnerAI = {
    apiFetch: apiFetch,
    readJson: readJson,
    describeError: describeError,
    setStatus: setStatus,
    announce: announce,
    applyTheme: applyTheme,
    setTheme: setTheme,
    currentTheme: currentTheme
  };

  document.addEventListener("DOMContentLoaded", function () {
    // Guard against a second initialisation (e.g. a synthetic event) - the
    // listeners below would otherwise be bound twice and every toggle would
    // be applied twice.
    if (document.body.dataset.owneraiReady === "1") {
      return;
    }
    document.body.dataset.owneraiReady = "1";
    initTheme();
    initCookieBanner();
    initBackToTop();
    initNav();
    initContact();
    initSearch();
    initLogout();
    initAuthForms();
    initForgotForm();
    initResetForm();
    initVerifyForm();
    window.OwnerAI = {
      apiFetch: apiFetch,
      readJson: readJson,
      describeError: describeError,
      setStatus: setStatus,
      announce: announce,
      applyTheme: applyTheme,
      setTheme: setTheme,
      currentTheme: currentTheme
    };
  });
})();
