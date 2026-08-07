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
          throw err;
        }
        return data;
      });
    });
  }

  var toastTimer;
  function toast(message, actionLabel, actionFn) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    if (actionLabel) {
      var action = document.createElement("button");
      action.className = "toast-action";
      action.textContent = actionLabel;
      action.addEventListener("click", function () {
        clearTimeout(toastTimer);
        el.hidden = true;
        actionFn();
      });
      el.appendChild(action);
    }
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, actionLabel ? 5000 : 2600);
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
  document.querySelectorAll("[data-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var dialog = document.getElementById(btn.getAttribute("data-open"));
      if (dialog) dialog.showModal();
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
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.toggle("is-active", t === tab); });
      document.querySelectorAll(".tabpane").forEach(function (pane) {
        pane.classList.toggle("is-active", pane.getAttribute("data-pane") === tab.getAttribute("data-tab"));
      });
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

  /* ————— Settings: add / sort / reorder feeds ————— */
  var feedsManage = document.getElementById("feeds-manage");

  function feedsOrder() {
    return Array.prototype.map.call(
      feedsManage.querySelectorAll(".manage-item[data-feed]"),
      function (li) { return parseInt(li.getAttribute("data-feed"), 10); }
    );
  }

  function syncSidebarOrder() {
    var list = document.querySelector(".sidebar .feed-list");
    if (!list) return;
    var byId = {};
    list.querySelectorAll("li").forEach(function (li) {
      var link = li.querySelector('a[href*="feed="]');
      var m = link && link.href.match(/[?&]feed=(\d+)/);
      if (m) byId[m[1]] = li;
    });
    feedsOrder().forEach(function (id) {
      if (byId[id]) list.appendChild(byId[id]);
    });
  }

  function saveFeedOrder() {
    api("/feeds/reorder", { order: feedsOrder() })
      .then(function () { syncSidebarOrder(); toast("Feed order saved"); })
      .catch(function (err) { toast(err.message); });
  }

  if (feedsManage) {
    var draggedItem = null;
    feedsManage.querySelectorAll(".manage-item").forEach(function (li) {
      li.addEventListener("dragstart", function (e) {
        draggedItem = li;
        li.classList.add("is-dragging");
        e.dataTransfer.effectAllowed = "move";
        try { e.dataTransfer.setData("text/plain", li.getAttribute("data-feed")); } catch (_) {}
      });
      li.addEventListener("dragend", function () {
        li.classList.remove("is-dragging");
        draggedItem = null;
        saveFeedOrder();
      });
    });
    feedsManage.addEventListener("dragover", function (e) {
      if (!draggedItem) return;
      e.preventDefault();
      var items = Array.prototype.filter.call(
        feedsManage.querySelectorAll(".manage-item:not(.is-dragging)"),
        function () { return true; }
      );
      var next = null;
      for (var i = 0; i < items.length; i++) {
        var rect = items[i].getBoundingClientRect();
        if (e.clientY < rect.top + rect.height / 2) { next = items[i]; break; }
      }
      if (next) feedsManage.insertBefore(draggedItem, next);
      else feedsManage.appendChild(draggedItem);
    });

    document.querySelectorAll("[data-sort]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var dir = btn.getAttribute("data-sort") === "desc" ? -1 : 1;
        var items = Array.prototype.slice.call(feedsManage.querySelectorAll(".manage-item"));
        items.sort(function (a, b) {
          var ta = a.querySelector(".manage-title").textContent.trim().toLowerCase();
          var tb = b.querySelector(".manage-title").textContent.trim().toLowerCase();
          return ta < tb ? -dir : ta > tb ? dir : 0;
        });
        items.forEach(function (li) { feedsManage.appendChild(li); });
        saveFeedOrder();
      });
    });
  }

  var feedsAddForm = document.getElementById("feeds-add-form");
  if (feedsAddForm) {
    var feedsScrape = document.getElementById("feeds-scrape");
    var feedsScrapeBtn = document.getElementById("feeds-scrape-btn");
    var feedsPendingUrl = null;

    function settingsAddFeed(url, busyBtn, scrape) {
      var errEl = document.getElementById("feeds-add-error");
      errEl.hidden = true;
      feedsScrape.hidden = true;
      if (!url) return;
      busyBtn.disabled = true;
      busyBtn.querySelector(".btn-label").hidden = true;
      busyBtn.querySelector(".btn-busy").hidden = false;
      api("/feeds/add", { url: url, scrape: !!scrape })
        .then(function (data) { location.href = data.redirect; })
        .catch(function (err) {
          errEl.textContent = err.message;
          errEl.hidden = false;
          if (err.canScrape && !scrape) {
            feedsPendingUrl = url;
            feedsScrape.hidden = false;
          }
          busyBtn.disabled = false;
          busyBtn.querySelector(".btn-label").hidden = false;
          busyBtn.querySelector(".btn-busy").hidden = true;
        });
    }

    feedsAddForm.addEventListener("submit", function (e) {
      e.preventDefault();
      settingsAddFeed(document.getElementById("feeds-add-url").value.trim(),
                      feedsAddForm.querySelector("button"), false);
    });
    document.getElementById("feeds-add-url").addEventListener("input", function () {
      feedsScrape.hidden = true;
    });
    feedsScrapeBtn.addEventListener("click", function () {
      if (feedsPendingUrl) settingsAddFeed(feedsPendingUrl, feedsScrapeBtn, true);
    });
  }

  /* ————— Add feed ————— */
  var addForm = document.getElementById("add-form");
  if (addForm) {
    var scrapeOffer = document.getElementById("scrape-offer");
    var scrapeBtn = document.getElementById("scrape-btn");

    function setBusy(btn, busy) {
      btn.disabled = busy;
      btn.querySelector(".btn-label").hidden = busy;
      btn.querySelector(".btn-busy").hidden = !busy;
    }

    function submitAdd(scrape, btn) {
      var errEl = document.getElementById("add-error");
      errEl.hidden = true;
      setBusy(btn, true);
      api("/feeds/add", { url: document.getElementById("add-url").value, scrape: scrape })
        .then(function (data) { location.href = data.redirect; })
        .catch(function (err) {
          errEl.textContent = err.message;
          errEl.hidden = false;
          scrapeOffer.hidden = !(err.canScrape && !scrape);
          setBusy(btn, false);
        });
    }

    addForm.addEventListener("submit", function (e) {
      e.preventDefault();
      scrapeOffer.hidden = true;
      submitAdd(false, addForm.querySelector('button[type="submit"]'));
    });
    scrapeBtn.addEventListener("click", function () {
      submitAdd(true, scrapeBtn);
    });
    document.getElementById("add-url").addEventListener("input", function () {
      scrapeOffer.hidden = true;
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
    var unreadNav = document.querySelector('.nav-primary a[href*="filter=unread"]');
    if (unreadNav) {
      var total = unreadNav.querySelector(".count");
      if (!total && delta > 0) {
        total = document.createElement("span");
        total.className = "count count--volt";
        total.textContent = "0";
        unreadNav.appendChild(total);
      }
      if (total) {
        var t = (parseInt(total.textContent, 10) || 0) + delta;
        if (t <= 0) total.remove();
        else total.textContent = t;
      }
    }
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
        if (data.auto_marked) bumpUnread(data.feed_id, -1);
        setReaderReadState(data.read);
        document.getElementById("reader-feed").textContent = data.feed;
        document.getElementById("reader-title").textContent = data.title;
        var meta = [data.published];
        if (data.author) meta.unshift(data.author);
        if (data.minutes) meta.push(data.minutes + " min read");
        document.getElementById("reader-meta").textContent = meta.join("  ·  ");
        var hero = document.getElementById("reader-hero");
        hero.innerHTML = "";
        var content = document.getElementById("reader-content");
        content.innerHTML = data.content || "<p>This feed only provides a preview. Read the full story on the site.</p>";
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

  document.addEventListener("click", function (e) {
    var hideBtn = e.target.closest("[data-hide]");
    if (hideBtn) {
      e.stopPropagation();
      var hideStory = hideBtn.closest(".story");
      var hideId = parseInt(hideStory.getAttribute("data-id"), 10);
      var hideFeed = parseInt(hideStory.getAttribute("data-feed"), 10);
      var wasUnread = !hideStory.classList.contains("is-read");
      api("/entries/" + hideId + "/hide").then(function () {
        document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
          el.classList.add("is-hidden");
        });
        if (wasUnread) bumpUnread(hideFeed, -1);
        toast("Story hidden", "Undo", function () {
          api("/entries/" + hideId + "/hide", { hidden: false }).then(function () {
            document.querySelectorAll('.story[data-id="' + hideId + '"]').forEach(function (el) {
              el.classList.remove("is-hidden");
            });
            if (wasUnread) bumpUnread(hideFeed, 1);
          }).catch(function (err) { toast(err.message); });
        });
      }).catch(function (err) { toast(err.message); });
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
    document.getElementById("reader-prev").addEventListener("click", function () { openSibling(-1); });
    document.getElementById("reader-next").addEventListener("click", function () { openSibling(1); });
    document.getElementById("reader-read").addEventListener("click", function () {
      if (!currentEntryId) return;
      var next = !currentRead;
      api("/entries/" + currentEntryId + "/read", { read: next }).then(function () {
        setReaderReadState(next);
        setCardRead(currentEntryId, next);
        bumpUnread(currentFeedId, next ? -1 : 1);
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
