/**
 * FestivaFlow — Client Application Script
 * Modular ES6+, accessible modal dialogs, debounced search, DOM fragment batching,
 * live SVG radial gauges, countdown timer, category stacked expenditure bar,
 * quick stats pill strip, inline RSVP switcher, task filter chips, keyboard shortcuts,
 * canvas confetti micro-interaction, interactive analytics distributions, and strict XSS protection.
 */

(() => {
  "use strict";

  // Application Global State
  const AppState = {
    events: [],
    activeEventId: null,
    activeEventDetail: null,
    vendors: [],
    analytics: null,
    activeTabId: "tab-overview",
    previousActiveElement: null,
    searchDebounceTimer: null,
    countdownInterval: null,
    activeTaskFilter: "all",
    guestSearchQuery: "",
    guestFilterRsvp: "",
    expenseSearchQuery: "",
    expenseFilterStatus: "",
  };

  // Color mapping for budget category visualization
  const CATEGORY_COLORS = {
    Catering: "#f59e0b",      // Amber
    Venue: "#3b82f6",         // Blue
    Decor: "#ec4899",         // Pink
    Entertainment: "#8b5cf6", // Purple
    Logistics: "#10b981",     // Emerald
    Marketing: "#06b6d4",     // Cyan
    Other: "#94a3b8",         // Slate
  };

  // Avatar gradient palettes
  const AVATAR_GRADIENTS = [
    "linear-gradient(135deg, #6366f1, #a855f7)",
    "linear-gradient(135deg, #ec4899, #f43f5e)",
    "linear-gradient(135deg, #10b981, #06b6d4)",
    "linear-gradient(135deg, #f59e0b, #ea580c)",
    "linear-gradient(135deg, #3b82f6, #6366f1)",
    "linear-gradient(135deg, #8b5cf6, #d946ef)",
  ];

  function getAvatarGradient(name) {
    let hash = 0;
    for (let i = 0; i < (name || "").length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const idx = Math.abs(hash) % AVATAR_GRADIENTS.length;
    return AVATAR_GRADIENTS[idx];
  }

  // Cached DOM Element References
  const DOM = {
    // Navigation & Tabs
    tabs: document.querySelectorAll('[role="tab"]'),
    panels: document.querySelectorAll('[role="tabpanel"]'),
    eventSelector: document.getElementById("global-event-selector"),

    // Banner Elements
    bannerTitle: document.getElementById("banner-title"),
    bannerDesc: document.getElementById("banner-description"),
    bannerCategory: document.getElementById("banner-category"),
    bannerStatus: document.getElementById("banner-status"),
    bannerCountdown: document.getElementById("banner-countdown"),
    bannerDatetime: document.getElementById("banner-datetime"),
    bannerVenue: document.getElementById("banner-venue"),
    activeEventCard: document.getElementById("active-event-card"),
    overBudgetAlert: document.getElementById("over-budget-alert"),
    overBudgetText: document.getElementById("over-budget-text"),

    // Metrics
    metricBudgetTotal: document.getElementById("metric-budget-total"),
    metricBudgetBurn: document.getElementById("metric-budget-burn"),
    metricBudgetRemaining: document.getElementById("metric-budget-remaining"),
    metricBudgetStatus: document.getElementById("metric-budget-status"),
    metricBudgetPendingSub: document.getElementById("metric-budget-pending-sub"),
    budgetBurnRing: document.getElementById("budget-burn-ring"),
    budgetRingPct: document.getElementById("budget-ring-pct"),
    budgetBurnProgressBar: document.getElementById("budget-burn-progress-bar"),

    metricRsvpCount: document.getElementById("metric-rsvp-count"),
    metricRsvpCap: document.getElementById("metric-rsvp-cap"),
    rsvpCapRing: document.getElementById("rsvp-cap-ring"),
    rsvpRingPct: document.getElementById("rsvp-ring-pct"),
    rsvpProgressBar: document.getElementById("rsvp-progress-bar"),

    metricTaskPct: document.getElementById("metric-task-pct"),
    metricTaskCount: document.getElementById("metric-task-count"),
    taskProgressRing: document.getElementById("task-progress-ring"),
    taskRingPct: document.getElementById("task-ring-pct"),
    taskProgressBar: document.getElementById("task-progress-bar"),

    // Controls & Containers
    eventsCountBadge: document.getElementById("events-count-badge"),
    eventsGrid: document.getElementById("events-grid-container"),
    eventSearch: document.getElementById("event-search-input"),
    filterCategory: document.getElementById("filter-category"),
    filterStatus: document.getElementById("filter-status"),

    // Guests Tab
    guestSearchInput: document.getElementById("guest-search-input"),
    guestFilterRsvp: document.getElementById("guest-filter-rsvp"),
    guestsTableBody: document.getElementById("guests-table-body"),
    gstatTotal: document.getElementById("gstat-total"),
    gstatAttending: document.getElementById("gstat-attending"),
    gstatPending: document.getElementById("gstat-pending"),
    gstatDeclined: document.getElementById("gstat-declined"),
    gstatDiets: document.getElementById("gstat-diets"),

    // Budget Tab
    expenseSearchInput: document.getElementById("expense-search-input"),
    expenseFilterStatus: document.getElementById("expense-filter-status"),
    expensesTableBody: document.getElementById("expenses-table-body"),
    categoryStackedBar: document.getElementById("category-stacked-bar"),
    categoryStackedLegend: document.getElementById("category-stacked-legend"),
    breakdownTotalSpentTag: document.getElementById("breakdown-total-spent-tag"),

    // Tasks & Vendors
    tasksList: document.getElementById("tasks-list"),
    vendorsGrid: document.getElementById("vendors-grid"),
    toastContainer: document.getElementById("toast-container"),

    // Modals & Buttons
    btnNewEvent: document.getElementById("btn-create-event-modal"),
    btnEditActiveEvent: document.getElementById("btn-edit-active-event"),
    btnExportJson: document.getElementById("btn-export-json"),
    btnExportCsv: document.getElementById("btn-export-csv"),
    btnOpenGuestModal: document.getElementById("btn-open-guest-modal"),
    btnOpenExpenseModal: document.getElementById("btn-open-expense-modal"),
    btnOpenTaskModal: document.getElementById("btn-open-task-modal"),
    btnOpenVendorModal: document.getElementById("btn-open-vendor-modal"),

    // Forms
    formEvent: document.getElementById("form-event"),
    formGuest: document.getElementById("form-guest"),
    formExpense: document.getElementById("form-expense"),
    formTask: document.getElementById("form-task"),
    formVendor: document.getElementById("form-vendor"),
  };

  // =========================================================================
  // API CLIENT UTILITIES
  // =========================================================================

  async function apiFetch(endpoint, options = {}) {
    const defaultHeaders = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };

    try {
      const response = await fetch(endpoint, {
        ...options,
        headers: { credentials: "same-origin", ...defaultHeaders, ...options.headers },
      });

      if (!response.ok) {
        let errMessage = `Error: ${response.status} ${response.statusText}`;
        try {
          const errData = await response.json();
          if (errData && errData.detail) {
            errMessage = Array.isArray(errData.detail)
              ? errData.detail.map((d) => d.msg || JSON.stringify(d)).join(", ")
              : errData.detail;
          }
        } catch (_) {}
        throw new Error(errMessage);
      }

      return await response.json();
    } catch (error) {
      showToast(error.message, "error");
      throw error;
    }
  }

  // =========================================================================
  // TOAST NOTIFICATIONS (WCAG aria-live="polite")
  // =========================================================================

  function showToast(message, type = "info") {
    if (!DOM.toastContainer) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", "status");

    const iconSpan = document.createElement("span");
    iconSpan.style.display = "inline-flex";
    iconSpan.style.alignItems = "center";
    if (type === "success") {
      iconSpan.textContent = "✓";
      iconSpan.style.color = "var(--accent-success)";
    } else if (type === "error") {
      iconSpan.textContent = "✕";
      iconSpan.style.color = "var(--accent-danger)";
    } else if (type === "warning") {
      iconSpan.textContent = "⚠";
      iconSpan.style.color = "var(--accent-warning)";
    } else {
      iconSpan.textContent = "ℹ";
      iconSpan.style.color = "var(--accent-info)";
    }
    toast.appendChild(iconSpan);

    const textSpan = document.createElement("span");
    textSpan.textContent = message;
    toast.appendChild(textSpan);

    DOM.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4200);
  }

  // =========================================================================
  // CELEBRATION CONFETTI BURST (Pure Canvas Micro-interaction)
  // =========================================================================

  function triggerConfetti(originX, originY) {
    const canvas = document.getElementById("confetti-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const count = 75;
    const colors = ["#6366f1", "#a855f7", "#ec4899", "#10b981", "#f59e0b", "#38bdf8", "#ffffff"];
    const particles = [];

    const startX = originX || canvas.width / 2;
    const startY = originY || canvas.height / 3;

    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = Math.random() * 8 + 3;
      particles.push({
        x: startX,
        y: startY,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 4,
        size: Math.random() * 6 + 4,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 10,
        opacity: 1,
        gravity: 0.18,
        drag: 0.98,
      });
    }

    let animationFrame;
    function update() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      let alive = false;

      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.vy += p.gravity;
        p.vx *= p.drag;
        p.vy *= p.drag;
        p.rotation += p.rotationSpeed;
        p.opacity -= 0.012;

        if (p.opacity > 0) {
          alive = true;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate((p.rotation * Math.PI) / 180);
          ctx.globalAlpha = Math.max(p.opacity, 0);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
          ctx.restore();
        }
      });

      if (alive) {
        animationFrame = requestAnimationFrame(update);
      } else {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        cancelAnimationFrame(animationFrame);
      }
    }

    update();
  }

  // =========================================================================
  // MODAL MANAGEMENT & ACCESSIBLE KEYBOARD TRAP
  // =========================================================================

  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    AppState.previousActiveElement = document.activeElement;
    modal.removeAttribute("hidden");

    // Trap focus inside modal
    const focusable = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length > 0) {
      focusable[0].focus();
    }

    modal.addEventListener("keydown", handleModalKeydown);
  }

  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.setAttribute("hidden", "true");
    modal.removeEventListener("keydown", handleModalKeydown);

    if (AppState.previousActiveElement) {
      AppState.previousActiveElement.focus();
    }
  }

  function handleModalKeydown(event) {
    const modal = event.currentTarget;
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal(modal.id);
      return;
    }

    if (event.key === "Tab") {
      const focusable = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length === 0) return;

      const firstElem = focusable[0];
      const lastElem = focusable[focusable.length - 1];

      if (event.shiftKey) {
        if (document.activeElement === firstElem) {
          event.preventDefault();
          lastElem.focus();
        }
      } else {
        if (document.activeElement === lastElem) {
          event.preventDefault();
          firstElem.focus();
        }
      }
    }
  }

  // Bind close buttons with data-close-modal attribute
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-close-modal");
      closeModal(targetId);
    });
  });

  // =========================================================================
  // ACCESSIBLE TAB SWITCHING
  // =========================================================================

  function initTabs() {
    DOM.tabs.forEach((tab) => {
      tab.addEventListener("click", () => switchTab(tab));
      tab.addEventListener("keydown", (e) => {
        const tabList = Array.from(DOM.tabs);
        const index = tabList.indexOf(tab);

        if (e.key === "ArrowRight") {
          const next = tabList[(index + 1) % tabList.length];
          next.focus();
          switchTab(next);
        } else if (e.key === "ArrowLeft") {
          const prev = tabList[(index - 1 + tabList.length) % tabList.length];
          prev.focus();
          switchTab(prev);
        }
      });
    });
  }

  function switchTab(selectedTab) {
    DOM.tabs.forEach((tab) => {
      tab.setAttribute("aria-selected", "false");
      tab.setAttribute("tabindex", "-1");
      tab.classList.remove("active");
    });

    selectedTab.setAttribute("aria-selected", "true");
    selectedTab.setAttribute("tabindex", "0");
    selectedTab.classList.add("active");

    const targetPanelId = selectedTab.getAttribute("aria-controls");
    DOM.panels.forEach((panel) => {
      if (panel.id === targetPanelId) {
        panel.removeAttribute("hidden");
        panel.classList.add("active");
      } else {
        panel.setAttribute("hidden", "true");
        panel.classList.remove("active");
      }
    });

    AppState.activeTabId = selectedTab.id;

    if (targetPanelId === "panel-analytics") {
      loadAnalytics();
    } else if (targetPanelId === "panel-vendors") {
      loadVendors();
    }
  }

  // =========================================================================
  // EVENT MANAGEMENT & DATA RENDERING
  // =========================================================================

  async function loadEvents() {
    const searchVal = DOM.eventSearch ? DOM.eventSearch.value.trim() : "";
    const catVal = DOM.filterCategory ? DOM.filterCategory.value : "";
    const statusVal = DOM.filterStatus ? DOM.filterStatus.value : "";

    const params = new URLSearchParams();
    if (searchVal) params.append("search", searchVal);
    if (catVal) params.append("category", catVal);
    if (statusVal) params.append("status", statusVal);

    try {
      const data = await apiFetch(`/api/events?${params.toString()}`);
      AppState.events = data.items || [];
      renderEventsSelector();
      renderEventsGrid();

      if (DOM.eventsCountBadge) {
        const count = AppState.events.length;
        DOM.eventsCountBadge.textContent = `${count} ${count === 1 ? "Celebration" : "Celebrations"}`;
      }

      if (AppState.events.length > 0 && !AppState.activeEventId) {
        await selectActiveEvent(AppState.events[0].id);
      } else if (AppState.activeEventId) {
        await selectActiveEvent(AppState.activeEventId);
      }
    } catch (_) {}
  }

  function renderEventsSelector() {
    if (!DOM.eventSelector) return;
    DOM.eventSelector.innerHTML = "";

    if (AppState.events.length === 0) {
      const opt = document.createElement("option");
      opt.textContent = "No events found";
      opt.value = "";
      DOM.eventSelector.appendChild(opt);
      return;
    }

    const fragment = document.createDocumentFragment();
    AppState.events.forEach((ev) => {
      const opt = document.createElement("option");
      opt.value = ev.id;
      opt.textContent = `${ev.title} (${ev.category})`;
      if (ev.id === AppState.activeEventId) {
        opt.selected = true;
      }
      fragment.appendChild(opt);
    });
    DOM.eventSelector.appendChild(fragment);
  }

  function renderEventsGrid() {
    if (!DOM.eventsGrid) return;
    DOM.eventsGrid.innerHTML = "";

    if (AppState.events.length === 0) {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "empty-state-box";
      emptyDiv.style.gridColumn = "1 / -1";
      emptyDiv.innerHTML = `
        <div class="empty-state-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        </div>
        <h4 class="empty-state-title">No Celebration Events Found</h4>
        <p class="empty-state-desc">Try clearing your search keyword or category filter, or create a brand new celebration.</p>
      `;
      DOM.eventsGrid.appendChild(emptyDiv);
      return;
    }

    const fragment = document.createDocumentFragment();

    AppState.events.forEach((ev) => {
      const card = document.createElement("article");
      const isActive = ev.id === AppState.activeEventId;
      card.className = `event-card ${isActive ? "is-active-card" : ""}`;
      card.style.setProperty("--card-color", ev.theme_color || "#6366f1");

      const topBar = document.createElement("div");
      topBar.className = "card-top";
      card.appendChild(topBar);

      const headerDiv = document.createElement("div");
      headerDiv.className = "banner-header";

      const catBadge = document.createElement("span");
      catBadge.className = "badge badge-accent";
      catBadge.textContent = ev.category;

      const statusWrap = document.createElement("div");
      statusWrap.style.display = "flex";
      statusWrap.style.alignItems = "center";
      statusWrap.style.gap = "0.4rem";

      if (isActive) {
        const activePill = document.createElement("span");
        activePill.className = "active-event-indicator-pill";
        const dot = document.createElement("span");
        dot.className = "active-pulse-dot";
        activePill.appendChild(dot);
        activePill.appendChild(document.createTextNode("Active"));
        statusWrap.appendChild(activePill);
      }

      const statusBadge = document.createElement("span");
      statusBadge.className = "badge badge-status";
      statusBadge.textContent = ev.status;
      statusWrap.appendChild(statusBadge);

      headerDiv.appendChild(catBadge);
      headerDiv.appendChild(statusWrap);
      card.appendChild(headerDiv);

      const titleEl = document.createElement("h4");
      titleEl.className = "card-title";
      titleEl.textContent = ev.title;
      card.appendChild(titleEl);

      const descEl = document.createElement("p");
      descEl.className = "card-desc";
      descEl.textContent = ev.description || "No description provided.";
      card.appendChild(descEl);

      const metaDiv = document.createElement("div");
      metaDiv.className = "banner-meta";
      metaDiv.style.marginBottom = "0.75rem";
      metaDiv.style.paddingBottom = "0.75rem";

      const dateItem = document.createElement("div");
      dateItem.className = "meta-item";
      const dt = new Date(ev.event_date);
      dateItem.textContent = `📅 ${dt.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;
      metaDiv.appendChild(dateItem);

      const venueItem = document.createElement("div");
      venueItem.className = "meta-item";
      venueItem.textContent = `📍 ${ev.venue}`;
      metaDiv.appendChild(venueItem);

      card.appendChild(metaDiv);

      // Capacity & Budget info strip
      const statsStrip = document.createElement("div");
      statsStrip.style.display = "flex";
      statsStrip.style.justifyContent = "space-between";
      statsStrip.style.fontSize = "0.82rem";
      statsStrip.style.color = "var(--text-muted)";
      statsStrip.style.marginTop = "0.5rem";

      const budgetSpan = document.createElement("span");
      budgetSpan.textContent = `Budget: $${ev.total_budget.toLocaleString()}`;
      const capSpan = document.createElement("span");
      capSpan.textContent = `Capacity: ${ev.capacity} guests`;
      statsStrip.appendChild(budgetSpan);
      statsStrip.appendChild(capSpan);
      card.appendChild(statsStrip);

      // Mini Capacity Bar
      const capBarWrap = document.createElement("div");
      capBarWrap.className = "card-capacity-bar-wrap";
      const capBar = document.createElement("div");
      capBar.className = "card-capacity-bar";
      capBar.style.width = "40%";
      capBarWrap.appendChild(capBar);
      card.appendChild(capBarWrap);

      const footerDiv = document.createElement("div");
      footerDiv.className = "card-footer-actions";

      const selectBtn = document.createElement("button");
      selectBtn.type = "button";
      selectBtn.className = isActive ? "btn btn-secondary btn-sm" : "btn btn-primary btn-sm";
      selectBtn.textContent = isActive ? "✓ Current Active" : "Select Event";
      selectBtn.addEventListener("click", () => {
        selectActiveEvent(ev.id);
        showToast(`Switched active celebration to "${ev.title}"`, "success");
      });
      footerDiv.appendChild(selectBtn);

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "btn btn-danger-outline btn-sm";
      deleteBtn.textContent = "Delete";
      deleteBtn.addEventListener("click", async () => {
        if (confirm(`Are you sure you want to delete "${ev.title}"?`)) {
          await deleteEvent(ev.id);
        }
      });
      footerDiv.appendChild(deleteBtn);

      card.appendChild(footerDiv);
      fragment.appendChild(card);
    });

    DOM.eventsGrid.appendChild(fragment);
  }

  async function selectActiveEvent(eventId) {
    try {
      const detail = await apiFetch(`/api/events/${eventId}`);
      AppState.activeEventId = eventId;
      AppState.activeEventDetail = detail;

      updateActiveBanner(detail);
      renderGuestsTable(detail.guests || []);
      renderGuestQuickStats(detail.guests || []);
      renderExpensesTable(detail.expenses || []);
      renderCategoryStackedBar(detail.expenses || []);
      renderTasksList(detail.tasks || []);

      if (DOM.eventSelector) {
        DOM.eventSelector.value = eventId;
      }
      renderEventsGrid();
    } catch (_) {}
  }

  // =========================================================================
  // DYNAMIC COUNTDOWN CALCULATOR
  // =========================================================================

  function updateCountdown(eventDateStr) {
    if (!DOM.bannerCountdown) return;

    if (!eventDateStr) {
      DOM.bannerCountdown.textContent = "🗓️ Date TBD";
      DOM.bannerCountdown.className = "badge badge-pill";
      return;
    }

    const eventDate = new Date(eventDateStr);
    const now = new Date();
    const diffMs = eventDate.getTime() - now.getTime();

    if (diffMs > 0) {
      const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      if (days > 0) {
        DOM.bannerCountdown.textContent = `⏳ ${days}d ${hours}h remaining`;
        DOM.bannerCountdown.className = "badge badge-pill";
      } else if (hours > 0) {
        DOM.bannerCountdown.textContent = `⏳ ${hours}h ${minutes}m left!`;
        DOM.bannerCountdown.className = "badge badge-accent";
      } else {
        DOM.bannerCountdown.textContent = `⏳ ${minutes}m left! Starting soon!`;
        DOM.bannerCountdown.className = "badge badge-status";
      }
    } else {
      const isToday = eventDate.toDateString() === now.toDateString();
      if (isToday) {
        DOM.bannerCountdown.textContent = "🎉 Happening Today!";
        DOM.bannerCountdown.className = "badge badge-status";
      } else {
        const daysAgo = Math.floor(Math.abs(diffMs) / (1000 * 60 * 60 * 24));
        DOM.bannerCountdown.textContent = daysAgo === 0 ? "🏁 Just Concluded" : `🏁 ${daysAgo}d ago`;
        DOM.bannerCountdown.className = "badge badge-pill";
      }
    }
  }

  // =========================================================================
  // ACTIVE HERO BANNER & RADIAL GAUGES
  // =========================================================================

  function updateActiveBanner(detail) {
    const { event, budget_summary, rsvp_summary, task_summary } = detail;
    if (!event) return;

    if (DOM.bannerTitle) DOM.bannerTitle.textContent = event.title;
    if (DOM.bannerDesc) DOM.bannerDesc.textContent = event.description || "No description provided.";
    if (DOM.bannerCategory) DOM.bannerCategory.textContent = event.category;
    if (DOM.bannerStatus) DOM.bannerStatus.textContent = event.status;

    // Countdown update
    updateCountdown(event.event_date);
    clearInterval(AppState.countdownInterval);
    AppState.countdownInterval = setInterval(() => {
      updateCountdown(event.event_date);
    }, 60000);

    const eventDate = new Date(event.event_date);
    if (DOM.bannerDatetime) {
      DOM.bannerDatetime.textContent = eventDate.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    }
    if (DOM.bannerVenue) DOM.bannerVenue.textContent = event.venue;

    if (DOM.activeEventCard && event.theme_color) {
      DOM.activeEventCard.style.setProperty("--active-theme", event.theme_color);
    }

    // Over-Budget Alert Banner Toggle
    if (DOM.overBudgetAlert && DOM.overBudgetText) {
      if (budget_summary.is_over_budget || budget_summary.burn_rate_pct > 100) {
        const overspend = (budget_summary.total_actual - budget_summary.total_budget).toFixed(2);
        DOM.overBudgetText.textContent = `Critical: Actual expenses ($${budget_summary.total_actual.toFixed(2)}) exceed total budget ($${budget_summary.total_budget.toFixed(2)}) by $${overspend}! (${budget_summary.burn_rate_pct}% burn rate)`;
        DOM.overBudgetAlert.removeAttribute("hidden");
      } else {
        DOM.overBudgetAlert.setAttribute("hidden", "true");
      }
    }

    // SVG Radial Ring Math (Circumference: 2 * pi * 18 = 113.1)
    const CIRCUMFERENCE = 113.1;

    // 1. Budget Metrics & Radial Gauge
    if (DOM.metricBudgetTotal) {
      DOM.metricBudgetTotal.textContent = `$${budget_summary.total_budget.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    }
    if (DOM.metricBudgetBurn) {
      DOM.metricBudgetBurn.textContent = `Spent: $${budget_summary.total_actual.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${budget_summary.burn_rate_pct}%)`;
    }
    if (DOM.metricBudgetRemaining) {
      DOM.metricBudgetRemaining.textContent = `$${budget_summary.remaining_budget.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
    }
    if (DOM.metricBudgetPendingSub) {
      const pendingAmt = Math.max(0, budget_summary.total_actual - (budget_summary.total_paid || 0));
      DOM.metricBudgetPendingSub.textContent = `$${pendingAmt.toFixed(2)} pending payment`;
    }
    if (DOM.metricBudgetStatus) {
      if (budget_summary.is_over_budget) {
        DOM.metricBudgetStatus.textContent = "Over Budget!";
        DOM.metricBudgetStatus.className = "status-indicator-pill status-danger";
      } else if (budget_summary.burn_rate_pct >= 85) {
        DOM.metricBudgetStatus.textContent = "Near Limit";
        DOM.metricBudgetStatus.className = "status-indicator-pill status-warning";
      } else {
        DOM.metricBudgetStatus.textContent = "On Track";
        DOM.metricBudgetStatus.className = "status-indicator-pill status-on-track";
      }
    }

    const burnPct = Math.round(budget_summary.burn_rate_pct || 0);
    const clampedBurn = Math.min(burnPct, 100);
    const burnOffset = CIRCUMFERENCE - (clampedBurn / 100) * CIRCUMFERENCE;

    if (DOM.budgetBurnRing) {
      DOM.budgetBurnRing.style.strokeDashoffset = `${burnOffset}`;
      if (burnPct > 100) {
        DOM.budgetBurnRing.style.stroke = "var(--accent-danger)";
      } else if (burnPct >= 85) {
        DOM.budgetBurnRing.style.stroke = "var(--accent-warning)";
      } else {
        DOM.budgetBurnRing.style.stroke = "var(--accent-primary)";
      }
    }
    if (DOM.budgetRingPct) DOM.budgetRingPct.textContent = `${burnPct}%`;
    if (DOM.budgetBurnProgressBar) {
      DOM.budgetBurnProgressBar.style.width = `${Math.min(burnPct, 100)}%`;
      if (burnPct > 100) {
        DOM.budgetBurnProgressBar.style.backgroundColor = "var(--accent-danger)";
      } else if (burnPct >= 85) {
        DOM.budgetBurnProgressBar.style.backgroundColor = "var(--accent-warning)";
      } else {
        DOM.budgetBurnProgressBar.style.backgroundColor = "var(--accent-primary)";
      }
    }

    // 2. RSVP Attendance & Headcount Radial Gauge
    if (DOM.metricRsvpCount) {
      DOM.metricRsvpCount.textContent = `${rsvp_summary.total_attendees} / ${rsvp_summary.capacity}`;
    }
    if (DOM.metricRsvpCap) {
      DOM.metricRsvpCap.textContent = `${rsvp_summary.capacity_utilization_pct}% Capacity Used`;
    }

    const rsvpPct = Math.round(rsvp_summary.capacity_utilization_pct || 0);
    const clampedRsvp = Math.min(rsvpPct, 100);
    const rsvpOffset = CIRCUMFERENCE - (clampedRsvp / 100) * CIRCUMFERENCE;

    if (DOM.rsvpCapRing) {
      DOM.rsvpCapRing.style.strokeDashoffset = `${rsvpOffset}`;
      if (rsvpPct >= 100) {
        DOM.rsvpCapRing.style.stroke = "var(--accent-warning)";
      } else {
        DOM.rsvpCapRing.style.stroke = "var(--accent-info)";
      }
    }
    if (DOM.rsvpRingPct) DOM.rsvpRingPct.textContent = `${rsvpPct}%`;
    if (DOM.rsvpProgressBar) {
      DOM.rsvpProgressBar.style.width = `${clampedRsvp}%`;
      if (rsvpPct >= 100) {
        DOM.rsvpProgressBar.style.backgroundColor = "var(--accent-warning)";
      } else {
        DOM.rsvpProgressBar.style.backgroundColor = "var(--accent-info)";
      }
    }

    // 3. Task Progress & Checklist Radial Gauge
    if (DOM.metricTaskPct) {
      DOM.metricTaskPct.textContent = `${task_summary.completion_rate_pct}%`;
    }
    if (DOM.metricTaskCount) {
      DOM.metricTaskCount.textContent = `${task_summary.completed_tasks} of ${task_summary.total_tasks} Completed`;
    }

    const taskPct = Math.round(task_summary.completion_rate_pct || 0);
    const clampedTask = Math.min(taskPct, 100);
    const taskOffset = CIRCUMFERENCE - (clampedTask / 100) * CIRCUMFERENCE;

    if (DOM.taskProgressRing) {
      DOM.taskProgressRing.style.strokeDashoffset = `${taskOffset}`;
    }
    if (DOM.taskRingPct) DOM.taskRingPct.textContent = `${taskPct}%`;
    if (DOM.taskProgressBar) {
      DOM.taskProgressBar.style.width = `${clampedTask}%`;
    }
  }

  // =========================================================================
  // GUEST & RSVP TRACKING WITH QUICK-STATS & INLINE STATUS SWITCHER
  // =========================================================================

  function renderGuestQuickStats(guests) {
    const gList = guests || [];
    const total = gList.length;
    let attendingCount = 0;
    let pendingCount = 0;
    let declinedCount = 0;
    let dietsCount = 0;

    gList.forEach((g) => {
      if (g.rsvp_status === "Attending") {
        attendingCount += 1 + (g.plus_one_count || 0);
      } else if (g.rsvp_status === "Declined") {
        declinedCount += 1;
      } else {
        pendingCount += 1;
      }

      if (g.dietary_preferences && g.dietary_preferences !== "None") {
        dietsCount += 1;
      }
    });

    if (DOM.gstatTotal) DOM.gstatTotal.textContent = total;
    if (DOM.gstatAttending) DOM.gstatAttending.textContent = attendingCount;
    if (DOM.gstatPending) DOM.gstatPending.textContent = pendingCount;
    if (DOM.gstatDeclined) DOM.gstatDeclined.textContent = declinedCount;
    if (DOM.gstatDiets) DOM.gstatDiets.textContent = dietsCount;
  }

  function renderGuestsTable(guests) {
    if (!DOM.guestsTableBody) return;
    DOM.guestsTableBody.innerHTML = "";

    const allGuests = guests || [];
    const search = (AppState.guestSearchQuery || "").toLowerCase();
    const rsvpFilter = AppState.guestFilterRsvp || "";

    const filtered = allGuests.filter((g) => {
      if (rsvpFilter && g.rsvp_status !== rsvpFilter) return false;
      if (search) {
        const matchesName = (g.name || "").toLowerCase().includes(search);
        const matchesEmail = (g.email || "").toLowerCase().includes(search);
        const matchesDiet = (g.dietary_preferences || "").toLowerCase().includes(search);
        if (!matchesName && !matchesEmail && !matchesDiet) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 7;
      td.style.textAlign = "center";
      td.style.padding = "2.5rem 1rem";
      td.style.color = "var(--text-muted)";
      td.textContent = allGuests.length === 0
        ? "No guests registered for this celebration yet. Click '+ Add Guest' to begin."
        : "No guests match your active search or RSVP filter.";
      tr.appendChild(td);
      DOM.guestsTableBody.appendChild(tr);
      return;
    }

    const fragment = document.createDocumentFragment();

    filtered.forEach((g) => {
      const tr = document.createElement("tr");

      // Name with visual Avatar badge
      const tdName = document.createElement("td");
      const nameWrap = document.createElement("div");
      nameWrap.style.display = "flex";
      nameWrap.style.alignItems = "center";
      nameWrap.style.gap = "0.75rem";

      const avatar = document.createElement("span");
      avatar.style.width = "32px";
      avatar.style.height = "32px";
      avatar.style.borderRadius = "50%";
      avatar.style.display = "inline-flex";
      avatar.style.alignItems = "center";
      avatar.style.justifyContent = "center";
      avatar.style.fontSize = "0.82rem";
      avatar.style.fontWeight = "bold";
      avatar.style.background = getAvatarGradient(g.name);
      avatar.style.color = "#ffffff";
      avatar.style.boxShadow = "0 2px 8px rgba(0, 0, 0, 0.3)";
      avatar.textContent = g.name.charAt(0).toUpperCase();

      const textWrap = document.createElement("div");
      const nameText = document.createElement("strong");
      nameText.style.display = "block";
      nameText.style.color = "var(--text-primary)";
      nameText.textContent = g.name;

      textWrap.appendChild(nameText);
      nameWrap.appendChild(avatar);
      nameWrap.appendChild(textWrap);
      tdName.appendChild(nameWrap);
      tr.appendChild(tdName);

      // Contact
      const tdContact = document.createElement("td");
      tdContact.textContent = g.phone ? `${g.email} • ${g.phone}` : g.email;
      tr.appendChild(tdContact);

      // Dietary
      const tdDiet = document.createElement("td");
      if (g.dietary_preferences && g.dietary_preferences !== "None") {
        const dietBadge = document.createElement("span");
        dietBadge.className = "badge badge-accent";
        dietBadge.textContent = `🥗 ${g.dietary_preferences}`;
        tdDiet.appendChild(dietBadge);
      } else {
        tdDiet.textContent = "Standard";
        tdDiet.style.color = "var(--text-muted)";
      }
      tr.appendChild(tdDiet);

      // Interactive Inline RSVP Switcher Dropdown
      const tdRsvp = document.createElement("td");
      const rsvpSelect = document.createElement("select");
      rsvpSelect.className = "form-control form-control-sm";
      rsvpSelect.style.padding = "0.3rem 0.6rem";
      rsvpSelect.style.fontSize = "0.82rem";
      rsvpSelect.style.borderRadius = "var(--radius-sm)";
      rsvpSelect.style.fontWeight = "600";
      rsvpSelect.style.cursor = "pointer";
      rsvpSelect.setAttribute("aria-label", `Change RSVP status for ${g.name}`);

      ["Attending", "Pending", "Declined"].forEach((status) => {
        const opt = document.createElement("option");
        opt.value = status;
        opt.textContent = `● ${status}`;
        if (g.rsvp_status === status) opt.selected = true;
        rsvpSelect.appendChild(opt);
      });

      function styleRsvpSelect(selectEl, status) {
        if (status === "Attending") {
          selectEl.style.borderColor = "var(--accent-success)";
          selectEl.style.color = "var(--accent-success)";
          selectEl.style.background = "rgba(16, 185, 129, 0.12)";
        } else if (status === "Declined") {
          selectEl.style.borderColor = "var(--accent-danger)";
          selectEl.style.color = "var(--accent-danger)";
          selectEl.style.background = "rgba(239, 68, 68, 0.12)";
        } else {
          selectEl.style.borderColor = "var(--accent-warning)";
          selectEl.style.color = "var(--accent-warning)";
          selectEl.style.background = "rgba(245, 158, 11, 0.12)";
        }
      }
      styleRsvpSelect(rsvpSelect, g.rsvp_status);

      rsvpSelect.addEventListener("change", async (e) => {
        const newStatus = e.target.value;
        try {
          await apiFetch(`/api/guests/${g.id}`, {
            method: "PUT",
            body: JSON.stringify({ rsvp_status: newStatus }),
          });
          showToast(`Updated ${g.name}'s RSVP to "${newStatus}"`, "success");
          styleRsvpSelect(rsvpSelect, newStatus);
          await selectActiveEvent(AppState.activeEventId);
        } catch (err) {
          // Revert on error (e.g., capacity exceeded)
          rsvpSelect.value = g.rsvp_status;
          styleRsvpSelect(rsvpSelect, g.rsvp_status);
        }
      });

      tdRsvp.appendChild(rsvpSelect);
      tr.appendChild(tdRsvp);

      // Plus Ones
      const tdPlus = document.createElement("td");
      if (g.plus_one_count > 0) {
        const plusBadge = document.createElement("span");
        plusBadge.className = "badge badge-pill";
        plusBadge.textContent = `+${g.plus_one_count}`;
        tdPlus.appendChild(plusBadge);
      } else {
        tdPlus.textContent = "0";
        tdPlus.style.color = "var(--text-muted)";
      }
      tr.appendChild(tdPlus);

      // Notes
      const tdNotes = document.createElement("td");
      tdNotes.textContent = g.notes || "-";
      tdNotes.style.maxWidth = "180px";
      tdNotes.style.overflow = "hidden";
      tdNotes.style.textOverflow = "ellipsis";
      tdNotes.style.whiteSpace = "nowrap";
      tr.appendChild(tdNotes);

      // Actions
      const tdActions = document.createElement("td");
      tdActions.className = "text-right";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-secondary btn-sm";
      editBtn.textContent = "Edit";
      editBtn.style.marginRight = "0.4rem";
      editBtn.addEventListener("click", () => populateGuestEdit(g));
      tdActions.appendChild(editBtn);

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-danger-outline btn-sm";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", async () => {
        if (confirm(`Remove guest ${g.name}?`)) {
          await deleteGuest(g.id);
        }
      });
      tdActions.appendChild(delBtn);

      tr.appendChild(tdActions);
      fragment.appendChild(tr);
    });

    DOM.guestsTableBody.appendChild(fragment);
  }

  function populateGuestEdit(guest) {
    document.getElementById("guest-form-id").value = guest.id;
    document.getElementById("guest-name").value = guest.name;
    document.getElementById("guest-email").value = guest.email;
    document.getElementById("guest-phone").value = guest.phone || "";
    document.getElementById("guest-rsvp").value = guest.rsvp_status;
    document.getElementById("guest-plus-ones").value = guest.plus_one_count;
    document.getElementById("guest-dietary").value = guest.dietary_preferences;
    document.getElementById("guest-notes").value = guest.notes || "";

    document.getElementById("modal-guest-title").textContent = "Edit Guest Details";
    openModal("modal-guest");
  }

  async function deleteGuest(guestId) {
    try {
      await apiFetch(`/api/guests/${guestId}`, { method: "DELETE" });
      showToast("Guest removed successfully", "success");
      await selectActiveEvent(AppState.activeEventId);
    } catch (_) {}
  }

  // =========================================================================
  // BUDGET & EXPENSES ENGINE WITH STACKED CATEGORY VISUALIZER
  // =========================================================================

  function renderCategoryStackedBar(expenses) {
    if (!DOM.categoryStackedBar || !DOM.categoryStackedLegend) return;
    DOM.categoryStackedBar.innerHTML = "";
    DOM.categoryStackedLegend.innerHTML = "";

    const totalSpent = (expenses || []).reduce((acc, ex) => acc + (ex.actual_cost || 0), 0);
    if (DOM.breakdownTotalSpentTag) {
      DOM.breakdownTotalSpentTag.textContent = `Total Spent: $${totalSpent.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    if (!expenses || expenses.length === 0 || totalSpent === 0) {
      const emptySeg = document.createElement("div");
      emptySeg.className = "stacked-seg";
      emptySeg.style.width = "100%";
      emptySeg.style.background = "rgba(255, 255, 255, 0.08)";
      emptySeg.title = "No expenses logged";
      DOM.categoryStackedBar.appendChild(emptySeg);

      const emptyLegend = document.createElement("span");
      emptyLegend.textContent = "No itemized expenses recorded.";
      emptyLegend.style.color = "var(--text-muted)";
      DOM.categoryStackedLegend.appendChild(emptyLegend);
      return;
    }

    // Aggregate expenditures by category
    const catSums = {};
    expenses.forEach((ex) => {
      const cat = ex.category || "Other";
      catSums[cat] = (catSums[cat] || 0) + (ex.actual_cost || 0);
    });

    const barFragment = document.createDocumentFragment();
    const legendFragment = document.createDocumentFragment();

    Object.entries(catSums).forEach(([cat, sum]) => {
      if (sum <= 0) return;
      const pct = ((sum / totalSpent) * 100).toFixed(1);
      const color = CATEGORY_COLORS[cat] || "#6366f1";

      // Segment in horizontal bar
      const seg = document.createElement("div");
      seg.className = "stacked-seg";
      seg.style.width = `${pct}%`;
      seg.style.backgroundColor = color;
      seg.title = `${cat}: $${sum.toFixed(2)} (${pct}%) — click to filter`;
      seg.style.cursor = "pointer";
      seg.addEventListener("click", () => {
        if (DOM.expenseSearchInput) {
          DOM.expenseSearchInput.value = cat;
          AppState.expenseSearchQuery = cat;
          if (AppState.activeEventDetail) {
            renderExpensesTable(AppState.activeEventDetail.expenses || []);
          }
        }
      });
      barFragment.appendChild(seg);

      // Legend chip
      const item = document.createElement("div");
      item.className = "legend-item";
      item.style.cursor = "pointer";
      item.title = `Click to filter by ${cat}`;
      item.addEventListener("click", () => {
        if (DOM.expenseSearchInput) {
          DOM.expenseSearchInput.value = cat;
          AppState.expenseSearchQuery = cat;
          if (AppState.activeEventDetail) {
            renderExpensesTable(AppState.activeEventDetail.expenses || []);
          }
        }
      });

      const dot = document.createElement("span");
      dot.className = "legend-dot";
      dot.style.backgroundColor = color;

      const label = document.createElement("span");
      label.textContent = `${cat}: $${sum.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${pct}%)`;

      item.appendChild(dot);
      item.appendChild(label);
      legendFragment.appendChild(item);
    });

    DOM.categoryStackedBar.appendChild(barFragment);
    DOM.categoryStackedLegend.appendChild(legendFragment);
  }

  function renderExpensesTable(expenses) {
    if (!DOM.expensesTableBody) return;
    DOM.expensesTableBody.innerHTML = "";

    const allExpenses = expenses || [];
    const search = (AppState.expenseSearchQuery || "").toLowerCase();
    const statusFilter = AppState.expenseFilterStatus || "";

    const filtered = allExpenses.filter((ex) => {
      if (statusFilter === "paid" && !ex.is_paid) return false;
      if (statusFilter === "pending" && ex.is_paid) return false;
      if (search) {
        const matchesName = (ex.item_name || "").toLowerCase().includes(search);
        const matchesCat = (ex.category || "").toLowerCase().includes(search);
        if (!matchesName && !matchesCat) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 8;
      td.style.textAlign = "center";
      td.style.padding = "2.5rem 1rem";
      td.style.color = "var(--text-muted)";
      td.textContent = allExpenses.length === 0
        ? "No itemized expenses recorded yet. Click '+ Log Expense' to add line items."
        : "No expenses match your active filter keyword or payment state.";
      tr.appendChild(td);
      DOM.expensesTableBody.appendChild(tr);
      return;
    }

    const fragment = document.createDocumentFragment();

    filtered.forEach((ex) => {
      const tr = document.createElement("tr");

      // Line Item
      const tdItem = document.createElement("td");
      const itemSpan = document.createElement("strong");
      itemSpan.style.color = "var(--text-primary)";
      itemSpan.textContent = ex.item_name;
      tdItem.appendChild(itemSpan);
      tr.appendChild(tdItem);

      // Category
      const tdCat = document.createElement("td");
      const catBadge = document.createElement("span");
      catBadge.className = "badge";
      const catColor = CATEGORY_COLORS[ex.category] || "#6366f1";
      catBadge.style.backgroundColor = `${catColor}20`;
      catBadge.style.color = catColor;
      catBadge.style.border = `1px solid ${catColor}50`;
      catBadge.textContent = ex.category;
      tdCat.appendChild(catBadge);
      tr.appendChild(tdCat);

      // Estimated
      const tdEst = document.createElement("td");
      tdEst.textContent = `$${ex.estimated_cost.toFixed(2)}`;
      tr.appendChild(tdEst);

      // Actual
      const tdAct = document.createElement("td");
      tdAct.textContent = `$${ex.actual_cost.toFixed(2)}`;
      if (ex.actual_cost > ex.estimated_cost && ex.estimated_cost > 0) {
        const diff = (ex.actual_cost - ex.estimated_cost).toFixed(2);
        tdAct.style.color = "var(--accent-warning)";
        tdAct.title = `Exceeds estimated by +$${diff}`;
      }
      tr.appendChild(tdAct);

      // Payment State Toggle Button
      const tdPaid = document.createElement("td");
      const togglePayBtn = document.createElement("button");
      togglePayBtn.type = "button";
      togglePayBtn.className = `badge ${ex.is_paid ? "badge-status" : "badge-accent"}`;
      togglePayBtn.style.cursor = "pointer";
      togglePayBtn.style.border = "none";
      togglePayBtn.style.fontFamily = "inherit";
      togglePayBtn.title = "Click to toggle payment settlement";
      togglePayBtn.textContent = ex.is_paid ? "● PAID" : "○ PENDING";

      togglePayBtn.addEventListener("click", async () => {
        await apiFetch(`/api/expenses/${ex.id}`, {
          method: "PUT",
          body: JSON.stringify({ is_paid: !ex.is_paid }),
        });
        showToast(`Marked "${ex.item_name}" as ${!ex.is_paid ? "Paid" : "Pending"}`, "success");
        await selectActiveEvent(AppState.activeEventId);
      });

      tdPaid.appendChild(togglePayBtn);
      tr.appendChild(tdPaid);

      // Due Date
      const tdDue = document.createElement("td");
      tdDue.textContent = ex.due_date || "-";
      tr.appendChild(tdDue);

      // Notes
      const tdNotes = document.createElement("td");
      tdNotes.textContent = ex.notes || "-";
      tdNotes.style.maxWidth = "180px";
      tdNotes.style.overflow = "hidden";
      tdNotes.style.textOverflow = "ellipsis";
      tdNotes.style.whiteSpace = "nowrap";
      tr.appendChild(tdNotes);

      // Actions
      const tdActions = document.createElement("td");
      tdActions.className = "text-right";

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-danger-outline btn-sm";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", async () => {
        if (confirm(`Delete expense line item "${ex.item_name}"?`)) {
          await deleteExpense(ex.id);
        }
      });
      tdActions.appendChild(delBtn);

      tr.appendChild(tdActions);
      fragment.appendChild(tr);
    });

    DOM.expensesTableBody.appendChild(fragment);
  }

  async function deleteExpense(expenseId) {
    try {
      await apiFetch(`/api/expenses/${expenseId}`, { method: "DELETE" });
      showToast("Expense line item deleted", "success");
      await selectActiveEvent(AppState.activeEventId);
    } catch (_) {}
  }

  // =========================================================================
  // TIMELINE & CHECKLIST TASKS WITH STATUS FILTERS
  // =========================================================================

  function renderTasksList(tasks) {
    if (!DOM.tasksList) return;
    DOM.tasksList.innerHTML = "";

    const allTasks = tasks || [];
    let filteredTasks = allTasks;

    if (AppState.activeTaskFilter === "pending") {
      filteredTasks = allTasks.filter((t) => !t.is_completed);
    } else if (AppState.activeTaskFilter === "completed") {
      filteredTasks = allTasks.filter((t) => t.is_completed);
    } else if (AppState.activeTaskFilter === "high") {
      filteredTasks = allTasks.filter((t) => t.priority === "High");
    }

    if (filteredTasks.length === 0) {
      const li = document.createElement("li");
      li.className = "empty-state-box";
      li.style.padding = "2.5rem 1rem";
      li.innerHTML = `
        <div class="empty-state-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
        </div>
        <h4 class="empty-state-title">No Checklist Tasks Found</h4>
        <p class="empty-state-desc">No milestone tasks match the selected filter category.</p>
      `;
      DOM.tasksList.appendChild(li);
      return;
    }

    const fragment = document.createDocumentFragment();

    filteredTasks.forEach((t) => {
      const li = document.createElement("li");
      li.className = `task-item ${t.is_completed ? "completed" : ""}`;

      const leftDiv = document.createElement("div");
      leftDiv.className = "task-left";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-checkbox";
      checkbox.checked = t.is_completed;
      checkbox.setAttribute("aria-label", `Mark task "${t.title}" complete`);
      checkbox.addEventListener("change", async (e) => {
        const isChecked = checkbox.checked;
        await apiFetch(`/api/tasks/${t.id}`, {
          method: "PUT",
          body: JSON.stringify({ is_completed: isChecked }),
        });
        showToast(
          isChecked ? `Task marked completed!` : `Task marked pending.`,
          "success"
        );

        // Check if all tasks are completed to trigger celebration confetti
        if (isChecked && AppState.activeEventDetail && AppState.activeEventDetail.tasks) {
          const remainingIncomplete = AppState.activeEventDetail.tasks.filter(
            (taskItem) => taskItem.id !== t.id && !taskItem.is_completed
          );
          if (remainingIncomplete.length === 0) {
            triggerConfetti(e.clientX, e.clientY);
            showToast("🎉 All milestone tasks completed! Congratulations!", "success");
          }
        }

        await selectActiveEvent(AppState.activeEventId);
      });
      leftDiv.appendChild(checkbox);

      const textWrap = document.createElement("div");

      const titleSpan = document.createElement("div");
      titleSpan.className = "task-title";
      titleSpan.textContent = t.title;
      textWrap.appendChild(titleSpan);

      const metaDiv = document.createElement("div");
      metaDiv.className = "task-meta-info";

      const prioritySpan = document.createElement("span");
      prioritySpan.className = `priority-${t.priority.toLowerCase()}`;
      prioritySpan.textContent = `${t.priority} Priority`;
      metaDiv.appendChild(prioritySpan);

      if (t.due_date) {
        const dueSpan = document.createElement("span");
        dueSpan.textContent = `• Due ${t.due_date}`;
        metaDiv.appendChild(dueSpan);
      }

      if (t.assignee) {
        const assignSpan = document.createElement("span");
        assignSpan.textContent = `• Assignee: ${t.assignee}`;
        metaDiv.appendChild(assignSpan);
      }

      if (t.category && t.category !== "General") {
        const catSpan = document.createElement("span");
        catSpan.textContent = `• ${t.category}`;
        metaDiv.appendChild(catSpan);
      }

      textWrap.appendChild(metaDiv);
      leftDiv.appendChild(textWrap);
      li.appendChild(leftDiv);

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-danger-outline btn-sm";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", async () => {
        if (confirm(`Delete milestone "${t.title}"?`)) {
          await deleteTask(t.id);
        }
      });
      li.appendChild(delBtn);

      fragment.appendChild(li);
    });

    DOM.tasksList.appendChild(fragment);
  }

  async function deleteTask(taskId) {
    try {
      await apiFetch(`/api/tasks/${taskId}`, { method: "DELETE" });
      showToast("Milestone task deleted", "success");
      await selectActiveEvent(AppState.activeEventId);
    } catch (_) {}
  }

  // =========================================================================
  // VENDOR DIRECTORY
  // =========================================================================

  async function loadVendors() {
    try {
      const data = await apiFetch("/api/vendors?limit=50");
      AppState.vendors = data.items || [];
      renderVendorsGrid();
    } catch (_) {}
  }

  function renderVendorsGrid() {
    if (!DOM.vendorsGrid) return;
    DOM.vendorsGrid.innerHTML = "";

    if (AppState.vendors.length === 0) {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "empty-state-box";
      emptyDiv.style.gridColumn = "1 / -1";
      emptyDiv.innerHTML = `
        <div class="empty-state-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path></svg>
        </div>
        <h4 class="empty-state-title">No Commercial Vendors Registered</h4>
        <p class="empty-state-desc">Click 'Register Vendor' to record caterers, photographers, venues, and audio/visual specialists.</p>
      `;
      DOM.vendorsGrid.appendChild(emptyDiv);
      return;
    }

    const fragment = document.createDocumentFragment();

    AppState.vendors.forEach((v) => {
      const card = document.createElement("article");
      card.className = "vendor-card";

      const headerDiv = document.createElement("div");
      headerDiv.className = "banner-header";

      const servBadge = document.createElement("span");
      servBadge.className = "badge badge-accent";
      servBadge.textContent = v.service_type;

      const statBadge = document.createElement("span");
      statBadge.className = "badge badge-status";
      statBadge.textContent = v.contract_status;

      headerDiv.appendChild(servBadge);
      headerDiv.appendChild(statBadge);
      card.appendChild(headerDiv);

      const titleEl = document.createElement("h4");
      titleEl.className = "card-title";
      titleEl.textContent = v.name;
      card.appendChild(titleEl);

      const contactEl = document.createElement("p");
      contactEl.className = "card-desc";
      contactEl.textContent = `Point of Contact: ${v.contact_name} (${v.email})`;
      card.appendChild(contactEl);

      const quoteEl = document.createElement("div");
      quoteEl.className = "metric-sub";
      quoteEl.textContent = `Cost Estimate: $${v.cost_estimate.toFixed(2)}`;
      card.appendChild(quoteEl);

      const notesEl = document.createElement("p");
      notesEl.className = "card-desc";
      notesEl.style.marginTop = "0.5rem";
      notesEl.textContent = v.notes || "No terms specified.";
      card.appendChild(notesEl);

      const footerDiv = document.createElement("div");
      footerDiv.className = "card-footer-actions";

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-danger-outline btn-sm";
      delBtn.textContent = "Remove";
      delBtn.addEventListener("click", async () => {
        if (confirm(`Remove vendor ${v.name}?`)) {
          await apiFetch(`/api/vendors/${v.id}`, { method: "DELETE" });
          showToast("Vendor profile removed", "success");
          loadVendors();
        }
      });
      footerDiv.appendChild(delBtn);

      card.appendChild(footerDiv);
      fragment.appendChild(card);
    });

    DOM.vendorsGrid.appendChild(fragment);
  }

  // =========================================================================
  // PLATFORM ANALYTICS DASHBOARD
  // =========================================================================

  async function loadAnalytics() {
    try {
      const data = await apiFetch("/api/analytics");
      AppState.analytics = data;

      document.getElementById("analytics-total-events").textContent = data.total_events;
      document.getElementById("analytics-rsvp-rate").textContent = `${data.rsvp_conversion_rate}%`;
      document.getElementById("analytics-rsvp-sub").textContent = `${data.total_attending} of ${data.total_guests} attending`;
      document.getElementById("analytics-total-spent").textContent = `$${data.total_spent.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
      document.getElementById("analytics-budget-util").textContent = `${data.budget_utilization_pct}% of $${data.total_budget.toLocaleString()}`;
      document.getElementById("analytics-task-rate").textContent = `${data.task_completion_pct}%`;
      document.getElementById("analytics-task-sub").textContent = `${data.completed_tasks} of ${data.total_tasks} completed`;

      // 1. Event Category Distribution Bar Graphs
      const catList = document.getElementById("analytics-cat-list");
      catList.innerHTML = "";
      const totalEvents = data.total_events || 1;

      Object.entries(data.category_distribution || {}).forEach(([cat, count]) => {
        const item = document.createElement("div");
        item.className = "dist-item";

        const header = document.createElement("div");
        header.className = "dist-item-header";

        const labelSpan = document.createElement("span");
        labelSpan.textContent = cat;

        const countBadge = document.createElement("span");
        const pct = Math.round((count / totalEvents) * 100);
        countBadge.className = "badge badge-accent";
        countBadge.textContent = `${count} (${pct}%)`;

        header.appendChild(labelSpan);
        header.appendChild(countBadge);
        item.appendChild(header);

        const track = document.createElement("div");
        track.className = "dist-bar-track";

        const fill = document.createElement("div");
        fill.className = "dist-bar-fill";
        fill.style.width = `${Math.min(pct, 100)}%`;
        fill.style.background = CATEGORY_COLORS[cat] || "linear-gradient(90deg, #6366f1, #a855f7)";

        track.appendChild(fill);
        item.appendChild(track);
        catList.appendChild(item);
      });

      // 2. Expense Category Distribution Bar Graphs
      const expList = document.getElementById("analytics-exp-list");
      expList.innerHTML = "";
      const totalSpent = data.total_spent || 1;

      Object.entries(data.expense_category_distribution || {}).forEach(([cat, amount]) => {
        const item = document.createElement("div");
        item.className = "dist-item";

        const header = document.createElement("div");
        header.className = "dist-item-header";

        const labelSpan = document.createElement("span");
        labelSpan.textContent = cat;

        const amountBadge = document.createElement("span");
        const pct = Math.round((amount / totalSpent) * 100);
        amountBadge.className = "badge badge-status";
        amountBadge.textContent = `$${amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${pct}%)`;

        header.appendChild(labelSpan);
        header.appendChild(amountBadge);
        item.appendChild(header);

        const track = document.createElement("div");
        track.className = "dist-bar-track";

        const fill = document.createElement("div");
        fill.className = "dist-bar-fill";
        fill.style.width = `${Math.min(pct, 100)}%`;
        fill.style.background = CATEGORY_COLORS[cat] || "var(--accent-success)";

        track.appendChild(fill);
        item.appendChild(track);
        expList.appendChild(item);
      });
    } catch (_) {}
  }

  // =========================================================================
  // FORM SUBMISSION HANDLERS
  // =========================================================================

  function initForms() {
    // 1. Event Form
    DOM.formEvent.addEventListener("submit", async (e) => {
      e.preventDefault();
      const eventId = document.getElementById("event-form-id").value;

      const payload = {
        title: document.getElementById("event-title").value.trim(),
        category: document.getElementById("event-category").value,
        status: document.getElementById("event-status").value,
        event_date: new Date(document.getElementById("event-date").value).toISOString(),
        theme_color: document.getElementById("event-theme-color").value,
        venue: document.getElementById("event-venue").value.trim(),
        total_budget: parseFloat(document.getElementById("event-budget").value) || 0.0,
        capacity: parseInt(document.getElementById("event-capacity").value, 10) || 50,
        description: document.getElementById("event-description").value.trim(),
      };

      try {
        if (eventId) {
          await apiFetch(`/api/events/${eventId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast("Event updated successfully", "success");
        } else {
          const created = await apiFetch("/api/events", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          AppState.activeEventId = created.id;
          showToast("New celebration created!", "success");
          triggerConfetti(window.innerWidth / 2, window.innerHeight / 2);
        }
        closeModal("modal-event");
        await loadEvents();
      } catch (_) {}
    });

    // 2. Guest Form
    DOM.formGuest.addEventListener("submit", async (e) => {
      e.preventDefault();
      const guestId = document.getElementById("guest-form-id").value;

      const payload = {
        name: document.getElementById("guest-name").value.trim(),
        email: document.getElementById("guest-email").value.trim(),
        phone: document.getElementById("guest-phone").value.trim() || null,
        rsvp_status: document.getElementById("guest-rsvp").value,
        plus_one_count: parseInt(document.getElementById("guest-plus-ones").value, 10) || 0,
        dietary_preferences: document.getElementById("guest-dietary").value,
        notes: document.getElementById("guest-notes").value.trim() || null,
      };

      try {
        if (guestId) {
          await apiFetch(`/api/guests/${guestId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast("Guest record updated", "success");
        } else {
          await apiFetch(`/api/events/${AppState.activeEventId}/guests`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast("Guest registered successfully!", "success");
        }
        closeModal("modal-guest");
        await selectActiveEvent(AppState.activeEventId);
      } catch (_) {}
    });

    // 3. Expense Form
    DOM.formExpense.addEventListener("submit", async (e) => {
      e.preventDefault();
      const expenseId = document.getElementById("expense-form-id").value;

      const payload = {
        item_name: document.getElementById("expense-name").value.trim(),
        category: document.getElementById("expense-category").value,
        due_date: document.getElementById("expense-due-date").value || null,
        estimated_cost: parseFloat(document.getElementById("expense-estimated").value) || 0.0,
        actual_cost: parseFloat(document.getElementById("expense-actual").value) || 0.0,
        is_paid: document.getElementById("expense-is-paid").checked,
        notes: document.getElementById("expense-notes").value.trim() || null,
      };

      try {
        if (expenseId) {
          await apiFetch(`/api/expenses/${expenseId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast("Expense line item updated", "success");
        } else {
          await apiFetch(`/api/events/${AppState.activeEventId}/expenses`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast("Expense logged successfully!", "success");
        }
        closeModal("modal-expense");
        await selectActiveEvent(AppState.activeEventId);
      } catch (_) {}
    });

    // 4. Task Form
    DOM.formTask.addEventListener("submit", async (e) => {
      e.preventDefault();
      const taskId = document.getElementById("task-form-id").value;

      const payload = {
        title: document.getElementById("task-title").value.trim(),
        priority: document.getElementById("task-priority").value,
        due_date: document.getElementById("task-due-date").value || null,
        assignee: document.getElementById("task-assignee").value.trim() || null,
        category: document.getElementById("task-category").value.trim() || "General",
        is_completed: document.getElementById("task-completed").checked,
        description: document.getElementById("task-desc").value.trim() || null,
      };

      try {
        if (taskId) {
          await apiFetch(`/api/tasks/${taskId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast("Milestone updated", "success");
        } else {
          await apiFetch(`/api/events/${AppState.activeEventId}/tasks`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast("Milestone added to checklist!", "success");
        }
        closeModal("modal-task");
        await selectActiveEvent(AppState.activeEventId);
      } catch (_) {}
    });

    // 5. Vendor Form
    DOM.formVendor.addEventListener("submit", async (e) => {
      e.preventDefault();
      const vendorId = document.getElementById("vendor-form-id").value;

      const payload = {
        name: document.getElementById("vendor-name").value.trim(),
        service_type: document.getElementById("vendor-service").value,
        contract_status: document.getElementById("vendor-status").value,
        contact_name: document.getElementById("vendor-contact").value.trim(),
        cost_estimate: parseFloat(document.getElementById("vendor-cost").value) || 0.0,
        email: document.getElementById("vendor-email").value.trim(),
        phone: document.getElementById("vendor-phone").value.trim() || null,
        notes: document.getElementById("vendor-notes").value.trim() || null,
      };

      try {
        if (vendorId) {
          await apiFetch(`/api/vendors/${vendorId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          });
          showToast("Vendor profile updated", "success");
        } else {
          await apiFetch("/api/vendors", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          showToast("Vendor registered in directory!", "success");
        }
        closeModal("modal-vendor");
        loadVendors();
      } catch (_) {}
    });
  }

  // =========================================================================
  // EVENT CRUD ACTIONS
  // =========================================================================

  async function deleteEvent(eventId) {
    try {
      await apiFetch(`/api/events/${eventId}`, { method: "DELETE" });
      showToast("Event deleted successfully", "success");
      if (AppState.activeEventId === eventId) {
        AppState.activeEventId = null;
        AppState.activeEventDetail = null;
      }
      await loadEvents();
    } catch (_) {}
  }

  // =========================================================================
  // UI CONTROLS & LISTENERS SETUP
  // =========================================================================

  function setupButtons() {
    // New Event Button
    if (DOM.btnNewEvent) {
      DOM.btnNewEvent.addEventListener("click", () => {
        DOM.formEvent.reset();
        document.getElementById("event-form-id").value = "";
        document.getElementById("modal-event-title").textContent = "Create Celebration Event";
        // Default date 14 days from now
        const d = new Date();
        d.setDate(d.getDate() + 14);
        d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
        document.getElementById("event-date").value = d.toISOString().slice(0, 16);
        openModal("modal-event");
      });
    }

    // Edit Active Event Button
    if (DOM.btnEditActiveEvent) {
      DOM.btnEditActiveEvent.addEventListener("click", () => {
        if (!AppState.activeEventDetail || !AppState.activeEventDetail.event) return;
        const ev = AppState.activeEventDetail.event;

        document.getElementById("event-form-id").value = ev.id;
        document.getElementById("event-title").value = ev.title;
        document.getElementById("event-category").value = ev.category;
        document.getElementById("event-status").value = ev.status;

        const d = new Date(ev.event_date);
        d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
        document.getElementById("event-date").value = d.toISOString().slice(0, 16);

        document.getElementById("event-theme-color").value = ev.theme_color || "#6366f1";
        document.getElementById("event-venue").value = ev.venue;
        document.getElementById("event-budget").value = ev.total_budget;
        document.getElementById("event-capacity").value = ev.capacity;
        document.getElementById("event-description").value = ev.description || "";

        document.getElementById("modal-event-title").textContent = "Edit Celebration Details";
        openModal("modal-event");
      });
    }

    // Add Guest Button
    if (DOM.btnOpenGuestModal) {
      DOM.btnOpenGuestModal.addEventListener("click", () => {
        if (!AppState.activeEventId) {
          showToast("Please select or create an event first.", "warning");
          return;
        }
        DOM.formGuest.reset();
        document.getElementById("guest-form-id").value = "";
        document.getElementById("modal-guest-title").textContent = "Register Guest";
        openModal("modal-guest");
      });
    }

    // Guest Search & RSVP Filter
    if (DOM.guestSearchInput) {
      DOM.guestSearchInput.addEventListener("input", () => {
        AppState.guestSearchQuery = DOM.guestSearchInput.value.trim();
        if (AppState.activeEventDetail) {
          renderGuestsTable(AppState.activeEventDetail.guests || []);
        }
      });
    }
    if (DOM.guestFilterRsvp) {
      DOM.guestFilterRsvp.addEventListener("change", () => {
        AppState.guestFilterRsvp = DOM.guestFilterRsvp.value;
        if (AppState.activeEventDetail) {
          renderGuestsTable(AppState.activeEventDetail.guests || []);
        }
      });
    }

    // Log Expense Button
    if (DOM.btnOpenExpenseModal) {
      DOM.btnOpenExpenseModal.addEventListener("click", () => {
        if (!AppState.activeEventId) {
          showToast("Please select or create an event first.", "warning");
          return;
        }
        DOM.formExpense.reset();
        document.getElementById("expense-form-id").value = "";
        document.getElementById("modal-expense-title").textContent = "Log Itemized Expense";
        openModal("modal-expense");
      });
    }

    // Expense Search & Payment Status Filter
    if (DOM.expenseSearchInput) {
      DOM.expenseSearchInput.addEventListener("input", () => {
        AppState.expenseSearchQuery = DOM.expenseSearchInput.value.trim();
        if (AppState.activeEventDetail) {
          renderExpensesTable(AppState.activeEventDetail.expenses || []);
        }
      });
    }
    if (DOM.expenseFilterStatus) {
      DOM.expenseFilterStatus.addEventListener("change", () => {
        AppState.expenseFilterStatus = DOM.expenseFilterStatus.value;
        if (AppState.activeEventDetail) {
          renderExpensesTable(AppState.activeEventDetail.expenses || []);
        }
      });
    }

    // Add Task Button
    if (DOM.btnOpenTaskModal) {
      DOM.btnOpenTaskModal.addEventListener("click", () => {
        if (!AppState.activeEventId) {
          showToast("Please select or create an event first.", "warning");
          return;
        }
        DOM.formTask.reset();
        document.getElementById("task-form-id").value = "";
        document.getElementById("modal-task-title").textContent = "Add Checklist Task";
        openModal("modal-task");
      });
    }

    // Register Vendor Button
    if (DOM.btnOpenVendorModal) {
      DOM.btnOpenVendorModal.addEventListener("click", () => {
        DOM.formVendor.reset();
        document.getElementById("vendor-form-id").value = "";
        document.getElementById("modal-vendor-title").textContent = "Register Vendor Partner";
        openModal("modal-vendor");
      });
    }

    // Export JSON
    if (DOM.btnExportJson) {
      DOM.btnExportJson.addEventListener("click", () => {
        if (!AppState.activeEventId) return;
        window.location.href = `/api/events/${AppState.activeEventId}/export?format=json`;
        showToast("Generating JSON event plan export...", "info");
      });
    }

    // Export CSV
    if (DOM.btnExportCsv) {
      DOM.btnExportCsv.addEventListener("click", () => {
        if (!AppState.activeEventId) return;
        window.location.href = `/api/events/${AppState.activeEventId}/export?format=csv`;
        showToast("Generating CSV event plan export...", "info");
      });
    }

    // Global Selector Change
    if (DOM.eventSelector) {
      DOM.eventSelector.addEventListener("change", (e) => {
        const selectedId = parseInt(e.target.value, 10);
        if (selectedId) {
          selectActiveEvent(selectedId);
        }
      });
    }

    // Debounced Search Input (300ms)
    if (DOM.eventSearch) {
      DOM.eventSearch.addEventListener("input", () => {
        clearTimeout(AppState.searchDebounceTimer);
        AppState.searchDebounceTimer = setTimeout(() => {
          loadEvents();
        }, 300);
      });
    }

    // Quick Category Chips
    document.querySelectorAll("[data-cat-filter]").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll("[data-cat-filter]").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        const category = chip.getAttribute("data-cat-filter");
        if (DOM.filterCategory) {
          DOM.filterCategory.value = category;
        }
        loadEvents();
      });
    });

    // Dropdown Category Filter Change
    if (DOM.filterCategory) {
      DOM.filterCategory.addEventListener("change", () => {
        const val = DOM.filterCategory.value;
        document.querySelectorAll("[data-cat-filter]").forEach((c) => {
          if (c.getAttribute("data-cat-filter") === val) {
            c.classList.add("active");
          } else {
            c.classList.remove("active");
          }
        });
        loadEvents();
      });
    }

    // Lifecycle Status Filter Change
    if (DOM.filterStatus) {
      DOM.filterStatus.addEventListener("change", () => loadEvents());
    }

    // Task Filter Chips
    document.querySelectorAll("[data-task-filter]").forEach((chip) => {
      chip.addEventListener("click", () => {
        document.querySelectorAll("[data-task-filter]").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        AppState.activeTaskFilter = chip.getAttribute("data-task-filter");
        if (AppState.activeEventDetail && AppState.activeEventDetail.tasks) {
          renderTasksList(AppState.activeEventDetail.tasks);
        }
      });
    });

    // Global Keyboard Shortcuts (N: New Event, /: Search, Esc: Close Dialogs)
    document.addEventListener("keydown", (e) => {
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
      if (activeTag === "input" || activeTag === "textarea" || activeTag === "select") {
        return;
      }

      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        if (DOM.btnNewEvent) DOM.btnNewEvent.click();
      } else if (e.key === "/") {
        e.preventDefault();
        if (DOM.eventSearch) {
          DOM.eventSearch.focus();
          DOM.eventSearch.select();
        }
      }
    });
  }

  // =========================================================================
  // BOOTSTRAP APPLICATION
  // =========================================================================

  document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initForms();
    setupButtons();
    loadEvents();
  });
})();
