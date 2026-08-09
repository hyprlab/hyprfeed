/* Hyprfeed client. No dependencies. */
(function () {
  "use strict";

  var CSRF = (document.querySelector('meta[name="csrf"]') || {}).content || "";
  var root = document.documentElement;

  function api(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF": CSRF },
      body: JSON.stringify(body || {})
    }).then(function (resp) {
      return resp.json().then(function (data) {
        if (!resp.ok) {
          var err = new Error(data.error || "Something went wrong.");
          err.canScrape = !!data.can_scrape;
          err.googleNews = data.google_news || null;
          throw err;
        }
        return data;
      });
    });
  }

  var toastTimer, toastLeaveTimer;
  function dismissToast(el) {
    if (el.hidden) return;
    el.classList.add("is-leaving");
    clearTimeout(toastLeaveTimer);
    toastLeaveTimer = setTimeout(function () {
      el.hidden = true;
      el.classList.remove("is-leaving");
    }, 260);
  }
  function toast(message, actionLabel, actionFn) {
    var el = document.getElementById("toast");
    if (!el) return;
    clearTimeout(toastTimer);
    clearTimeout(toastLeaveTimer);
    el.classList.remove("is-leaving");
    el.textContent = message;
    if (actionLabel) {
      var action = document.createElement("button");
      action.className = "toast-action";
      action.textContent = actionLabel;
      action.addEventListener("click", function () {
        clearTimeout(toastTimer);
        dismissToast(el);
        actionFn();
      });
      el.appendChild(action);
    }
    el.hidden = false;
    toastTimer = setTimeout(function () { dismissToast(el); }, actionLabel ? 3500 : 2600);
  }

  /* ————— Theme ————— */
  var media = window.matchMedia("(prefers-color-scheme: dark)");
  function applyTheme(pref) {
    root.setAttribute("data-theme-pref", pref);
    root.setAttribute("data-theme", pref === "system" ? (media.matches ? "dark" : "light") : pref);
  }
  media.addEventListener("change", function () {
    if (root.getAttribute("data-theme-pref") === "system") applyTheme("system");
  });

  var themeBtn = document.getElementById("theme-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      applyTheme(next);
      var radio = document.querySelector('input[name="theme"][value="' + next + '"]');
      if (radio) radio.checked = true;
      api("/settings", { theme: next }).catch(function () {});
    });
  }
  document.querySelectorAll('input[name="theme"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      applyTheme(radio.value);
      api("/settings", { theme: radio.value }).catch(function () {});
    });
  });

  /* ————— Sidebar (mobile) ————— */
  var sidebar = document.getElementById("sidebar");
  var scrim = document.querySelector(".scrim");
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (scrim) scrim.hidden = !open;
  }
  document.querySelectorAll("[data-open-sidebar]").forEach(function (el) {
    el.addEventListener("click", function () { setSidebar(true); });
  });
  document.querySelectorAll("[data-close-sidebar]").forEach(function (el) {
    el.addEventListener("click", function () { setSidebar(false); });
  });

  /* ————— Modals ————— */
  function switchSettingsTab(name) {
    document.querySelectorAll(".tab").forEach(function (t) {
      var active = t.getAttribute("data-tab") === name;
      t.classList.toggle("is-active", active);
      if (active && t.scrollIntoView) {
        t.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
      }
    });
    document.querySelectorAll(".tabpane").forEach(function (pane) {
      pane.classList.toggle("is-active", pane.getAttribute("data-pane") === name);
    });
  }

  var tabsBar = document.querySelector(".settings-tabs");
  function updateTabFades() {
    if (!tabsBar) return;
    var max = tabsBar.scrollWidth - tabsBar.clientWidth;
    tabsBar.classList.toggle("can-scroll-left", tabsBar.scrollLeft > 2);
    tabsBar.classList.toggle("can-scroll-right", max - tabsBar.scrollLeft > 2);
  }
  if (tabsBar) {
    tabsBar.addEventListener("scroll", updateTabFades, { passive: true });
    window.addEventListener("resize", updateTabFades);
  }

  document.querySelectorAll("[data-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var dialog = document.getElementById(btn.getAttribute("data-open"));
      if (!dialog) return;
      var tab = btn.getAttribute("data-tab-target");
      if (tab) switchSettingsTab(tab);
      dialog.showModal();
      if (dialog.id === "settings-modal") updateTabFades();
    });
  });
  document.querySelectorAll("dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (e) {
      if (e.target === dialog) dialog.close(); // backdrop click
    });
    dialog.querySelectorAll("[data-close]").forEach(function (btn) {
      btn.addEventListener("click", function () { dialog.close(); });
    });
  });

  /* ————— Settings: tabs & preferences ————— */
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      switchSettingsTab(tab.getAttribute("data-tab"));
    });
  });
  document.querySelectorAll('input[name="view_mode"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      api("/settings", { view_mode: radio.value }).then(function () { toast("Default view saved"); }).catch(function () {});
    });
  });
  var markRead = document.getElementById("mark-read-open");
  if (markRead) {
    markRead.addEventListener("change", function () {
      api("/settings", { mark_read_on_open: markRead.checked }).catch(function () {});
    });
  }

  var acctName = document.getElementById("acct-name");
  if (acctName) {
    acctName.addEventListener("change", function () {
      var value = acctName.value.trim();
      api("/settings", { name: value }).then(function () {
        toast("Name saved");
        var nameEl = document.getElementById("user-name");
        var emailEl = document.getElementById("user-email");
        var avatar = document.getElementById("user-avatar");
        var email = (emailEl && emailEl.textContent) || (nameEl && nameEl.textContent) || "";
        if (nameEl) nameEl.textContent = value || email;
        if (avatar) avatar.textContent = (value || email).charAt(0).toUpperCase();
        if (emailEl) emailEl.hidden = !value;
      }).catch(function (err) { toast(err.message); });
    });
  }

  var passwordForm = document.getElementById("password-form");
  if (passwordForm) {
    passwordForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("pw-error");
      errEl.hidden = true;
      api("/account/password", {
        current: document.getElementById("pw-current").value,
        new: document.getElementById("pw-new").value
      }).then(function () {
        passwordForm.reset();
        toast("Password updated");
      }).catch(function (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      });
    });
  }

  /* ————— Manage feeds ————— */
  document.querySelectorAll(".manage-item").forEach(function (item) {
    var feedId = item.getAttribute("data-feed");
    var renameBtn = item.querySelector("[data-rename]");
    var unsubBtn = item.querySelector("[data-unsub]");
    if (renameBtn) {
      renameBtn.addEventListener("click", function () {
        var current = item.querySelector(".manage-title").textContent;
        var title = prompt("Feed name (leave empty to restore the original):", current);
        if (title === null) return;
        api("/feeds/" + feedId + "/rename", { title: title }).then(function (data) {
          item.querySelector(".manage-title").textContent = data.title;
          toast("Renamed");
        }).catch(function (err) { toast(err.message); });
      });
    }
    if (unsubBtn) {
      unsubBtn.addEventListener("click", function () {
        var name = item.querySelector(".manage-title").textContent;
        if (!confirm('Unfollow "' + name + '"?')) return;
        api("/feeds/" + feedId + "/unsubscribe").then(function () {
          location.href = "/";
        }).catch(function (err) { toast(err.message); });
      });
    }
  });

  /* ————— Admin ————— */
  var regOpen = document.getElementById("reg-open");
  if (regOpen) {
    regOpen.addEventListener("change", function () {
      api("/admin/registration", { open: regOpen.checked }).then(function (data) {
        toast(data.open ? "Registration is open" : "Registration is closed");
      }).catch(function (err) { toast(err.message); });
    });
  }
  [["inst-refresh", "refresh_minutes", "Refresh interval saved"],
   ["inst-retention", "max_entries_per_feed", "Retention saved"]].forEach(function (spec) {
    var input = document.getElementById(spec[0]);
    if (!input) return;
    input.addEventListener("change", function () {
      var body = {};
      body[spec[1]] = parseInt(input.value, 10);
      api("/admin/instance", body)
        .then(function () { toast(spec[2]); })
        .catch(function (err) { toast(err.message); });
    });
  });
  var adduserForm = document.getElementById("admin-adduser");
  if (adduserForm) {
    adduserForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var errEl = document.getElementById("au-error");
      errEl.hidden = true;
      api("/admin/users", {
        name: document.getElementById("au-name").value.trim(),
        username: document.getElementById("au-email").value.trim(),
        password: document.getElementById("au-password").value,
        is_admin: document.getElementById("au-admin").checked
      }).then(function () {
        toast("User created");
        setTimeout(function () { location.reload(); }, 600);
      }).catch(function (err) {
        errEl.textContent = err.message;
        errEl.hidden = false;
      });
    });
  }
  document.querySelectorAll(".manage-item[data-user]").forEach(function (item) {
    var userId = item.getAttribute("data-user");
    var username = item.getAttribute("data-username");
    var pwBtn = item.querySelector("[data-admin-password]");
    var toggleBtn = item.querySelector("[data-admin-toggle]");
    var deleteBtn = item.querySelector("[data-admin-delete]");
    if (pwBtn) {
      pwBtn.addEventListener("click", function () {
        var pw = prompt('New password for "' + username + '" (at least 8 characters):');
        if (pw === null) return;
        api("/admin/users/" + userId + "/password", { new: pw })
          .then(function () { toast("Password reset for " + username); })
          .catch(function (err) { toast(err.message); });
      });
    }
    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        api("/admin/users/" + userId + "/toggle-admin")
          .then(function (data) {
            toast(username + (data.is_admin ? " is now an admin" : " is no longer an admin"));
            setTimeout(function () { location.reload(); }, 700);
          })
          .catch(function (err) { toast(err.message); });
      });
    }
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function () {
        if (!confirm('Delete "' + username + '" and all their subscriptions? This cannot be undone.')) return;
        api("/admin/users/" + userId + "/delete")
          .then(function () {
            toast("Deleted " + username);
            setTimeout(function () { location.reload(); }, 700);
          })
          .catch(function (err) { toast(err.message); });
      });
    }
  });

  /* ————— Settings: groups, sort, drag organization ————— */
  var feedsManage = document.getElementById("feeds-manage");
  var organizeDirty = false;

  function collectLayout() {
    var layout = [];
    Array.prototype.forEach.call(feedsManage.children, function (el) {
      if (el.classList.contains("manage-group-wrap")) {
        var gid = parseInt(el.getAttribute("data-group"), 10);
        layout.push({ type: "group", id: gid });
        el.querySelectorAll(".manage-sublist > .manage-item").forEach(function (li) {
          layout.push({ type: "feed", id: parseInt(li.getAttribute("data-feed"), 10), group: gid });
        });
      } else if (el.hasAttribute("data-feed")) {
        layout.push({ type: "feed", id: parseInt(el.getAttribute("data-feed"), 10), group: null });
      }
    });
    return layout;
  }

  function refreshIndent() {
    feedsManage.querySelectorAll(":scope > .manage-item[data-feed]").forEach(function (li) {
      li.classList.remove("manage-item--in-group");
    });
    feedsManage.querySelectorAll(".manage-sublist .manage-item[data-feed]").forEach(function (li) {
      li.classList.add("manage-item--in-group");
    });
  }

  function saveOrganize() {
    api("/feeds/organize", { layout: collectLayout() })
      .then(function () { organizeDirty = true; toast("Layout saved"); })
      .catch(function (err) { toast(err.message); });
  }

  if (feedsManage) {
    var draggedItem = null;

    function clearDropTargets() {
      feedsManage.querySelectorAll(".is-drop-target").forEach(function (el) {
        el.classList.remove("is-drop-target");
      });
    }

    function bindDrag(li) {
      li.addEventListener("dragstart", function (e) {
        e.stopPropagation();   // a feed drag must not also start its group's drag
        draggedItem = li;
        li.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        try { e.dataTransfer.setData("text/plain", "drag"); } catch (_) {}
      });
      li.addEventListener("dragend", function () {
        li.classList.remove("is-dragging");
        clearDropTargets();
        draggedItem = null;
        refreshIndent();
        saveOrganize();
      });
    }
    feedsManage.querySelectorAll(":scope > .manage-item, :scope > .manage-group-wrap, .manage-sublist > .manage-item")
      .forEach(bindDrag);

    function midpointInsert(container, items, clientY) {
      var next = null;
      for (var i = 0; i < items.length; i++) {
        var rect = items[i].getBoundingClientRect();
        if (clientY < rect.top + rect.height / 2) { next = items[i]; break; }
      }
      if (next) container.insertBefore(draggedItem, next);
      else container.appendChild(draggedItem);
    }

    feedsManage.addEventListener("dragover", function (e) {
      if (!draggedItem) return;
      e.preventDefault();
      clearDropTargets();
      var draggingGroup = draggedItem.classList.contains("manage-group-wrap");
      var topItems = Array.prototype.filter.call(feedsManage.children, function (el) {
        return el !== draggedItem && !el.contains(draggedItem);
      });

      if (draggingGroup) {
        // Groups are sealed blocks: they only reorder among top-level items.
        // Nothing can fall in or out while moving one.
        midpointInsert(feedsManage, topItems, e.clientY);
        return;
      }

      // Dragging a feed: check whether the pointer is inside a group block.
      for (var w = 0; w < topItems.length; w++) {
        var wrap = topItems[w];
        if (!wrap.classList.contains("manage-group-wrap")) continue;
        var rect = wrap.getBoundingClientRect();
        if (e.clientY < rect.top || e.clientY > rect.bottom) continue;
        var head = wrap.querySelector(".manage-group");
        var headRect = head.getBoundingClientRect();
        var sublist = wrap.querySelector(".manage-sublist");
        if (e.clientY <= headRect.bottom) {
          // Over the header: file at the top of this group.
          head.classList.add("is-drop-target");
          sublist.insertBefore(draggedItem, sublist.firstChild);
        } else {
          // Within the group's body: position among its members.
          var members = Array.prototype.filter.call(
            sublist.children, function (el) { return el !== draggedItem; });
          midpointInsert(sublist, members, e.clientY);
        }
        refreshIndent();
        return;
      }

      // Outside any group: place among top-level items (ungrouped).
      midpointInsert(feedsManage, topItems, e.clientY);
      refreshIndent();
    });

    // Sort: alphabetize ungrouped feeds (in their slots) and each group's
    // members; group positions stay where they are.
    document.querySelectorAll("[data-sort]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dir = btn.getAttribute("data-sort") === "desc" ? -1 : 1;
        function cmp(a, b) {
          var ta = a.querySelector(".manage-title").textContent.trim().toLowerCase();
          var tb = b.querySelector(".manage-title").textContent.trim().toLowerCase();
          return ta < tb ? -dir : ta > tb ? dir : 0;
        }
        var order = Array.prototype.slice.call(feedsManage.children);
        var loose = order.filter(function (el) { return el.hasAttribute("data-feed"); }).sort(cmp);
        var looseIdx = 0;
        order.forEach(function (el) {
          feedsManage.appendChild(el.hasAttribute("data-feed") ? loose[looseIdx++] : el);
        });
        feedsManage.querySelectorAll(".manage-sublist").forEach(function (sublist) {
          Array.prototype.slice.call(sublist.children).sort(cmp).forEach(function (li) {
            sublist.appendChild(li);
          });
        });
        refreshIndent();
        saveOrganize();
      });
    });

    // Group actions: create / rename / delete reload into the same tab.
    function reloadToFeedsTab() {
      location.hash = "settings-reading";
      location.reload();
    }
    document.querySelectorAll("[data-grename]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var wrap = btn.closest(".manage-group-wrap");
        var name = prompt("Group name:", wrap.querySelector(".manage-title").textContent.trim());
        if (name === null || !name.trim()) return;
        api("/groups/" + wrap.getAttribute("data-group") + "/rename", { name: name.trim() })
          .then(reloadToFeedsTab).catch(function (err) { toast(err.message); });
      });
    });
    document.querySelectorAll("[data-gdelete]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var wrap = btn.closest(".manage-group-wrap");
        var name = wrap.querySelector(".manage-title").textContent.trim();
        if (!confirm('Delete the group "' + name + '"? Its feeds are kept, just ungrouped.')) return;
        api("/groups/" + wrap.getAttribute("data-group") + "/delete")
          .then(reloadToFeedsTab).catch(function (err) { toast(err.message); });
      });
    });
  }

  var groupCreate = document.getElementById("group-create");
  if (groupCreate) {
    groupCreate.addEventListener("click", function () {
      var name = prompt("Name for the new group:");
      if (name === null || !name.trim()) return;
      api("/groups", { name: name.trim() })
        .then(function () { location.hash = "settings-reading"; location.reload(); })
        .catch(function (err) { toast(err.message); });
    });
  }

  // Settings closes after drag changes -> refresh so the sidebar matches.
  var settingsModal = document.getElementById("settings-modal");
  if (settingsModal) {
    settingsModal.addEventListener("close", function () {
      if (organizeDirty) location.reload();
    });
  }
  // Reopen settings on the feeds tab after a group action reload.
  if (location.hash === "#settings-reading" && settingsModal) {
    history.replaceState(null, "", location.pathname + location.search);
    switchSettingsTab("reading");
    settingsModal.showModal();
  }

  /* ————— Sidebar: collapse/expand groups ————— */
  document.querySelectorAll(".grouphead").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var wrap = btn.closest(".sidebar-group");
      var collapsed = wrap.classList.toggle("is-collapsed");
      btn.setAttribute("aria-expanded", String(!collapsed));
      api("/groups/" + wrap.getAttribute("data-group") + "/collapse", { collapsed: collapsed })
        .catch(function () {});
    });
  });

  var feedsAddForm = document.getElementById("feeds-add-form");
  if (feedsAddForm) {
    var feedsScrape = document.getElementById("feeds-scrape");
    var feedsScrapeBtn = document.getElementById("feeds-scrape-btn");
    var feedsGn = document.getElementById("feeds-gn");
    var feedsGnBtn = document.getElementById("feeds-gn-btn");
    var feedsPendingUrl = null;
    var feedsGnInfo = null;

    function settingsAddFeed(payload, busyBtn) {
      var errEl = document.getElementById("feeds-add-error");
      errEl.hidden = true;
      feedsScrape.hidden = true;
      feedsGn.hidden = true;
      if (!payload.url) return;
      busyBtn.disabled = true;
      busyBtn.querySelector(".btn-label").hidden = true;
      busyBtn.querySelector(".btn-busy").hidden = false;
      api("/feeds/add", payload)
        .then(function (data) { location.href = data.redirect; })
        .catch(function (err) {
          errEl.textContent = err.message;
          errEl.hidden = false;
          if (err.canScrape && !payload.scrape) {
            feedsPendingUrl = payload.url;
            feedsScrape.hidden = false;
          }
          feedsGnInfo = err.googleNews;
          if (feedsGnInfo) {
            document.getElementById("feeds-gn-text").textContent = gnExplanation(feedsGnInfo);
            feedsGn.hidden = false;
          }
          busyBtn.disabled = false;
          busyBtn.querySelector(".btn-label").hidden = false;
          busyBtn.querySelector(".btn-busy").hidden = true;
        });
    }

    feedsAddForm.addEventListener("submit", function (e) {
      e.preventDefault();
      settingsAddFeed({ url: document.getElementById("feeds-add-url").value.trim() },
                      feedsAddForm.querySelector("button"));
    });
    document.getElementById("feeds-add-url").addEventListener("input", function () {
      feedsScrape.hidden = true;
      feedsGn.hidden = true;
    });
    feedsScrapeBtn.addEventListener("click", function () {
      if (feedsPendingUrl) settingsAddFeed({ url: feedsPendingUrl, scrape: true }, feedsScrapeBtn);
    });
    feedsGnBtn.addEventListener("click", function () {
      if (feedsGnInfo) settingsAddFeed({ url: feedsGnInfo.url, custom_title: feedsGnInfo.title }, feedsGnBtn);
    });
  }

  /* ————— OPML import ————— */
  var opmlBtn = document.getElementById("opml-import-btn");
  var opmlFile = document.getElementById("opml-file");
  if (opmlBtn && opmlFile) {
    opmlBtn.addEventListener("click", function () { opmlFile.click(); });
    opmlFile.addEventListener("change", function () {
      if (!opmlFile.files.length) return;
      var form = new FormData();
      form.append("opml", opmlFile.files[0]);
      opmlBtn.disabled = true;
      opmlBtn.querySelector(".btn-label").hidden = true;
      opmlBtn.querySelector(".btn-busy").hidden = false;
      fetch("/feeds/import", { method: "POST", headers: { "X-CSRF": CSRF }, body: form })
        .then(function (resp) { return resp.json().then(function (d) { if (!resp.ok) throw new Error(d.error || "Import failed."); return d; }); })
        .then(function (data) {
          toast("Imported " + data.added + " " + (data.added === 1 ? "feed" : "feeds")
                + (data.skipped ? " (" + data.skipped + " already followed)" : ""));
          setTimeout(function () { location.reload(); }, 900);
        })
        .catch(function (err) {
          toast(err.message);
          opmlBtn.disabled = false;
          opmlBtn.querySelector(".btn-label").hidden = false;
          opmlBtn.querySelector(".btn-busy").hidden = true;
          opmlFile.value = "";
        });
    });
  }

  /* ————— Add feed ————— */
  function gnExplanation(info) {
    return info.domain + " blocks automated readers, so Hyprfeed can't fetch it directly. "
      + "Google News publishes a public feed of " + info.domain
      + " stories — headlines link to the original articles.";
  }

  var addForm = document.getElementById("add-form");
  if (addForm) {
    var scrapeOffer = document.getElementById("scrape-offer");
    var scrapeBtn = document.getElementById("scrape-btn");
    var gnOffer = document.getElementById("gn-offer");
    var gnBtn = document.getElementById("gn-btn");
    var gnInfo = null;

    function setBusy(btn, busy) {
      btn.disabled = busy;
      btn.querySelector(".btn-label").hidden = busy;
      btn.querySelector(".btn-busy").hidden = !busy;
    }

    function submitAdd(payload, btn) {
      var errEl = document.getElementById("add-error");
      errEl.hidden = true;
      setBusy(btn, true);
      api("/feeds/add", payload)
        .then(function (data) { location.href = data.redirect; })
        .catch(function (err) {
          errEl.textContent = err.message;
          errEl.hidden = false;
          scrapeOffer.hidden = !(err.canScrape && !payload.scrape);
          gnInfo = err.googleNews;
          gnOffer.hidden = !gnInfo;
          if (gnInfo) document.getElementById("gn-text").textContent = gnExplanation(gnInfo);
          setBusy(btn, false);
        });
    }

    addForm.addEventListener("submit", function (e) {
      e.preventDefault();
      scrapeOffer.hidden = true;
      gnOffer.hidden = true;
      submitAdd({ url: document.getElementById("add-url").value }, addForm.querySelector('button[type="submit"]'));
    });
    scrapeBtn.addEventListener("click", function () {
      submitAdd({ url: document.getElementById("add-url").value, scrape: true }, scrapeBtn);
    });
    gnBtn.addEventListener("click", function () {
      if (gnInfo) submitAdd({ url: gnInfo.url, custom_title: gnInfo.title }, gnBtn);
    });
    document.getElementById("add-url").addEventListener("input", function () {
      scrapeOffer.hidden = true;
      gnOffer.hidden = true;
    });
  }

  /* ————— Filter menu ————— */
  var filterMenu = document.getElementById("filter-menu");
  if (filterMenu) {
    var filterBtn = document.getElementById("filter-btn");
    var filterPop = filterMenu.querySelector(".filterpop");
    function setFilterOpen(open) {
      filterMenu.classList.toggle("is-open", open);
      filterBtn.setAttribute("aria-expanded", String(open));
      filterPop.hidden = !open;
    }
    filterBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      setFilterOpen(filterPop.hidden);
    });
    document.addEventListener("click", function (e) {
      if (!filterMenu.contains(e.target)) setFilterOpen(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !filterPop.hidden) setFilterOpen(false);
    });
  }

  /* ————— Topbar actions ————— */
  var refreshBtn = document.getElementById("refresh-btn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      refreshBtn.classList.add("is-busy");
      api("/refresh").then(function (data) {
        toast(data.new ? data.new + " new " + (data.new === 1 ? "story" : "stories") : "You're up to date");
        setTimeout(function () { location.reload(); }, data.new ? 700 : 1200);
      }).catch(function (err) {
        refreshBtn.classList.remove("is-busy");
        toast(err.message);
      });
    });
  }
  var skipallBtn = document.getElementById("skipall-btn");
  if (skipallBtn) {
    skipallBtn.addEventListener("click", function () {
      var scope = skipallBtn.hasAttribute("data-feed") ? "this feed" : "every feed";
      if (!confirm("Skip all stories in " + scope + "? They move to the Skipped bin and can be restored from there.")) return;
      var payload = skipallBtn.hasAttribute("data-feed")
        ? { feed: parseInt(skipallBtn.getAttribute("data-feed"), 10) } : {};
      api("/entries/skip-all", payload).then(function () { location.reload(); })
        .catch(function (err) { toast(err.message); });
    });
  }
  var readallBtn = document.getElementById("readall-btn");
  if (readallBtn) {
    readallBtn.addEventListener("click", function () {
      var payload = readallBtn.hasAttribute("data-feed")
        ? { feed: parseInt(readallBtn.getAttribute("data-feed"), 10) } : {};
      api("/entries/read-all", payload).then(function () { location.reload(); })
        .catch(function (err) { toast(err.message); });
    });
  }

  /* ————— Stories: open reader, star, read state ————— */
  var reader = document.getElementById("reader");
  var currentEntryId = null;
  var currentFeedId = null;
  var currentRead = false;
  var currentEntryUrl = null;

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    // Fallback for plain-http LAN deployments where the Clipboard API
    // is unavailable outside secure contexts.
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      (reader.open ? reader : document.body).appendChild(area);
      area.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (_) {}
      area.remove();
      ok ? resolve() : reject(new Error("Copy failed"));
    });
  }

  function youtubeVideoId(url) {
    if (!url) return null;
    var u;
    try { u = new URL(url); } catch (_) { return null; }
    var host = u.hostname.replace(/^(www|m)\./, "");
    var id = null;
    if (host === "youtu.be") {
      id = u.pathname.slice(1).split("/")[0];
    } else if (host === "youtube.com" || host.endsWith(".youtube.com")) {
      if (u.pathname === "/watch") id = u.searchParams.get("v");
      else if (/^\/(shorts|embed|live)\//.test(u.pathname)) id = u.pathname.split("/")[2];
    }
    return id && /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
  }

  function storyIds() {
    return Array.prototype.map.call(document.querySelectorAll(".story[data-id]"), function (el) {
      return parseInt(el.getAttribute("data-id"), 10);
    });
  }

  function setCardRead(entryId, read) {
    document.querySelectorAll('.story[data-id="' + entryId + '"]').forEach(function (el) {
      el.classList.toggle("is-read", read);
    });
  }

  function bumpUnread(feedId, delta) {
    document.querySelectorAll(".feed-list .feeditem").forEach(function (link) {
      var m = link.href.match(/[?&]feed=(\d+)/);
      if (!m || parseInt(m[1], 10) !== feedId) return;
      var badge = link.querySelector(".count");
      if (!badge && delta > 0) {
        badge = document.createElement("span");
        badge.className = "count";
        badge.textContent = "0";
        link.appendChild(badge);
      }
      if (!badge) return;
      var value = (parseInt(badge.textContent, 10) || 0) + delta;
      if (value <= 0) badge.remove();
      else badge.textContent = value;
    });
    var allNav = document.getElementById("nav-unread");
    if (allNav) {
      var total = allNav.querySelector(".count");
      if (!total && delta > 0) {
        total = document.createElement("span");
        total.className = "count count--volt";
        total.id = "total-unread";
        total.textContent = "0";
        allNav.appendChild(total);
      }
      if (total) {
        var t = (parseInt(total.textContent, 10) || 0) + delta;
        if (t <= 0) total.remove();
        else total.textContent = t;
      }
    }
  }

  function inSkippedView() {
    var root = document.getElementById("entries-root");
    return !!root && root.getAttribute("data-filter") === "skipped";
  }

  function setReaderReadState(read) {
    currentRead = read;
    var btn = document.getElementById("reader-read");
    if (btn) {
      btn.classList.toggle("is-read", read);
      btn.title = read ? "Mark as unread" : "Mark as read";
      btn.setAttribute("aria-label", btn.title);
    }
  }

  function openEntry(entryId) {
    if (!reader) return;
    fetch("/entries/" + entryId, { headers: { "X-CSRF": CSRF } })
      .then(function (resp) {
        if (!resp.ok) throw new Error("Could not load this story.");
        return resp.json();
      })
      .then(function (data) {
        currentEntryId = data.id;
        currentFeedId = data.feed_id;
        if (data.auto_marked && !inSkippedView()) bumpUnread(data.feed_id, -1);
        setReaderReadState(data.read);
        var readerFeed = document.getElementById("reader-feed");
        readerFeed.textContent = data.feed;
        if (data.site_url) readerFeed.href = data.site_url;
        else readerFeed.removeAttribute("href");
        document.getElementById("reader-title").textContent = data.title;
        var meta = [data.published];
        if (data.author) meta.unshift(data.author);
        if (data.minutes) meta.push(data.minutes + " min read");
        document.getElementById("reader-meta").textContent = meta.join("  ·  ");
        var hero = document.getElementById("reader-hero");
        hero.innerHTML = "";
        var content = document.getElementById("reader-content");
        content.innerHTML = data.content || "<p>This feed only provides a preview. Read the full story on the site.</p>";
        var videoId = youtubeVideoId(data.url);
        if (videoId) {
          // YouTube story: embed the player where the hero image would go.
          var wrap = document.createElement("div");
          wrap.className = "video-embed";
          var frame = document.createElement("iframe");
          frame.src = "https://www.youtube-nocookie.com/embed/" + videoId;
          frame.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
          frame.allowFullscreen = true;
          frame.title = data.title;
          wrap.appendChild(frame);
          hero.appendChild(wrap);
        } else {
          // Show the lead image only if the article body doesn't already open
          // with one (feeds often repeat the same image under a different URL).
          var bodyOpensWithImage = content.innerHTML.slice(0, 600).indexOf("<img") !== -1;
          if (data.image && !bodyOpensWithImage && content.innerHTML.indexOf(data.image) === -1) {
            var img = document.createElement("img");
            img.src = data.image;
            img.alt = "";
            img.onerror = function () { hero.innerHTML = ""; };
            hero.appendChild(img);
          }
        }
        currentEntryUrl = data.url || null;
        var copyBtn = document.getElementById("reader-copy");
        copyBtn.style.display = data.url ? "" : "none";
        var visit = document.getElementById("reader-visit");
        var visitFoot = document.getElementById("reader-visit-foot");
        visit.style.display = visitFoot.style.display = data.url ? "" : "none";
        if (data.url) { visit.href = visitFoot.href = data.url; }
        document.getElementById("reader-star").classList.toggle("is-starred", !!data.starred);
        // Grey the card only when the story is actually read.
        setCardRead(data.id, data.read);
        if (!reader.open) reader.showModal();
        reader.scrollTop = 0;
      })
      .catch(function (err) { toast(err.message); });
  }

  function openSibling(step) {
    var ids = storyIds();
    var idx = ids.indexOf(currentEntryId);
    if (idx === -1) return;
    var next = ids[idx + step];
    if (next) openEntry(next);
  }

  function performHide(hideStory, onHidden) {
    var hideId = parseInt(hideStory.getAttribute("data-id"), 10);
    var hideFeed = parseInt(hideStory.getAttribute("data-feed"), 10);
    var wasUnread = !hideStory.classList.contains("is-read");
    var root = document.getElementById("entries-root");
    if (root && root.getAttribute("data-filter") === "skipped") {
      // In the Skipped view the same action restores the story.
      api("/entries/" + hideId + "/hide", { hidden: false }).then(function () {
        document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
          el.classList.add("is-hidden");   // leaves this list; it's visible elsewhere again
        });
        if (onHidden) onHidden();
        if (wasUnread) bumpUnread(hideFeed, 1);
        toast("Story restored", "Undo", function () {
          api("/entries/" + hideId + "/hide").then(function () {
            document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
              el.classList.remove("is-hidden");
            });
            if (wasUnread) bumpUnread(hideFeed, -1);
          }).catch(function (err) { toast(err.message); });
        });
      }).catch(function (err) { toast(err.message); });
      return;
    }
    api("/entries/" + hideId + "/hide").then(function () {
      document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
        el.classList.add("is-hidden");
      });
      if (onHidden) onHidden();
      if (wasUnread) bumpUnread(hideFeed, -1);
      toast("Story skipped", "Undo", function () {
        api("/entries/" + hideId + "/hide", { hidden: false }).then(function () {
          document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
            el.classList.remove("is-hidden");
          });
          if (wasUnread) bumpUnread(hideFeed, 1);
        }).catch(function (err) { toast(err.message); });
      });
    }).catch(function (err) { toast(err.message); });
  }

  document.addEventListener("click", function (e) {
    var hideBtn = e.target.closest("[data-hide]");
    if (hideBtn) {
      e.stopPropagation();
      performHide(hideBtn.closest(".story"));
      return;
    }
    var star = e.target.closest("[data-star]");
    if (star) {
      e.stopPropagation();
      var story = star.closest(".story");
      var entryId = parseInt(story.getAttribute("data-id"), 10);
      api("/entries/" + entryId + "/star").then(function (data) {
        star.classList.toggle("is-starred", data.starred);
        toast(data.starred ? "Saved" : "Removed from saved");
      }).catch(function (err) { toast(err.message); });
      return;
    }
    var story = e.target.closest(".story[data-id]");
    if (story) openEntry(parseInt(story.getAttribute("data-id"), 10));
  });
  document.addEventListener("keydown", function (e) {
    var story = e.target.closest && e.target.closest(".story[data-id]");
    if (story && (e.key === "Enter" || e.key === " ") && !e.target.closest("[data-star]")) {
      e.preventDefault();
      openEntry(parseInt(story.getAttribute("data-id"), 10));
    }
  });

  if (reader) {
    reader.addEventListener("close", function () {
      // Stories read in the reader leave the Unread list (they're read) and
      // the Skipped list (reading them un-skipped them) once it closes.
      var root = document.getElementById("entries-root");
      var f = root && root.getAttribute("data-filter");
      if (f !== "unread" && f !== "skipped") return;
      var dismissed = 0;
      document.querySelectorAll(".story.is-read:not(.is-hidden)").forEach(function (el) {
        el.classList.add("is-hidden");
        dismissed++;
      });
      if (dismissed && !document.querySelector(".story:not(.is-hidden)")) {
        location.reload();   // empty now — show the "All caught up" state
      }
    });
    document.getElementById("reader-prev").addEventListener("click", function () { openSibling(-1); });
    document.getElementById("reader-next").addEventListener("click", function () { openSibling(1); });
    var copyTipTimer = null;
    document.getElementById("reader-copy").addEventListener("click", function () {
      if (!currentEntryUrl) return;
      var btn = this;
      copyText(currentEntryUrl)
        .then(function () {
          btn.classList.add("show-tip");
          clearTimeout(copyTipTimer);
          copyTipTimer = setTimeout(function () { btn.classList.remove("show-tip"); }, 1300);
        })
        .catch(function () { toast("Couldn't copy the link"); });
    });
    document.getElementById("reader-read").addEventListener("click", function () {
      if (!currentEntryId) return;
      var next = !currentRead;
      api("/entries/" + currentEntryId + "/read", { read: next }).then(function () {
        setReaderReadState(next);
        setCardRead(currentEntryId, next);
        if (!inSkippedView()) bumpUnread(currentFeedId, next ? -1 : 1);
        toast(next ? "Marked as read" : "Marked as unread");
      }).catch(function (err) { toast(err.message); });
    });
    document.getElementById("reader-star").addEventListener("click", function () {
      if (!currentEntryId) return;
      var btn = this;
      api("/entries/" + currentEntryId + "/star").then(function (data) {
        btn.classList.toggle("is-starred", data.starred);
        document.querySelectorAll('.story[data-id="' + currentEntryId + '"] [data-star]').forEach(function (el) {
          el.classList.toggle("is-starred", data.starred);
        });
      }).catch(function () {});
    });
    document.addEventListener("keydown", function (e) {
      if (!reader.open) return;
      if (e.key === "j" || e.key === "ArrowRight") openSibling(1);
      if (e.key === "k" || e.key === "ArrowLeft") openSibling(-1);
    });
  }

  /* ————— About hero: animated sine-wave gradient ————— */
  (function initAboutHeroBg() {
    var canvas = document.querySelector(".about-hero-bg");
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var W = 200, H = 120;
    canvas.width = W; canvas.height = H;
    var cctx = canvas.getContext("2d");

    function hslToRgb(h, s, l) {
      h /= 360;
      var a = s * Math.min(l, 1 - l);
      var f = function (n) {
        var k = (n + h * 12) % 12;
        return Math.round((l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))) * 255);
      };
      return [f(0), f(8), f(4)];
    }
    var rand = function (a, b) { return a + Math.random() * (b - a); };

    // Triadic palette from a random base hue; jitter keeps each visit distinct.
    var hueBase = Math.random() * 360;
    var triad = [0, 120, 240].map(function (d) { return (hueBase + d + rand(-8, 8) + 360) % 360; });
    for (var i = triad.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = triad[i]; triad[i] = triad[j]; triad[j] = tmp;
    }
    var rgb = triad.map(function (h) { return hslToRgb(h, 1, 0.55); });
    var n = rgb.length;

    var freq1 = rand(2.2, 4.0), freq2 = rand(5.0, 8.0);
    var amp1 = rand(0.16, 0.28), amp2 = rand(0.06, 0.12);
    var speed1 = rand(0.05, 0.12) * (Math.random() < 0.5 ? 1 : -1);
    var speed2 = rand(0.06, 0.14) * (Math.random() < 0.5 ? 1 : -1);
    var phase = Math.random() * Math.PI * 2;
    var rot = Math.random() * Math.PI * 2;
    var cosR = Math.cos(rot), sinR = Math.sin(rot);
    var maxDim = Math.max(W, H);

    var img = cctx.createImageData(W, H);
    var d = img.data;
    var running = false, start = 0;

    function frame(now) {
      if (!running) return;
      var t = (now - start) / 1000;
      var p1 = t * speed1, p2 = t * speed2 + phase;
      for (var y = 0; y < H; y++) {
        for (var x = 0; x < W; x++) {
          var cx = x - W / 2, cy = y - H / 2;
          var rx = cx * cosR - cy * sinR, ry = cx * sinR + cy * cosR;
          var nx = (rx + maxDim / 2) / maxDim, ny = (ry + maxDim / 2) / maxDim;
          var wave = Math.sin(nx * freq1 + p1) * amp1 + Math.sin(nx * freq2 + p2) * amp2;
          var g = Math.min(0.9999, Math.max(0, ny + wave));
          var seg = g * (n - 1), lo = Math.floor(seg), f = seg - lo;
          var c0 = rgb[lo], c1 = rgb[Math.min(lo + 1, n - 1)];
          var o = (y * W + x) * 4;
          d[o] = c0[0] + (c1[0] - c0[0]) * f;
          d[o + 1] = c0[1] + (c1[1] - c0[1]) * f;
          d[o + 2] = c0[2] + (c1[2] - c0[2]) * f;
          d[o + 3] = 255;
        }
      }
      cctx.putImageData(img, 0, 0);
      requestAnimationFrame(frame);
    }
    // Only animate while the canvas is actually visible (About tab open).
    new IntersectionObserver(function (entries) {
      var visible = entries[0].isIntersecting;
      if (visible && !running) {
        running = true;
        start = performance.now();
        requestAnimationFrame(frame);
      } else if (!visible) {
        running = false;
      }
    }).observe(canvas);
  })();

  /* ————— Search palette (Ctrl/Cmd+K) ————— */
  var palette = document.getElementById("search-modal");
  if (palette) {
    var searchInput = document.getElementById("search-input");
    var resultsEl = document.getElementById("search-results");
    var searchTimer = null;
    var items = [];        // flat list of actionable rows
    var activeIndex = -1;
    var lastQuery = "";

    function openPalette() {
      if (!palette.open) palette.showModal();
      searchInput.focus();
      searchInput.select();
    }
    document.getElementById("search-btn").addEventListener("click", openPalette);
    var searchKbd = document.getElementById("search-kbd");
    if (searchKbd && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
      searchKbd.textContent = "⌘K";
    }
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (palette.open) palette.close();
        else openPalette();
      }
    });
    palette.addEventListener("click", function (e) {
      if (e.target === palette) palette.close();
    });

    function highlighted(text, query) {
      var span = document.createElement("span");
      span.className = "palette-item-title";
      var idx = text.toLowerCase().indexOf(query.toLowerCase());
      if (idx === -1) {
        span.textContent = text;
        return span;
      }
      span.appendChild(document.createTextNode(text.slice(0, idx)));
      var mark = document.createElement("mark");
      mark.textContent = text.slice(idx, idx + query.length);
      span.appendChild(mark);
      span.appendChild(document.createTextNode(text.slice(idx + query.length)));
      return span;
    }

    function row(iconUrl, titleEl, meta, onPick, extraClass) {
      var el = document.createElement("div");
      el.className = "palette-item" + (extraClass ? " " + extraClass : "");
      var icon = document.createElement("img");
      icon.className = "favicon";
      icon.src = iconUrl || "";
      icon.onerror = function () { icon.classList.add("is-broken"); };
      el.appendChild(icon);
      el.appendChild(titleEl);
      if (meta) {
        var metaEl = document.createElement("span");
        metaEl.className = "palette-item-meta";
        metaEl.textContent = meta;
        el.appendChild(metaEl);
      }
      el.addEventListener("click", onPick);
      el.addEventListener("mousemove", function () { setActive(items.indexOf(el)); });
      el._pick = onPick;
      return el;
    }

    function setActive(index) {
      activeIndex = index;
      items.forEach(function (el, i) { el.classList.toggle("is-active", i === index); });
      if (items[index]) items[index].scrollIntoView({ block: "nearest" });
    }

    function render(data, query) {
      resultsEl.innerHTML = "";
      items = [];
      if (!data.feeds.length && !data.entries.length) {
        var empty = document.createElement("div");
        empty.className = "palette-empty";
        empty.textContent = 'No matches for "' + query + '"';
        resultsEl.appendChild(empty);
        resultsEl.hidden = false;
        return;
      }
      if (data.feeds.length) {
        var flabel = document.createElement("div");
        flabel.className = "palette-label";
        flabel.textContent = "Feeds";
        resultsEl.appendChild(flabel);
        data.feeds.forEach(function (f) {
          var el = row(f.icon, highlighted(f.title, query), "feed", function () {
            location.href = "/?feed=" + f.id;
          });
          resultsEl.appendChild(el);
          items.push(el);
        });
      }
      if (data.entries.length) {
        var slabel = document.createElement("div");
        slabel.className = "palette-label";
        slabel.textContent = "Stories";
        resultsEl.appendChild(slabel);
        data.entries.forEach(function (s) {
          var el = row(s.icon, highlighted(s.title, query), s.feed + " · " + s.ago,
            function () {
              palette.close();
              openEntry(s.id);
            }, s.read ? "is-read" : "");
          resultsEl.appendChild(el);
          items.push(el);
        });
      }
      resultsEl.hidden = false;
      setActive(items.length ? 0 : -1);
    }

    searchInput.addEventListener("input", function () {
      var query = searchInput.value.trim();
      clearTimeout(searchTimer);
      if (query.length < 2) {
        resultsEl.hidden = true;
        resultsEl.innerHTML = "";
        items = [];
        return;
      }
      searchTimer = setTimeout(function () {
        lastQuery = query;
        fetch("/search?q=" + encodeURIComponent(query), { headers: { "X-CSRF": CSRF } })
          .then(function (resp) { return resp.json(); })
          .then(function (data) {
            if (query === lastQuery) render(data, query);
          })
          .catch(function () {});
      }, 200);
    });

    searchInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (items.length) setActive((activeIndex + 1) % items.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (items.length) setActive((activeIndex - 1 + items.length) % items.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (items[activeIndex]) items[activeIndex]._pick();
      }
    });
  }

  /* ————— YouTube thumbnails: crop baked-in letterbox bars ————— */
  function classifyYtThumb(img) {
    if (!img.naturalWidth || !img.naturalHeight) return;
    var thumb = img.closest(".thumb--yt");
    if (!thumb) return;
    // 4:3 file = 16:9 video letterboxed inside it; zoom crops the bars.
    if (img.naturalWidth / img.naturalHeight < 1.5) thumb.classList.add("thumb--crop");
  }
  document.addEventListener("load", function (e) {
    var img = e.target;
    if (img.tagName === "IMG" && img.closest && img.closest(".thumb--yt")) {
      classifyYtThumb(img);
    }
  }, true);
  document.querySelectorAll(".thumb--yt img").forEach(function (img) {
    if (img.complete) classifyYtThumb(img);
  });

  /* ————— Card swipes (touch): left = hide, right = save + mark read ————— */
  function performSaveRead(storyEl, onDone) {
    var id = parseInt(storyEl.getAttribute("data-id"), 10);
    var feedId = parseInt(storyEl.getAttribute("data-feed"), 10);
    var wasUnread = !storyEl.classList.contains("is-read");
    Promise.all([
      api("/entries/" + id + "/star", { starred: true }),
      api("/entries/" + id + "/read", { read: true }),
    ]).then(function () {
      document.querySelectorAll('.story[data-id="' + id + '"]').forEach(function (el) {
        el.classList.add("is-read");
        var starBtn = el.querySelector("[data-star]");
        if (starBtn) starBtn.classList.add("is-starred");
      });
      if (wasUnread && !inSkippedView()) bumpUnread(feedId, -1);
      if (onDone) onDone();
      toast("Saved", "Undo", function () {
        Promise.all([
          api("/entries/" + id + "/star", { starred: false }),
          api("/entries/" + id + "/read", { read: false }),
        ]).then(function () {
          document.querySelectorAll('.story[data-id="' + id + '"]').forEach(function (el) {
            el.classList.remove("is-read", "is-hidden");
            var starBtn = el.querySelector("[data-star]");
            if (starBtn) starBtn.classList.remove("is-starred");
          });
          if (wasUnread && !inSkippedView()) bumpUnread(feedId, 1);
        }).catch(function (err) { toast(err.message); });
      });
    }).catch(function (err) { toast(err.message); });
  }

  (function initCardSwipes() {
    if (!window.matchMedia("(pointer: coarse)").matches) return;
    var story = null, startX = 0, startY = 0, dx = 0, dir = 0, thresholdPx = 0;
    var engaged = false, cancelled = false;

    // Action pill: tells the user what releasing the swipe will do. Lives
    // only for the duration of the gesture — slides in from the screen edge,
    // slides down and fades on release.
    var pill = document.createElement("div");
    pill.className = "swipe-pill";
    document.body.appendChild(pill);
    var pillTimer = null;
    var PILL_HIDE = '<svg viewBox="0 0 24 24"><path d="m5 5.5 6.5 6.5L5 18.5M12.5 5.5 19 12l-6.5 6.5"/></svg>Skip';
    var PILL_UNHIDE = '<svg viewBox="0 0 24 24"><path d="M2.5 4v6h6"/><path d="M4.6 15.5A8.5 8.5 0 1 0 4 9L2.5 10"/></svg>Restore';
    var PILL_SAVE = '<svg viewBox="0 0 24 24"><path d="M7 4.5h10a1 1 0 0 1 1 1V20l-6-3.5L6 20V5.5a1 1 0 0 1 1-1Z"/></svg>Save';

    function showPill(el, direction) {
      clearTimeout(pillTimer);
      pill.className = "swipe-pill " + (direction < 0 ? "from-left" : "from-right");
      var root = document.getElementById("entries-root");
      var inHidden = root && root.getAttribute("data-filter") === "skipped";
      pill.innerHTML = direction < 0 ? (inHidden ? PILL_UNHIDE : PILL_HIDE) : PILL_SAVE;
      var rect = el.getBoundingClientRect();
      pill.style.top = rect.top + rect.height / 2 + "px";
      // The pill sits on the side the card is heading toward.
      pill.style.left = direction < 0 ? "18px" : "auto";
      pill.style.right = direction > 0 ? "18px" : "auto";
      void pill.offsetWidth;   // flush styles so the entry transition plays
      pill.classList.add("is-showing");
    }

    function hidePill() {
      if (!pill.classList.contains("is-showing")) {
        pill.className = "swipe-pill";
        return;
      }
      pill.classList.remove("is-showing");
      pill.classList.add("is-leaving");
      clearTimeout(pillTimer);
      pillTimer = setTimeout(function () { pill.className = "swipe-pill"; }, 320);
    }

    function resetSwipeStyles(el) {
      el.classList.remove("swipe-out", "swipe-collapse");
      el.style.transform = "";
      el.style.opacity = "";
      el.style.height = "";
      el.style.overflow = "";
      el.style.paddingTop = "";
      el.style.paddingBottom = "";
    }

    function slideOutAndCollapse(el, dirSign, done) {
      el.classList.add("swipe-out");
      el.style.transform = "translateX(" + dirSign * 110 + "%)";
      el.style.opacity = "0";
      setTimeout(function () {
        el.style.height = el.offsetHeight + "px";
        el.style.overflow = "hidden";
        el.classList.add("swipe-collapse");
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            el.style.height = "0px";
            el.style.paddingTop = "0px";
            el.style.paddingBottom = "0px";
          });
        });
      }, 60);
      setTimeout(function () {
        el.classList.add("is-hidden");
        done();
      }, 250);
    }

    function springBack(el) {
      el.classList.add("swipe-return");
      el.style.transform = "";
      el.style.opacity = "";
      setTimeout(function () { el.classList.remove("swipe-return"); }, 300);
    }

    document.addEventListener("touchstart", function (e) {
      var el = e.target.closest && e.target.closest(".story[data-id]");
      if (!el || e.touches.length !== 1 || document.querySelector("dialog[open]")) {
        story = null;
        return;
      }
      story = el;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      dx = 0;
      dir = 0;
      engaged = false;
      cancelled = false;
    }, { passive: true });

    document.addEventListener("touchmove", function (e) {
      if (!story || cancelled) return;
      var t = e.touches[0];
      dx = t.clientX - startX;
      var dy = t.clientY - startY;
      if (!engaged) {
        // Axis lock: a mostly-vertical move is a scroll, leave it alone.
        if (Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx)) { cancelled = true; return; }
        if (Math.abs(dx) > 14 && Math.abs(dx) > Math.abs(dy)) {
          engaged = true;
          dir = dx < 0 ? -1 : 1;
          thresholdPx = story.offsetWidth * 0.6;
          story.classList.add("is-swiping");
          window.__hfCardSwipe = true;
          showPill(story, dir);
        } else {
          return;
        }
      }
      e.preventDefault();   // own the gesture: no scroll while sliding the card
      var x = dir < 0 ? Math.min(0, dx) : Math.max(0, dx);
      story.style.transform = "translateX(" + x + "px)";
      story.style.opacity = String(Math.max(0.3, 1 - Math.abs(x) / (story.offsetWidth * 1.1)));
      pill.classList.toggle("is-armed", Math.abs(x) >= thresholdPx);
    }, { passive: false });

    document.addEventListener("touchend", function () {
      window.__hfCardSwipe = false;
      hidePill();
      if (!story || !engaged) { story = null; return; }
      var el = story;
      story = null;
      el.classList.remove("is-swiping");
      var threshold = el.offsetWidth * 0.6;   // deliberate swipe, not a nudge

      if (dir < 0 && dx <= -threshold) {
        // Hide.
        slideOutAndCollapse(el, -1, function () {
          performHide(el, function () { resetSwipeStyles(el); });
        });
      } else if (dir > 0 && dx >= threshold) {
        // Save + mark read.
        var rootEl = document.getElementById("entries-root");
        if (rootEl && rootEl.getAttribute("data-filter") === "unread") {
          // Read stories leave the Unread view.
          slideOutAndCollapse(el, 1, function () {
            performSaveRead(el, function () { resetSwipeStyles(el); });
          });
        } else {
          springBack(el);
          performSaveRead(el);
        }
      } else {
        springBack(el);
      }
    });

    document.addEventListener("touchcancel", function () {
      window.__hfCardSwipe = false;
      hidePill();
      if (story && engaged) springBack(story);
      story = null;
      engaged = false;
    });
  })();

  /* ————— Pull to refresh (touch devices) ————— */
  (function initPullToRefresh() {
    if (!window.matchMedia("(pointer: coarse)").matches) return;
    if (!document.getElementById("entries-root")) return;  // app pages only

    var THRESHOLD = 64;   // px of indicator travel that arms the refresh
    var indicator = document.createElement("div");
    indicator.className = "ptr";
    indicator.setAttribute("aria-hidden", "true");
    indicator.innerHTML = '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 3.5V7h-3.5"/></svg>';
    document.body.appendChild(indicator);

    var startY = null, startX = null, pulling = false, armed = false, refreshing = false;

    function setTravel(px) {
      indicator.style.transform = "translateY(" + px + "px) rotate(" + px * 2.2 + "deg)";
    }
    function reset() {
      indicator.classList.remove("is-dragging", "is-armed");
      indicator.style.transform = "";
    }

    document.addEventListener("touchstart", function (e) {
      if (refreshing || window.scrollY > 0) return;
      if (document.querySelector("dialog[open]") || document.querySelector(".sidebar.is-open")) return;
      startY = e.touches[0].clientY;
      startX = e.touches[0].clientX;
      pulling = true;
      armed = false;
    }, { passive: true });

    document.addEventListener("touchmove", function (e) {
      if (!pulling || refreshing) return;
      if (window.__hfCardSwipe) { armed = false; reset(); pulling = false; return; }
      var dy = e.touches[0].clientY - startY;
      var dxp = e.touches[0].clientX - startX;
      if (dy <= 0 || Math.abs(dxp) > dy || window.scrollY > 0) {
        armed = false;
        reset();
        return;
      }
      var travel = Math.min(dy * 0.45, 104);
      indicator.classList.add("is-dragging");
      setTravel(travel);
      armed = travel >= THRESHOLD;
      indicator.classList.toggle("is-armed", armed);
    }, { passive: true });

    document.addEventListener("touchend", function () {
      if (!pulling) return;
      pulling = false;
      indicator.classList.remove("is-dragging");
      if (armed && !refreshing) {
        refreshing = true;
        indicator.classList.add("is-refreshing");
        setTravel(THRESHOLD);
        api("/refresh").then(function () {
          location.reload();
        }).catch(function (err) {
          toast(err.message);
          refreshing = false;
          indicator.classList.remove("is-refreshing");
          reset();
        });
      } else {
        reset();
      }
    });
  })();

  /* ————— Load more ————— */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("#load-more");
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = "Loading…";
    var params = new URLSearchParams(location.search);
    params.set("partial", "1");
    params.set("page", btn.getAttribute("data-next"));
    fetch(location.pathname + "?" + params, { headers: { "X-CSRF": CSRF } })
      .then(function (resp) { return resp.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var newGrid = doc.querySelector(".grid");
        var grid = document.querySelector("#entries-root .grid");
        if (newGrid && grid) {
          while (newGrid.firstChild) grid.appendChild(newGrid.firstChild);
        }
        var oldPager = document.querySelector("#entries-root .pager");
        var newPager = doc.querySelector(".pager");
        if (oldPager) {
          if (newPager) oldPager.replaceWith(newPager);
          else oldPager.remove();
        }
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Load older stories";
        toast("Could not load more stories.");
      });
  });
})();
