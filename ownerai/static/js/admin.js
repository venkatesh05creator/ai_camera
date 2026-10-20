/* Administration console behaviour. */
(function () {
  "use strict";

  var api = window.OwnerAI;
  if (!api) {
    return;
  }

  function $(selector, root) {
    return (root || document).querySelector(selector);
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
    return isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }

  function renderUsers(users) {
    var table = $("[data-users-table]");
    var body = $("[data-users-body]");
    var status = $("[data-panel-status='users']");
    if (!body) {
      return;
    }
    clear(body);
    if (status) {
      status.hidden = true;
    }
    if (table) {
      table.hidden = false;
    }
    users.forEach(function (user) {
      var row = document.createElement("tr");
      var nameCell = document.createElement("td");
      var mail = document.createElement("strong");
      mail.textContent = user.email;
      var role = document.createElement("div");
      role.className = "small muted";
      role.textContent = user.display_name || "no display name";
      nameCell.appendChild(mail);
      nameCell.appendChild(role);
      row.appendChild(nameCell);

      var roleCell = document.createElement("td");
      roleCell.textContent = user.role;
      row.appendChild(roleCell);

      var statusCell = document.createElement("td");
      var badge = document.createElement("span");
      badge.className = "status status-" + (user.email_verified ? "active" : "paused");
      badge.textContent = user.email_verified ? "verified" : "unverified";
      statusCell.appendChild(badge);
      row.appendChild(statusCell);

      var actionCell = document.createElement("td");
      var select = document.createElement("select");
      select.setAttribute("aria-label", "Role for " + user.email);
      ["owner", "admin", "trusted", "viewer"].forEach(function (value) {
        var option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === user.role) {
          option.selected = true;
        }
        select.appendChild(option);
      });
      var save = document.createElement("button");
      save.type = "button";
      save.className = "button button-small";
      save.textContent = "Apply";
      save.addEventListener("click", function () {
        save.disabled = true;
        api.apiFetch("/api/admin/users/" + user.id + "/role", {
          method: "PATCH",
          body: JSON.stringify({ role: select.value })
        })
          .then(function (response) {
            return api.readJson(response).then(function (body) {
              if (!response.ok) {
                throw new Error(api.describeError(body, "The role could not be changed."));
              }
              loadUsers();
            });
          })
          .catch(function (error) {
            window.alert(error.message || "The role could not be changed.");
          })
          .finally(function () {
            save.disabled = false;
          });
      });
      actionCell.appendChild(select);
      actionCell.appendChild(save);
      row.appendChild(actionCell);
      body.appendChild(row);
    });
  }

  function loadUsers() {
    return api.apiFetch("/api/admin/users?limit=50")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The accounts could not be loaded."));
          }
          renderUsers(body);
        });
      })
      .catch(function (error) {
        var box = $("[data-users-error]");
        api.setStatus(box, error.message || "The accounts could not be loaded.", true);
      });
  }

  function renderAudit(entries) {
    var table = $("[data-audit-table]");
    var body = $("[data-audit-body]");
    var status = $("[data-panel-status='audit']");
    if (!body) {
      return;
    }
    clear(body);
    if (status) {
      status.hidden = true;
    }
    if (table) {
      table.hidden = false;
    }
    entries.forEach(function (entry) {
      var row = document.createElement("tr");
      [formatDate(entry.created_at), entry.action, entry.target_type + " " + entry.target_id, entry.outcome].forEach(
        function (value) {
          var cell = document.createElement("td");
          cell.textContent = value || "";
          row.appendChild(cell);
        }
      );
      body.appendChild(row);
    });
  }

  function loadAudit() {
    return api.apiFetch("/api/admin/audit?limit=50")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The audit log could not be loaded."));
          }
          renderAudit(body);
        });
      })
      .catch(function (error) {
        var status = $("[data-panel-status='audit']");
        if (status) {
          status.textContent = error.message;
        }
      });
  }

  function renderContacts(messages) {
    var list = $("[data-contacts-list]");
    var empty = $("[data-contacts-empty]");
    var status = $("[data-panel-status='contacts']");
    if (!list) {
      return;
    }
    clear(list);
    if (status) {
      status.hidden = true;
    }
    if (!messages.length) {
      if (empty) {
        empty.hidden = false;
      }
      return;
    }
    if (empty) {
      empty.hidden = true;
    }
    messages.forEach(function (message) {
      var item = document.createElement("li");
      item.className = "identity-item";
      var title = document.createElement("strong");
      title.textContent = message.subject;
      var who = document.createElement("div");
      who.className = "small muted";
      who.textContent = message.email + " · " + formatDate(message.created_at) + " · " + message.status;
      var body = document.createElement("div");
      body.textContent = message.message;
      item.appendChild(title);
      item.appendChild(who);
      item.appendChild(body);
      list.appendChild(item);
    });
  }

  function loadContacts() {
    return api.apiFetch("/api/admin/contacts?limit=25")
      .then(function (response) {
        return api.readJson(response).then(function (body) {
          if (!response.ok) {
            throw new Error(api.describeError(body, "The messages could not be loaded."));
          }
          renderContacts(body);
        });
      })
      .catch(function (error) {
        var status = $("[data-panel-status='contacts']");
        if (status) {
          status.textContent = error.message;
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadUsers();
    loadAudit();
    loadContacts();
  });
})();
