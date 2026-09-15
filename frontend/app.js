// FinTrack Multi-Profile & Mobile Application Logic
let currentProfile = 'mom'; // 'mom' or 'me'
let currentMonth = new Date().toISOString().slice(0, 7); // 'YYYY-MM'
let fontSize = 'large';
let accountsList = [];
let categoriesList = [];
let investmentsData = null;
let allocationChartInstance = null;
let currentModalType = 'expense';
let selectedCalDate = null;
let isSiteLocked = false;

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', async () => {
  // Check server configuration (APP_PROFILE set in Render / environment)
  let serverAppProfile = window.SERVER_APP_PROFILE || null;
  if (!serverAppProfile) {
    try {
      const cfgRes = await fetch('/api/config');
      if (cfgRes.ok) {
        const cfg = await cfgRes.json();
        if (cfg && (cfg.app_profile === 'mom' || cfg.app_profile === 'me')) {
          serverAppProfile = cfg.app_profile;
        }
      }
    } catch (e) {
      console.warn('Failed to load /api/config', e);
    }
  }

  const urlParams = new URLSearchParams(window.location.search);
  const pParam = urlParams.get('profile') || urlParams.get('user');
  const lockParam = urlParams.get('lock') || urlParams.get('only');

  if (serverAppProfile) {
    // Dedicated standalone site deployment (via Render APP_PROFILE environment variable)
    currentProfile = serverAppProfile;
    isSiteLocked = true;
  } else if (pParam === 'me' || pParam === 'mom') {
    currentProfile = pParam;
    isSiteLocked = (lockParam === 'true' || lockParam === 'mom' || urlParams.get('user') === 'mom');
  } else {
    const saved = localStorage.getItem('fintrack_active_profile');
    if (saved === 'me' || saved === 'mom') currentProfile = saved;
    isSiteLocked = (lockParam === 'true');
  }

  setupEventListeners();
  await switchProfile(currentProfile, false, isSiteLocked);
  await loadCategories();
  loadSettings();
});

function setupEventListeners() {
  // Desktop Navigation Tabs
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const tabId = tab.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // Month Selector
  document.getElementById('prevMonthBtn').addEventListener('click', () => changeMonth(-1));
  document.getElementById('nextMonthBtn').addEventListener('click', () => changeMonth(1));

  // Quick Add Button
  document.getElementById('openQuickAddBtn').addEventListener('click', () => openModal('expense'));

  // Price refresh buttons
  const r1 = document.getElementById('refreshPricesBtn');
  if (r1) r1.addEventListener('click', handleRefreshPrices);
  const r2 = document.getElementById('dashRefreshPricesBtn');
  if (r2) r2.addEventListener('click', handleRefreshPrices);

  // Filter change in transactions list
  document.getElementById('txFilterType').addEventListener('change', loadTransactions);
  document.getElementById('txSearchKeyword').addEventListener('keyup', (e) => {
    if (e.key === 'Enter') loadTransactions();
  });
}

// ----------------- Multi-Profile Switching -----------------

async function switchProfile(profileId, showMessage = true, isLocked = false) {
  if (isSiteLocked) {
    profileId = currentProfile;
    isLocked = true;
  } else {
    currentProfile = profileId;
    localStorage.setItem('fintrack_active_profile', profileId);

    // Update URL without reload for bookmarking
    const newUrl = new URL(window.location);
    newUrl.searchParams.set('profile', profileId);
    window.history.replaceState({}, '', newUrl);
  }

  const switcher = document.getElementById('profileSwitcherBox');
  const standaloneTitle = document.getElementById('standaloneTitleBox');
  const standaloneIcon = document.getElementById('standaloneIcon');
  const standaloneHeader = document.getElementById('standaloneTitle');
  const settingDataReset = document.getElementById('settingDataResetBox');

  if (isLocked) {
    if (switcher) switcher.classList.add('hidden');
    if (standaloneTitle) standaloneTitle.classList.remove('hidden');
  } else {
    if (switcher) switcher.classList.remove('hidden');
    if (standaloneTitle) standaloneTitle.classList.add('hidden');
  }

  const btnMom = document.getElementById('profileBtnMom');
  const btnMe = document.getElementById('profileBtnMe');
  const investTab = document.getElementById('investNavTab');
  const mobileInvestTab = document.getElementById('mobileInvestNavBtn');
  const netWorthCard = document.getElementById('netWorthCard');
  const dashInvestBox = document.getElementById('dashInvestBox');

  const bannerIcon = document.getElementById('profileBannerIcon');
  const bannerTitle = document.getElementById('profileBannerTitle');
  const bannerDesc = document.getElementById('profileBannerDesc');
  const bannerBox = document.getElementById('profileBanner');
  const badgeText = document.getElementById('profileBadgeText');

  if (profileId === 'mom') {
    // Mother's Profile UI
    if (standaloneIcon) standaloneIcon.textContent = "🌸";
    if (standaloneHeader) standaloneHeader.textContent = "어머니 행복 가계부";
    document.title = "어머니 행복 가계부 🌸";

    if (btnMom) btnMom.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition bg-white text-emerald-700 shadow-xs font-black";
    if (btnMe) btnMe.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition text-slate-600 hover:text-slate-900 font-bold";

    if (bannerBox) bannerBox.className = "bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs";
    if (bannerIcon) {
      bannerIcon.textContent = "🌸";
      bannerIcon.className = "w-10 h-10 rounded-full bg-emerald-500 text-white flex items-center justify-center flex-shrink-0 text-lg shadow-xs";
    }
    if (bannerTitle) {
      bannerTitle.textContent = "어머니 전용 간편 가계부입니다";
      bannerTitle.className = "text-base font-bold text-emerald-900";
    }
    if (bannerDesc) {
      bannerDesc.textContent = "복잡한 주식/투자 없이 오늘 쓴 돈과 남은 예산을 편하게 확인하세요.";
      bannerDesc.className = "text-xs text-emerald-700";
    }
    if (badgeText) badgeText.textContent = "어머니 독립 장부";

    if (investTab) investTab.classList.add('hidden');
    if (mobileInvestTab) mobileInvestTab.classList.add('hidden');
    if (netWorthCard) netWorthCard.classList.add('hidden');
    if (dashInvestBox) dashInvestBox.classList.add('hidden');
    if (settingDataReset) settingDataReset.classList.add('hidden');

    setFontSize('large'); // Senior-friendly large text
    if (showMessage) showToast("🌸 어머니 가계부로 전환되었습니다.");

  } else {
    // My Profile UI (With Investments & Net worth)
    if (standaloneIcon) standaloneIcon.textContent = "💼";
    if (standaloneHeader) standaloneHeader.textContent = "내 스마트 가계부 & 자산관리";
    document.title = "내 가계부 & 자산관리 💼";

    if (btnMe) btnMe.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition bg-white text-indigo-700 shadow-xs font-black";
    if (btnMom) btnMom.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition text-slate-600 hover:text-slate-900 font-bold";

    if (bannerBox) bannerBox.className = "bg-gradient-to-r from-indigo-50 to-blue-50 border border-indigo-200 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs";
    if (bannerIcon) {
      bannerIcon.textContent = "👤";
      bannerIcon.className = "w-10 h-10 rounded-full bg-indigo-600 text-white flex items-center justify-center flex-shrink-0 text-lg shadow-xs";
    }
    if (bannerTitle) {
      bannerTitle.textContent = "내 스마트 가계부 & 투자 포트폴리오";
      bannerTitle.className = "text-base font-bold text-indigo-950";
    }
    if (bannerDesc) {
      bannerDesc.textContent = "주식, 가상자산 시세 및 총 순자산(Net Worth)이 연동되는 통합 장부입니다.";
      bannerDesc.className = "text-xs text-indigo-700";
    }
    if (badgeText) badgeText.textContent = "내 전용 통합 장부";

    if (investTab) investTab.classList.remove('hidden');
    if (mobileInvestTab) mobileInvestTab.classList.remove('hidden');
    if (netWorthCard) netWorthCard.classList.remove('hidden');
    if (dashInvestBox) dashInvestBox.classList.remove('hidden');
    if (settingDataReset) settingDataReset.classList.remove('hidden');

    setFontSize('normal');
    if (showMessage) showToast("👤 내 가계부(투자 연동)로 전환되었습니다.");
  }

  await loadAccounts();
  await refreshCurrentView();
}

function setFontSize(size) {
  fontSize = size;
  const normBtn = document.getElementById('fontNormalBtn');
  const largeBtn = document.getElementById('fontLargeBtn');
  if (size === 'large') {
    document.body.classList.add('font-large');
    if (largeBtn) {
      largeBtn.className = "flex-1 py-2.5 rounded-xl border-2 border-indigo-600 bg-indigo-50 text-indigo-700 text-base font-extrabold shadow-xs";
      normBtn.className = "flex-1 py-2.5 rounded-xl border border-slate-200 text-sm font-bold hover:bg-slate-50";
    }
  } else {
    document.body.classList.remove('font-large');
    if (normBtn) {
      normBtn.className = "flex-1 py-2.5 rounded-xl border-2 border-indigo-600 bg-indigo-50 text-indigo-700 text-base font-extrabold shadow-xs";
      largeBtn.className = "flex-1 py-2.5 rounded-xl border border-slate-200 text-sm font-bold hover:bg-slate-50";
    }
  }
}

// ----------------- Navigation & Month Controls -----------------

function switchTab(tabId) {
  // Desktop tabs
  document.querySelectorAll('.nav-tab').forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) {
      btn.classList.add('active', 'text-indigo-600', 'border-indigo-600', 'font-bold');
      btn.classList.remove('text-slate-500', 'border-transparent');
    } else {
      btn.classList.remove('active', 'text-indigo-600', 'border-indigo-600', 'font-bold');
      btn.classList.add('text-slate-500', 'border-transparent');
    }
  });

  // Mobile bottom buttons
  document.querySelectorAll('.mobile-nav-btn').forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) {
      btn.classList.add('active', 'text-indigo-600');
      btn.classList.remove('text-slate-400');
    } else {
      btn.classList.remove('active', 'text-indigo-600');
      btn.classList.add('text-slate-400');
    }
  });

  // Tab panes
  document.querySelectorAll('.tab-pane').forEach(pane => {
    if (pane.id === tabId) {
      pane.classList.remove('hidden');
    } else {
      pane.classList.add('hidden');
    }
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (tabId === 'tab-dashboard') loadDashboard();
  else if (tabId === 'tab-transactions') loadTransactions();
  else if (tabId === 'tab-calendar') loadCalendar();
  else if (tabId === 'tab-budget') loadBudgets();
  else if (tabId === 'tab-investments') loadInvestments();
  else if (tabId === 'tab-accounts') loadAccounts();
  else if (tabId === 'tab-settings') loadSettings();
}

function changeMonth(delta) {
  const parts = currentMonth.split('-');
  let year = parseInt(parts[0], 10);
  let month = parseInt(parts[1], 10) + delta;

  if (month < 1) {
    month = 12;
    year -= 1;
  } else if (month > 12) {
    month = 1;
    year += 1;
  }

  currentMonth = `${year}-${String(month).padStart(2, '0')}`;
  document.getElementById('currentMonthLabel').textContent = `${year}.${String(month).padStart(2, '0')}`;
  refreshCurrentView();
}

async function refreshCurrentView() {
  document.getElementById('currentMonthLabel').textContent = currentMonth.replace('-', '.');
  await loadDashboard();
  const activeTab = document.querySelector('.nav-tab.active')?.getAttribute('data-tab');
  if (activeTab === 'tab-transactions') loadTransactions();
  if (activeTab === 'tab-calendar') loadCalendar();
  if (activeTab === 'tab-budget') loadBudgets();
  if (activeTab === 'tab-investments') loadInvestments();
}

// ----------------- Dashboard -----------------

async function loadDashboard() {
  try {
    const res = await fetch(`/api/summary?profile_id=${currentProfile}&month=${currentMonth}`);
    const data = await res.json();

    document.getElementById('dashTodayExpense').textContent = formatCurrency(data.today.expense);
    document.getElementById('dashTodayDate').textContent = `${data.today.date} 지출`;
    document.getElementById('dashMonthExpense').textContent = formatCurrency(data.monthly.expense);
    document.getElementById('dashMonthIncome').textContent = formatCurrency(data.monthly.income);
    
    const netEl = document.getElementById('dashMonthNet');
    netEl.textContent = formatCurrency(data.monthly.net);
    netEl.className = data.monthly.net >= 0 ? "text-xl sm:text-2xl font-black text-indigo-600" : "text-xl sm:text-2xl font-black text-rose-600";

    // Net worth & Investments (for Me / Pro mode)
    document.getElementById('dashNetWorth').textContent = formatCurrency(data.net_worth);
    document.getElementById('dashNetCash').textContent = formatCurrency(data.cash_total);
    document.getElementById('dashNetInvest').textContent = formatCurrency(data.investments.total_value_krw);

    // Budget Progress Box
    const budgetPct = data.monthly.budget_usage_pct;
    document.getElementById('dashBudgetPct').textContent = `${budgetPct}%`;
    const bBar = document.getElementById('dashBudgetBar');
    bBar.style.width = `${Math.min(budgetPct, 100)}%`;
    bBar.className = budgetPct > 100 ? "bg-rose-500 h-3 rounded-full transition-all duration-500" : "bg-indigo-600 h-3 rounded-full transition-all duration-500";
    document.getElementById('dashBudgetSpent').textContent = formatCurrency(data.monthly.expense);
    document.getElementById('dashBudgetTotal').textContent = formatCurrency(data.monthly.budget);

    // Investment Box on Dashboard
    document.getElementById('dashInvestCost').textContent = formatCurrency(data.investments.total_cost_krw);
    document.getElementById('dashInvestValue').textContent = formatCurrency(data.investments.total_value_krw);
    const pEl = document.getElementById('dashInvestProfit');
    const pVal = data.investments.profit_krw;
    const pRate = data.investments.profit_rate_pct;
    pEl.textContent = `${pVal >= 0 ? '+' : ''}${formatCurrency(pVal)} (${pRate >= 0 ? '+' : ''}${pRate}%)`;
    pEl.className = pVal >= 0 ? "font-black text-rose-500" : "font-black text-blue-500";

    await loadRecentTransactions();
  } catch (err) {
    console.error("대시보드 요약 로드 실패:", err);
  }
}

async function loadRecentTransactions() {
  try {
    const res = await fetch(`/api/transactions?profile_id=${currentProfile}&month=${currentMonth}&limit=5`);
    const txs = await res.json();

    const container = document.getElementById('recentTxList');
    document.getElementById('recentTxCount').textContent = `${txs.length}건`;

    if (txs.length === 0) {
      container.innerHTML = `
        <div class="text-center py-10 text-slate-400">
          <i class="fa-regular fa-clipboard text-4xl mb-2 text-slate-300"></i>
          <p class="text-sm font-medium">이번 달 내역이 아직 없습니다.</p>
          <p class="text-xs text-slate-400 mt-1">[쓴 돈 쓰기] 버튼으로 오늘 지출을 적어보세요.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = txs.map(tx => {
      const isExpense = tx.type === 'expense';
      const isIncome = tx.type === 'income';
      const sign = isExpense ? '-' : (isIncome ? '+' : '');
      const colorClass = isExpense ? 'text-rose-600' : (isIncome ? 'text-emerald-600' : 'text-slate-700');
      const badgeClass = isExpense ? 'bg-rose-50 text-rose-600' : (isIncome ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600');
      const typeLabel = isExpense ? '지출' : (isIncome ? '수입' : '이체');

      return `
        <div class="flex items-center justify-between p-3.5 rounded-xl border border-slate-100 hover:bg-slate-50 transition cursor-pointer group" onclick="openEditTransactionById(${tx.id})" title="클릭하여 내역 수정">
          <div class="flex items-center gap-3">
            <span class="text-xs font-bold px-2 py-1 rounded-lg ${badgeClass}">
              ${typeLabel}
            </span>
            <div>
              <div class="font-bold text-slate-800 text-sm">${tx.category} <span class="font-normal text-xs text-slate-400">· ${tx.memo || '메모 없음'}</span></div>
              <div class="text-xs text-slate-400">${tx.date} · ${tx.account_name || '기본통장'}</div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="font-black text-base ${colorClass}">
              ${sign}${formatCurrency(tx.amount)}
            </div>
            <span class="text-slate-300 group-hover:text-indigo-600 text-xs p-1 transition">
              <i class="fa-solid fa-pen-to-square"></i>
            </span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error(err);
  }
}

// ----------------- Transactions Full List -----------------

async function loadTransactions() {
  const type = document.getElementById('txFilterType').value;
  const search = document.getElementById('txSearchKeyword').value.trim();

  try {
    let url = `/api/transactions?profile_id=${currentProfile}&month=${currentMonth}`;
    if (type && type !== 'all') url += `&type=${type}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const res = await fetch(url);
    const txs = await res.json();
    const tbody = document.getElementById('txFullTableBody');

    if (txs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-12 text-slate-400">
            조건에 해당하는 거래 내역이 없습니다.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = txs.map(tx => {
      const isExpense = tx.type === 'expense';
      const isIncome = tx.type === 'income';
      const sign = isExpense ? '-' : (isIncome ? '+' : '');
      const colorClass = isExpense ? 'text-rose-600' : (isIncome ? 'text-emerald-600' : 'text-blue-600');
      const typeLabel = isExpense ? '지출' : (isIncome ? '수입' : '이체');

      let accText = tx.account_name || '미지정';
      if (tx.type === 'transfer' && tx.to_account_name) {
        accText = `${tx.account_name} &rarr; ${tx.to_account_name}`;
      }

      return `
        <tr class="hover:bg-slate-50 transition">
          <td class="py-3 px-3 text-xs font-semibold text-slate-500">${tx.date}</td>
          <td class="py-3 px-3">
            <span class="text-xs px-2 py-0.5 rounded font-bold ${isExpense ? 'bg-rose-50 text-rose-600' : (isIncome ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600')}">
              ${typeLabel}
            </span>
          </td>
          <td class="py-3 px-3 font-bold text-slate-800">${tx.category}</td>
          <td class="py-3 px-3 text-slate-600 text-xs">${tx.memo || '-'}</td>
          <td class="py-3 px-3 text-xs text-slate-500">${accText}</td>
          <td class="py-3 px-3 text-right font-black ${colorClass}">
            ${sign}${formatCurrency(tx.amount)}
          </td>
          <td class="py-3 px-3 text-center space-x-1 whitespace-nowrap">
            <button onclick="openEditTransactionById(${tx.id})" class="text-slate-400 hover:text-indigo-600 text-xs p-1.5 transition" title="내역 수정">
              <i class="fa-solid fa-pen-to-square"></i>
            </button>
            <button onclick="deleteTransaction(${tx.id})" class="text-slate-400 hover:text-rose-600 text-xs p-1.5 transition" title="삭제">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error(err);
  }
}

async function deleteTransaction(id) {
  if (!confirm("이 거래 내역을 삭제하시겠습니까?")) return;
  try {
    const res = await fetch(`/api/transactions/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showToast("내역이 삭제되었습니다.");
      loadTransactions();
      loadDashboard();
      loadAccounts();
    }
  } catch (e) {
    console.error(e);
  }
}

// ----------------- Calendar View -----------------

async function loadCalendar() {
  try {
    const res = await fetch(`/api/calendar?profile_id=${currentProfile}&month=${currentMonth}`);
    const dailyMap = await res.json();

    const parts = currentMonth.split('-');
    const year = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);

    const firstDay = new Date(year, month - 1, 1).getDay();
    const lastDate = new Date(year, month, 0).getDate();
    const prevLastDate = new Date(year, month - 1, 0).getDate();

    const grid = document.getElementById('calendarGrid');
    grid.innerHTML = '';

    const todayStr = new Date().toISOString().slice(0, 10);

    for (let i = firstDay - 1; i >= 0; i--) {
      const cell = document.createElement('div');
      cell.className = "cal-day-cell other-month";
      cell.innerHTML = `<span class="text-xs font-semibold text-slate-400">${prevLastDate - i}</span>`;
      grid.appendChild(cell);
    }

    for (let d = 1; d <= lastDate; d++) {
      const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const dayData = dailyMap[dateStr] || { income: 0, expense: 0, count: 0 };
      const isToday = dateStr === todayStr;

      const cell = document.createElement('div');
      cell.className = `cal-day-cell ${isToday ? 'is-today' : ''}`;
      cell.onclick = () => selectCalendarDay(dateStr);

      let incomeHtml = dayData.income > 0 ? `<div class="text-[10px] sm:text-[11px] font-bold text-emerald-600 truncate">+${formatCompact(dayData.income)}</div>` : '';
      let expenseHtml = dayData.expense > 0 ? `<div class="text-[10px] sm:text-[11px] font-bold text-rose-600 truncate">-${formatCompact(dayData.expense)}</div>` : '';

      cell.innerHTML = `
        <div class="flex justify-between items-center">
          <span class="text-xs font-bold ${isToday ? 'text-indigo-600' : 'text-slate-700'}">${d}</span>
          ${dayData.count > 0 ? `<span class="text-[10px] text-slate-400 font-medium">${dayData.count}건</span>` : ''}
        </div>
        <div class="mt-1 space-y-0.5">
          ${incomeHtml}
          ${expenseHtml}
        </div>
      `;
      grid.appendChild(cell);
    }
  } catch (err) {
    console.error(err);
  }
}

async function selectCalendarDay(dateStr) {
  selectedCalDate = dateStr;
  const detailBox = document.getElementById('calendarDetailBox');
  detailBox.classList.remove('hidden');
  document.getElementById('calSelectedDateText').textContent = `${dateStr} 상세 내역`;

  try {
    const res = await fetch(`/api/transactions?profile_id=${currentProfile}&month=${currentMonth}`);
    const allTxs = await res.json();
    const dayTxs = allTxs.filter(t => t.date === dateStr);

    const listEl = document.getElementById('calDayTxList');
    if (dayTxs.length === 0) {
      listEl.innerHTML = `<div class="text-xs text-slate-400 py-3">이 날짜에 기록된 거래가 없습니다.</div>`;
      return;
    }

    listEl.innerHTML = dayTxs.map(tx => {
      const isExp = tx.type === 'expense';
      const color = isExp ? 'text-rose-600' : (tx.type === 'income' ? 'text-emerald-600' : 'text-blue-600');
      const sign = isExp ? '-' : (tx.type === 'income' ? '+' : '');
      return `
        <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100 hover:bg-indigo-50/60 transition cursor-pointer group" onclick="openEditTransactionById(${tx.id})" title="클릭하여 내역 수정">
          <div>
            <span class="font-bold text-slate-800 text-xs">${tx.category}</span>
            <span class="text-xs text-slate-500 ml-1">(${tx.memo || '메모 없음'})</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="font-black text-xs ${color}">
              ${sign}${formatCurrency(tx.amount)}
            </div>
            <span class="text-slate-300 group-hover:text-indigo-600 text-xs transition">
              <i class="fa-solid fa-pen-to-square"></i>
            </span>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error(e);
  }
}

function openModalForDate() {
  openModal('expense');
  if (selectedCalDate) {
    document.getElementById('txDateInput').value = selectedCalDate;
  }
}

// ----------------- Budgets -----------------

async function loadBudgets() {
  try {
    const res = await fetch(`/api/budgets?profile_id=${currentProfile}&month=${currentMonth}`);
    const data = await res.json();

    document.getElementById('budgetRemainingTotal').textContent = formatCurrency(data.remaining);

    const container = document.getElementById('budgetCategoryList');
    if (data.categories.length === 0) {
      container.innerHTML = `<div class="text-center py-10 text-slate-400">등록된 지출 카테고리가 없습니다.</div>`;
      return;
    }

    container.innerHTML = data.categories.map(c => {
      const isOver = c.spent > c.budget && c.budget > 0;
      const pct = c.percentage;

      return `
        <div class="p-4 rounded-2xl border border-slate-200 bg-white hover:border-indigo-200 transition">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span class="w-3 h-3 rounded-full" style="background-color: ${c.color}"></span>
              <span class="font-bold text-slate-900 text-sm">${c.category}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs ${isOver ? 'text-rose-600 font-bold' : 'text-slate-500'}">
                지출: <b>${formatCurrency(c.spent)}</b> / 예산: <b>${formatCurrency(c.budget)}</b>
              </span>
              <button onclick="promptSetBudget('${c.category}', ${c.budget})" class="text-xs px-2 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium">
                예산 변경
              </button>
            </div>
          </div>
          <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
            <div class="h-2.5 rounded-full ${isOver ? 'bg-rose-500' : 'bg-indigo-600'} transition-all duration-300" style="width: ${Math.min(pct, 100)}%"></div>
          </div>
          <div class="flex justify-between text-[11px] text-slate-400 mt-1.5 font-medium">
            <span>소진율 ${pct}%</span>
            <span>남은 금액: <b class="${c.remaining < 0 ? 'text-rose-500' : 'text-slate-700'}">${formatCurrency(c.remaining)}</b></span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error(err);
  }
}

async function promptSetBudget(category, currentAmt) {
  const val = prompt(`[${category}] 한 달 예산 금액을 입력하세요 (원):`, currentAmt || 0);
  if (val === null) return;
  const num = parseFloat(val);
  if (isNaN(num) || num < 0) {
    alert("올바른 금액을 입력해주세요.");
    return;
  }

  try {
    const res = await fetch('/api/budgets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_id: currentProfile,
        month: currentMonth,
        category: category,
        amount: num
      })
    });
    if (res.ok) {
      showToast(`${category} 예산이 설정되었습니다.`);
      loadBudgets();
      loadDashboard();
    }
  } catch (e) {
    console.error(e);
  }
}

// ----------------- Investments -----------------

async function loadInvestments() {
  try {
    const res = await fetch(`/api/investments?profile_id=${currentProfile}`);
    investmentsData = await res.json();

    const sum = investmentsData.summary;
    document.getElementById('invTotalValue').textContent = formatCurrency(sum.total_value_krw);
    document.getElementById('invTotalCost').textContent = formatCurrency(sum.total_cost_krw);
    
    const profitEl = document.getElementById('invTotalProfit');
    const rateEl = document.getElementById('invTotalRate');
    const pSign = sum.profit_krw >= 0 ? '+' : '';
    profitEl.textContent = `${pSign}${formatCurrency(sum.profit_krw)}`;
    profitEl.className = sum.profit_krw >= 0 ? "text-2xl font-black mt-1 text-rose-500" : "text-2xl font-black mt-1 text-blue-500";
    rateEl.textContent = `${pSign}${sum.profit_rate}%`;

    document.getElementById('invUsdRate').textContent = sum.usd_krw_rate.toLocaleString();
    document.getElementById('holdingCountBadge').textContent = `${investmentsData.items.length}개`;

    const tbody = document.getElementById('holdingsTableBody');
    if (investmentsData.items.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-12 text-slate-400">
            등록된 투자 종목이 없습니다. [+ 새 종목 추가]를 눌러 보유 종목을 추가해보세요.
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = investmentsData.items.map(item => {
        const isUp = item.profit_krw >= 0;
        const color = isUp ? 'text-rose-500' : 'text-blue-500';
        const sign = isUp ? '+' : '';
        const currSym = item.currency === 'USD' ? '$' : '₩';

        return `
          <tr class="hover:bg-slate-50 transition">
            <td class="py-3 px-3">
              <div class="font-bold text-slate-900">${item.name}</div>
              <div class="text-[11px] text-slate-400">${item.symbol}</div>
            </td>
            <td class="py-3 px-3">
              <span class="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">${item.category_label}</span>
            </td>
            <td class="py-3 px-3 text-right font-medium text-slate-800">${item.quantity}</td>
            <td class="py-3 px-3 text-right text-xs text-slate-600">${currSym}${item.avg_buy_price.toLocaleString()}</td>
            <td class="py-3 px-3 text-right text-xs font-bold text-slate-900">${currSym}${item.current_price.toLocaleString()}</td>
            <td class="py-3 px-3 text-right font-black ${color}">
              ${sign}${formatCurrency(item.profit_krw)}<br>
              <span class="text-[11px] font-semibold">(${sign}${item.profit_rate}%)</span>
            </td>
            <td class="py-3 px-3 text-center">
              <button onclick="deleteInvestment(${item.id})" class="text-slate-400 hover:text-rose-600 text-xs transition" title="종목 삭제">
                <i class="fa-regular fa-trash-can"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    renderAllocationChart(investmentsData.allocation);

  } catch (err) {
    console.error("투자 내역 로드 실패:", err);
  }
}

function renderAllocationChart(allocationMap) {
  const ctx = document.getElementById('allocationChart').getContext('2d');
  const labels = Object.keys(allocationMap);
  const data = Object.values(allocationMap);

  const colors = [
    '#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#06B6D4', '#8B5CF6', '#EC4899', '#64748B'
  ];

  if (allocationChartInstance) {
    allocationChartInstance.destroy();
  }

  if (data.length === 0 || data.reduce((a, b) => a + b, 0) === 0) {
    allocationChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['데이터 없음'],
        datasets: [{ data: [1], backgroundColor: ['#E2E8F0'] }]
      },
      options: { cutout: '70%', plugins: { tooltip: { enabled: false } } }
    });
    document.getElementById('allocationLegend').innerHTML = `<div class="text-center text-xs text-slate-400">보유 종목이 없습니다.</div>`;
    return;
  }

  allocationChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#FFFFFF'
      }]
    },
    options: {
      cutout: '68%',
      plugins: {
        legend: { display: false }
      }
    }
  });

  const total = data.reduce((a, b) => a + b, 0);
  const legendEl = document.getElementById('allocationLegend');
  legendEl.innerHTML = labels.map((label, idx) => {
    const val = data[idx];
    const pct = ((val / total) * 100).toFixed(1);
    return `
      <div class="flex items-center justify-between py-0.5">
        <div class="flex items-center gap-1.5">
          <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${colors[idx]}"></span>
          <span>${label}</span>
        </div>
        <span class="font-bold text-slate-800">${pct}%</span>
      </div>
    `;
  }).join('');
}

async function handleRefreshPrices() {
  showToast("최신 시세 및 환율을 조회하고 있습니다...");
  try {
    const res = await fetch('/api/investments/refresh-prices', { method: 'POST' });
    const data = await res.json();
    showToast(`시세가 갱신되었습니다. (환율: ${data.usd_krw_rate}원)`);
    loadInvestments();
    loadDashboard();
  } catch (err) {
    showToast("시세 갱신 중 오류가 발생했습니다.");
  }
}

async function deleteInvestment(id) {
  if (!confirm("이 종목을 포트폴리오에서 삭제하시겠습니까?")) return;
  try {
    const res = await fetch(`/api/investments/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showToast("종목이 삭제되었습니다.");
      loadInvestments();
      loadDashboard();
    }
  } catch (e) {
    console.error(e);
  }
}

// ----------------- Accounts & Categories -----------------

async function loadAccounts() {
  try {
    const res = await fetch(`/api/accounts?profile_id=${currentProfile}`);
    accountsList = await res.json();

    const grid = document.getElementById('accountsListGrid');
    if (grid) {
      grid.innerHTML = accountsList.map(acc => {
        const isInvest = acc.is_investment === 1;
        const typeBadge = isInvest ? '투자/증권 예수금' : (acc.type === 'cash' ? '현금 지갑' : (acc.type === 'card' ? '카드' : '은행 통장'));
        const initBal = acc.initial_balance !== undefined && acc.initial_balance !== null ? acc.initial_balance : 0;
        return `
          <div class="p-5 rounded-2xl border border-slate-200 bg-white shadow-xs flex flex-col justify-between hover:border-indigo-300 transition">
            <div>
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                  <span class="w-3.5 h-3.5 rounded-full shadow-2xs" style="background-color: ${acc.color}"></span>
                  <span class="font-bold text-slate-900 text-base">${acc.name}</span>
                </div>
                <span class="text-xs px-2.5 py-0.5 rounded-full font-bold ${isInvest ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'}">
                  ${typeBadge}
                </span>
              </div>
              <div class="space-y-1 my-3">
                <div class="text-[11px] text-slate-400 font-medium">실시간 현재 잔액</div>
                <div class="text-2xl font-black text-slate-900">${formatCurrency(acc.balance)}</div>
                <div class="text-xs text-slate-500 pt-1.5 flex items-center gap-1.5 font-medium">
                  <i class="fa-solid fa-flag-checkered text-slate-400 text-[11px]"></i>
                  <span>시작 초기 잔액: <b class="text-slate-800">${formatCurrency(initBal)}</b></span>
                </div>
              </div>
            </div>
            <div class="pt-3 border-t border-slate-100 flex items-center justify-end gap-2 mt-2">
              <button onclick="openEditAccountModal(${acc.id})" class="px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-600 rounded-xl text-xs font-bold text-slate-700 transition flex items-center gap-1.5 shadow-2xs">
                <i class="fa-solid fa-pen-to-square text-[11px]"></i>
                <span>잔액 및 정보 수정</span>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    populateAccountDropdowns();
  } catch (err) {
    console.error(err);
  }
}

function populateAccountDropdowns() {
  const fromSel = document.getElementById('txAccountInput');
  const toSel = document.getElementById('txToAccountInput');
  const investCashSel = document.getElementById('invCashAccountInput');
  const tradeAccSel = document.getElementById('tradeAccountSelect');

  const options = accountsList.map(a => `<option value="${a.id}">${a.name} (${formatCurrency(a.balance)})</option>`).join('');

  if (fromSel) fromSel.innerHTML = options;
  if (toSel) toSel.innerHTML = options;
  if (investCashSel) investCashSel.innerHTML = `<option value="">연동 안 함 (자산만 등록)</option>` + options;
  if (tradeAccSel) tradeAccSel.innerHTML = options;
}

async function loadCategories() {
  try {
    const res = await fetch('/api/categories');
    categoriesList = await res.json();
    renderCategoryChips();
  } catch (err) {
    console.error(err);
  }
}

function renderCategoryChips() {
  const container = document.getElementById('categoryChips');
  if (!container) return;

  const currentType = currentModalType === 'income' ? 'income' : 'expense';
  const filtered = categoriesList.filter(c => c.type === currentType);

  container.innerHTML = filtered.map((cat, idx) => {
    return `
      <button type="button" onclick="selectCategoryChip('${cat.name}')" class="category-chip px-3 py-1.5 rounded-lg text-xs font-bold border border-slate-200 bg-white text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-300 transition ${idx === 0 ? 'active border-indigo-600 bg-indigo-50 text-indigo-600' : ''}">
        ${cat.name}
      </button>
    `;
  }).join('');

  if (filtered.length > 0) {
    document.getElementById('txCategoryInput').value = filtered[0].name;
  }
}

function selectCategoryChip(catName) {
  document.getElementById('txCategoryInput').value = catName;
  document.querySelectorAll('.category-chip').forEach(btn => {
    if (btn.textContent.trim() === catName) {
      btn.className = "category-chip px-3 py-1.5 rounded-lg text-xs font-bold border-2 border-indigo-600 bg-indigo-50 text-indigo-700 shadow-xs";
    } else {
      btn.className = "category-chip px-3 py-1.5 rounded-lg text-xs font-bold border border-slate-200 bg-white text-slate-700 hover:bg-indigo-50 transition";
    }
  });
}

// ----------------- Modal Handlers -----------------

let editingTxId = null;

function openModal(type = 'expense') {
  editingTxId = null;
  currentModalType = type;
  document.getElementById('txModal').classList.remove('hidden');
  document.getElementById('txDateInput').value = new Date().toISOString().slice(0, 10);
  document.getElementById('txAmountInput').value = '';
  document.getElementById('txMemoInput').value = '';
  document.getElementById('txSubmitBtn').textContent = "저장하기";
  const delBtn = document.getElementById('txModalDeleteBtn');
  if (delBtn) delBtn.classList.add('hidden');
  setTxModalType(type);
  setTimeout(() => document.getElementById('txAmountInput').focus(), 100);
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
  if (id === 'txModal') editingTxId = null;
  if (id === 'accountModal') editingAccountId = null;
}

async function openEditTransactionById(txId) {
  try {
    const res = await fetch(`/api/transactions/${txId}`);
    if (!res.ok) {
      alert("해당 내역을 찾을 수 없습니다.");
      return;
    }
    const tx = await res.json();
    editingTxId = tx.id;
    currentModalType = tx.type;

    document.getElementById('txModal').classList.remove('hidden');
    document.getElementById('txDateInput').value = tx.date;
    document.getElementById('txAmountInput').value = tx.amount;
    document.getElementById('txMemoInput').value = tx.memo || '';
    document.getElementById('txModalTitle').textContent = "✏️ 가계부 내역 수정";
    document.getElementById('txSubmitBtn').textContent = "수정 완료";
    const delBtn = document.getElementById('txModalDeleteBtn');
    if (delBtn) delBtn.classList.remove('hidden');

    setTxModalType(tx.type);
    if (tx.account_id) {
      document.getElementById('txAccountInput').value = tx.account_id;
    }
    if (tx.to_account_id) {
      document.getElementById('txToAccountInput').value = tx.to_account_id;
    }
    if (tx.category) {
      selectCategoryChip(tx.category);
    }
    setTimeout(() => document.getElementById('txAmountInput').focus(), 100);
  } catch (err) {
    console.error("내역 조회 실패:", err);
  }
}

async function deleteCurrentEditingTx() {
  if (!editingTxId) return;
  if (!confirm("이 거래 내역을 삭제하시겠습니까?")) return;
  try {
    const res = await fetch(`/api/transactions/${editingTxId}`, { method: 'DELETE' });
    if (res.ok) {
      closeModal('txModal');
      showToast("내역이 삭제되었습니다.");
      loadTransactions();
      loadDashboard();
      loadAccounts();
    }
  } catch (err) {
    console.error(err);
  }
}

function setTxModalType(type) {
  currentModalType = type;
  const bExp = document.getElementById('txTypeExpenseBtn');
  const bInc = document.getElementById('txTypeIncomeBtn');
  const bTr = document.getElementById('txTypeTransferBtn');
  const toBox = document.getElementById('txToAccountBox');
  const catField = document.getElementById('txCategoryField');
  const modalTitle = document.getElementById('txModalTitle');

  bExp.className = "py-2 rounded-xl text-slate-600";
  bInc.className = "py-2 rounded-xl text-slate-600";
  bTr.className = "py-2 rounded-xl text-slate-600";

  if (type === 'expense') {
    bExp.className = "py-2 rounded-xl bg-white text-rose-600 shadow-xs font-black";
    toBox.classList.add('hidden');
    catField.classList.remove('hidden');
    modalTitle.textContent = editingTxId ? "✏️ 지출 내역 수정" : "- 쓴 돈 기록하기 (지출)";
    renderCategoryChips();
  } else if (type === 'income') {
    bInc.className = "py-2 rounded-xl bg-white text-emerald-600 shadow-xs font-black";
    toBox.classList.add('hidden');
    catField.classList.remove('hidden');
    modalTitle.textContent = editingTxId ? "✏️ 수입 내역 수정" : "+ 번 돈 기록하기 (수입)";
    renderCategoryChips();
  } else if (type === 'transfer') {
    bTr.className = "py-2 rounded-xl bg-white text-indigo-600 shadow-xs font-black";
    toBox.classList.remove('hidden');
    catField.classList.add('hidden');
    modalTitle.textContent = editingTxId ? "✏️ 이체 내역 수정" : "계좌 간 이체 (송금)";
  }
}

async function handleTxSubmit(e) {
  e.preventDefault();
  const date = document.getElementById('txDateInput').value;
  const amount = parseFloat(document.getElementById('txAmountInput').value);
  const memo = document.getElementById('txMemoInput').value;
  const accId = parseInt(document.getElementById('txAccountInput').value, 10);
  let toAccId = null;
  let category = document.getElementById('txCategoryInput').value;

  if (currentModalType === 'transfer') {
    toAccId = parseInt(document.getElementById('txToAccountInput').value, 10);
    category = "계좌이체";
    if (accId === toAccId) {
      alert("출금 통장과 입금 계좌는 서로 달라야 합니다.");
      return;
    }
  }

  try {
    let res;
    if (editingTxId) {
      res = await fetch(`/api/transactions/${editingTxId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: date,
          type: currentModalType,
          amount: amount,
          category: category,
          account_id: accId,
          to_account_id: toAccId,
          memo: memo
        })
      });
    } else {
      res = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: currentProfile,
          date: date,
          type: currentModalType,
          amount: amount,
          category: category,
          account_id: accId,
          to_account_id: toAccId,
          memo: memo
        })
      });
    }

    if (res.ok) {
      closeModal('txModal');
      showToast(editingTxId ? "내역이 성공적으로 수정되었습니다! ✨" : "성공적으로 저장되었습니다.");
      editingTxId = null;
      await loadAccounts();
      refreshCurrentView();
    } else {
      alert("내역 저장에 실패했습니다.");
    }
  } catch (err) {
    console.error(err);
  }
}

// Investment Modals
function openAddInvestmentModal() {
  document.getElementById('investModal').classList.remove('hidden');
  document.getElementById('invSymbolInput').value = '';
  document.getElementById('invNameInput').value = '';
  document.getElementById('invQuantityInput').value = '';
  document.getElementById('invAvgPriceInput').value = '';
  document.getElementById('invCurrentPriceInput').value = '';
}

function onInvestCategoryChange() {
  const cat = document.getElementById('invCategoryInput').value;
  const curr = document.getElementById('invCurrencyInput');
  curr.value = (cat === 'us_stock') ? 'USD' : 'KRW';
}

async function handleInvestSubmit(e) {
  e.preventDefault();
  const cat = document.getElementById('invCategoryInput').value;
  const sym = document.getElementById('invSymbolInput').value.trim();
  const name = document.getElementById('invNameInput').value.trim();
  const qty = parseFloat(document.getElementById('invQuantityInput').value);
  const avg = parseFloat(document.getElementById('invAvgPriceInput').value);
  const curPrice = parseFloat(document.getElementById('invCurrentPriceInput').value) || null;
  const curr = document.getElementById('invCurrencyInput').value;
  const linkAcc = document.getElementById('invCashAccountInput').value;

  try {
    const res = await fetch('/api/investments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile_id: currentProfile,
        symbol: sym,
        name: name,
        category: cat,
        quantity: qty,
        avg_buy_price: avg,
        current_price: curPrice,
        currency: curr,
        link_cash_account_id: linkAcc ? parseInt(linkAcc, 10) : null
      })
    });
    if (res.ok) {
      closeModal('investModal');
      showToast("종목이 추가되었습니다.");
      loadInvestments();
      loadAccounts();
      loadDashboard();
    }
  } catch (err) {
    console.error(err);
  }
}

// Trade Modal
let currentTradeType = 'buy';

function openTradeModal() {
  if (!investmentsData || investmentsData.items.length === 0) {
    alert("먼저 보유 종목을 1개 이상 추가해주세요.");
    return;
  }
  const select = document.getElementById('tradeHoldingSelect');
  select.innerHTML = investmentsData.items.map(i => `<option value="${i.id}">${i.name} (${i.symbol}) - 보유: ${i.quantity}</option>`).join('');

  document.getElementById('tradeDateInput').value = new Date().toISOString().slice(0, 10);
  document.getElementById('tradeQtyInput').value = '';
  document.getElementById('tradePriceInput').value = '';
  setTradeType('buy');
  document.getElementById('tradeModal').classList.remove('hidden');
}

function setTradeType(type) {
  currentTradeType = type;
  const bBuy = document.getElementById('tradeTypeBuy');
  const bSell = document.getElementById('tradeTypeSell');
  const bDiv = document.getElementById('tradeTypeDividend');
  const qtyBox = document.getElementById('tradeQtyLabel');
  const priceBox = document.getElementById('tradePriceLabel');

  bBuy.className = "py-2 rounded-lg text-slate-600";
  bSell.className = "py-2 rounded-lg text-slate-600";
  bDiv.className = "py-2 rounded-lg text-slate-600";

  if (type === 'buy') {
    bBuy.className = "py-2 rounded-lg bg-white text-indigo-600 shadow-xs font-bold";
    qtyBox.textContent = "추가 매수 수량";
    priceBox.textContent = "매수 단가";
  } else if (type === 'sell') {
    bSell.className = "py-2 rounded-lg bg-white text-rose-600 shadow-xs font-bold";
    qtyBox.textContent = "매도 수량";
    priceBox.textContent = "매도 단가";
  } else if (type === 'dividend') {
    bDiv.className = "py-2 rounded-lg bg-white text-emerald-600 shadow-xs font-bold";
    qtyBox.textContent = "수량 (선택/0가능)";
    priceBox.textContent = "총 배당금 금액";
  }
}

async function handleTradeSubmit(e) {
  e.preventDefault();
  const invId = parseInt(document.getElementById('tradeHoldingSelect').value, 10);
  const date = document.getElementById('tradeDateInput').value;
  const qty = parseFloat(document.getElementById('tradeQtyInput').value) || 0;
  const price = parseFloat(document.getElementById('tradePriceInput').value) || 0;
  const syncLedger = document.getElementById('tradeSyncLedger').checked;
  const accId = parseInt(document.getElementById('tradeAccountSelect').value, 10);

  try {
    const res = await fetch('/api/investments/trade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        investment_id: invId,
        date: date,
        type: currentTradeType,
        quantity: qty,
        price: price,
        sync_to_ledger: syncLedger,
        account_id: accId
      })
    });
    if (res.ok) {
      closeModal('tradeModal');
      showToast("거래 내역이 저장되었습니다.");
      loadInvestments();
      loadAccounts();
      loadDashboard();
    }
  } catch (err) {
    console.error(err);
  }
}

// Add / Edit Account Modal
let editingAccountId = null;

function openAddAccountModal() {
  editingAccountId = null;
  document.getElementById('accountModal').classList.remove('hidden');
  document.getElementById('accountModalTitle').textContent = "새 통장 / 지갑 추가";
  document.getElementById('accSubmitBtn').textContent = "계좌 추가";
  document.getElementById('accModalDeleteBtn').classList.add('hidden');
  document.getElementById('accCurrentBalanceBox').classList.add('hidden');
  document.getElementById('accNameInput').value = '';
  document.getElementById('accBalanceInput').value = '0';
  document.getElementById('accTypeInput').value = 'bank';
  setTimeout(() => document.getElementById('accNameInput').focus(), 100);
}

function openEditAccountModal(accId) {
  const acc = accountsList.find(a => a.id === accId);
  if (!acc) return;

  editingAccountId = accId;
  document.getElementById('accountModal').classList.remove('hidden');
  document.getElementById('accountModalTitle').textContent = `✏️ [${acc.name}] 잔액 및 정보 수정`;
  document.getElementById('accSubmitBtn').textContent = "수정 저장하기";
  document.getElementById('accModalDeleteBtn').classList.remove('hidden');

  const curBox = document.getElementById('accCurrentBalanceBox');
  curBox.classList.remove('hidden');
  document.getElementById('accCurrentBalancePreview').textContent = formatCurrency(acc.balance);

  document.getElementById('accNameInput').value = acc.name;
  document.getElementById('accTypeInput').value = acc.type;
  document.getElementById('accBalanceInput').value = acc.initial_balance !== undefined && acc.initial_balance !== null ? acc.initial_balance : acc.balance;
  setTimeout(() => document.getElementById('accBalanceInput').focus(), 100);
}

async function deleteCurrentEditingAccount() {
  if (!editingAccountId) return;
  if (!confirm("정말로 이 통장/지갑을 삭제하시겠습니까?\n(해당 계좌와 연결된 가계부 거래 내역이 있을 수 있습니다)")) return;

  try {
    const res = await fetch(`/api/accounts/${editingAccountId}`, { method: 'DELETE' });
    if (res.ok) {
      closeModal('accountModal');
      showToast("통장이 삭제되었습니다.");
      editingAccountId = null;
      await loadAccounts();
      loadDashboard();
    } else {
      alert("삭제에 실패했습니다.");
    }
  } catch (e) {
    console.error(e);
  }
}

async function handleAccountSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('accNameInput').value.trim();
  const type = document.getElementById('accTypeInput').value;
  const initialBal = parseFloat(document.getElementById('accBalanceInput').value) || 0;
  const isInvest = (type === 'investment' || type === 'crypto') ? 1 : 0;

  try {
    let res;
    if (editingAccountId) {
      res = await fetch(`/api/accounts/${editingAccountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          type: type,
          initial_balance: initialBal
        })
      });
    } else {
      res = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          profile_id: currentProfile,
          name: name,
          type: type,
          initial_balance: initialBal,
          balance: initialBal,
          is_investment: isInvest
        })
      });
    }

    if (res.ok) {
      closeModal('accountModal');
      showToast(editingAccountId ? "통장 잔액 및 정보가 수정되었습니다! ✨" : "새 통장이 추가되었습니다.");
      editingAccountId = null;
      await loadAccounts();
      loadDashboard();
    } else {
      alert("통장 저장에 실패했습니다.");
    }
  } catch (err) {
    console.error(err);
  }
}

// ----------------- Data Reset & Load Sample -----------------

async function confirmResetData() {
  if (!confirm("정말로 모든 가계부 내역과 투자 종목을 초기화(완전 빈 상태)하시겠습니까?")) return;
  try {
    const res = await fetch('/api/data/reset', { method: 'POST' });
    if (res.ok) {
      showToast("데이터가 깨끗하게 초기화되었습니다.");
      await loadAccounts();
      await loadCategories();
      refreshCurrentView();
    }
  } catch (e) {
    console.error(e);
  }
}

async function confirmLoadSample() {
  if (!confirm("둘러보기용 샘플 데이터(어머니 가계부 & 내 가계부 샘플)를 불러오시겠습니까?")) return;
  try {
    const res = await fetch('/api/data/load-sample', { method: 'POST' });
    if (res.ok) {
      showToast("샘플 데이터가 로드되었습니다.");
      await loadAccounts();
      await loadCategories();
      refreshCurrentView();
    }
  } catch (e) {
    console.error(e);
  }
}

// ----------------- Helpers -----------------

function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(val)) return '0원';
  const num = Math.round(val);
  return `${num.toLocaleString('ko-KR')}원`;
}

function formatCompact(val) {
  if (val >= 100000000) return `${(val / 100000000).toFixed(1)}억`;
  if (val >= 10000) return `${(val / 10000).toFixed(0)}만`;
  return val.toLocaleString();
}

function showToast(msg) {
  const toast = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  toast.classList.remove('translate-y-20', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 2600);
}

// ----------------- AI Receipt Scanner & Settings -----------------

function openReceiptCamera() {
  openModal('expense');
  setTimeout(() => {
    const input = document.getElementById('receiptFileInput');
    if (input) input.click();
  }, 150);
}

async function handleReceiptFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const overlay = document.getElementById('receiptScanningOverlay');
  if (overlay) overlay.classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/receipt/scan', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (!data.success) {
      if (data.error === 'GEMINI_API_KEY_REQUIRED') {
        alert("구글 Gemini API 키(무료)가 등록되지 않았습니다.\n\n[설정] 메뉴에서 무료 API 키를 1회 등록하시면 영수증 자동 입력이 바로 작동합니다!");
        switchTab('tab-settings');
        closeModal('txModal');
      } else {
        alert(data.message || "영수증 분석에 실패했습니다. 사진이 흐리거나 영수증 형태가 아닐 수 있습니다.");
      }
      return;
    }

    // AI 자동 추출 데이터 가계부 입력창에 채우기
    if (data.amount) {
      document.getElementById('txAmountInput').value = data.amount;
    }
    if (data.date) {
      document.getElementById('txDateInput').value = data.date;
    }
    if (data.memo || data.store_name) {
      document.getElementById('txMemoInput').value = data.memo || data.store_name;
    }
    if (data.category) {
      selectCategoryChip(data.category);
    }

    showToast("영수증을 AI가 성공적으로 읽었습니다! 📸");
  } catch (err) {
    console.error("영수증 스캔 실패:", err);
    alert("영수증 스캔 중 서버 오류가 발생했습니다: " + err.message);
  } finally {
    if (overlay) overlay.classList.add('hidden');
    event.target.value = '';
  }
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const settings = await res.json();
    if (settings && settings.gemini_api_key) {
      const input = document.getElementById('geminiApiKeyInput');
      if (input) input.value = settings.gemini_api_key;
    }
  } catch (err) {
    console.error("설정 로드 실패:", err);
  }
}

async function saveGeminiApiKey() {
  const keyInput = document.getElementById('geminiApiKeyInput');
  const key = keyInput.value.trim();
  if (!key) {
    alert("구글 Gemini API 키를 입력해주세요.");
    return;
  }
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gemini_api_key: key })
    });
    if (res.ok) {
      showToast("Gemini API 키가 안전하게 저장되었습니다! ✨");
    } else {
      const errText = await res.text();
      alert("API 키 저장에 실패했습니다. (서버 응답: " + errText.slice(0, 100) + ")");
    }
  } catch (err) {
    alert("저장 통신 오류: " + err.message);
  }
}
