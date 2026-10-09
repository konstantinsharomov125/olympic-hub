let rawData = [];
let filteredData = [];
let activeCategory = 'ALL';

const CATEGORIES = [
  "Олимпийское образование и просвещение",
  "Пропаганда, философия и культурология",
  "История и наследие олимпизма",
  "Этика, честная игра и антидопинг",
  "Политика, геополитика и глобальные вызовы",
  "Психология олимпийского спорта",
  "Менеджмент, маркетинг и экономика Игр",
  "Спортивная медицина, физиология и биомеханика",
  "Подготовка олимпийского резерва и тренировка",
  "Теория и методология олимпийского движения"
];

document.addEventListener('DOMContentLoaded', async () => {
  await loadDataset();
  renderCategorySidebar();
  renderAnalyticsDashboard();
  setupEventListeners();
  applyFilters();
});

async function loadDataset() {
  const paths = ['generated/web_data.json', 'data/web_data.json', 'web_data.json'];
  let loaded = false;

  for (const path of paths) {
    try {
      const res = await fetch(path);
      if (res.ok) {
        const data = await res.json();
        rawData = Array.isArray(data) ? data : (data.items || data.records || data.data || []);
        filteredData = [...rawData];
        loaded = true;
        break;
      }
    } catch (e) {
      // Ищем по следующему пути
    }
  }

  if (!loaded) {
    console.error("Ошибка загрузки файла web_data.json");
    document.getElementById('publications-feed').innerHTML = 
      `<div class="publication-card"><p style="color:red;">❌ Ошибка: Не удалось загрузить базу web_data.json</p></div>`;
  }
}

// Отрисовка левого сайдбара с фильтрами
function renderCategorySidebar() {
  const container = document.getElementById('category-list');
  const counts = getCategoryCounts(rawData);

  document.getElementById('metric-total').innerText = rawData.length.toLocaleString('ru-RU');

  const html = CATEGORIES.map(cat => `
    <li class="category-item">
      <button data-category="${cat}" class="${activeCategory === cat ? 'active' : ''}">
        <span>${cat}</span>
        <span class="category-count">${counts[cat] || 0}</span>
      </button>
    </li>
  `).join('');

  container.innerHTML = `
    <li class="category-item">
      <button data-category="ALL" class="${activeCategory === 'ALL' ? 'active' : ''}">
        <span>Все направления</span>
        <span class="category-count">${rawData.length}</span>
      </button>
    </li>
  ` + html;
}

// Отрисовка анимированных графиков аналитики
function renderAnalyticsDashboard() {
  const container = document.getElementById('chart-bars-container');
  const counts = getCategoryCounts(rawData);
  const maxCount = Math.max(...Object.values(counts), 1);

  const html = CATEGORIES.map(cat => {
    const count = counts[cat] || 0;
    const percentage = Math.round((count / (rawData.length || 1)) * 100);
    const barWidth = Math.round((count / maxCount) * 100);

    return `
      <div class="chart-bar-item">
        <div class="chart-bar-meta">
          <span><strong>${cat}</strong></span>
          <span>${count} работ (${percentage}%)</span>
        </div>
        <div class="chart-bar-track">
          <div class="chart-bar-fill" data-width="${barWidth}%" style="width: 0%;"></div>
        </div>
      </div>
    `;
  }).join('');

  container.innerHTML = html;

  // Плавный запуск анимации полос при загрузке
  setTimeout(() => {
    document.querySelectorAll('.chart-bar-fill').forEach(bar => {
      bar.style.width = bar.dataset.width;
    });
  }, 100);
}

function getCategoryCounts(dataArray) {
  const counts = {};
  CATEGORIES.forEach(cat => counts[cat] = 0);
  
  dataArray.forEach(item => {
    const cat = item.category || item.discipline;
    if (counts[cat] !== undefined) counts[cat]++;
  });
  return counts;
}

function setupEventListeners() {
  document.getElementById('search-input').addEventListener('input', applyFilters);
  document.getElementById('sort-select').addEventListener('change', applyFilters);
  
  // Клик по категориям
  document.getElementById('category-list').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    
    activeCategory = btn.dataset.category;
    document.querySelectorAll('#category-list button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    applyFilters();
  });

  // Сброс фильтров
  document.getElementById('reset-filters-btn').addEventListener('click', () => {
    document.getElementById('search-input').value = '';
    activeCategory = 'ALL';
    document.querySelectorAll('#category-list button').forEach(b => b.classList.remove('active'));
    document.querySelector('#category-list button[data-category="ALL"]').classList.add('active');
    applyFilters();
  });

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-view').addEventListener('click', (e) => {
    if (e.target.id === 'modal-view') closeModal();
  });
}

function switchMainTab(tab) {
  const analyticsSec = document.getElementById('analytics-section');
  const feedBtn = document.getElementById('tab-feed-btn');
  const analyticsBtn = document.getElementById('tab-analytics-btn');

  if (tab === 'analytics') {
    analyticsSec.style.display = 'flex';
    feedBtn.classList.remove('active');
    analyticsBtn.classList.add('active');
    
    // Перезапуск анимации полос
    document.querySelectorAll('.chart-bar-fill').forEach(bar => {
      bar.style.width = '0%';
      setTimeout(() => bar.style.width = bar.dataset.width, 50);
    });
  } else {
    analyticsSec.style.display = 'flex'; // Показываем панель в общем виде
    analyticsBtn.classList.remove('active');
    feedBtn.classList.add('active');
  }
}

function applyFilters() {
  const query = document.getElementById('search-input').value.toLowerCase().trim();
  const sortBy = document.getElementById('sort-select').value;

  filteredData = rawData.filter(item => {
    const cat = item.category || item.discipline || '';
    const matchesCat = (activeCategory === 'ALL') || (cat === activeCategory);
    
    const title = (item.title_original || item.title || '').toLowerCase();
    const summary = (item.summary || item.abstract || '').toLowerCase();
    const matchesSearch = !query || title.includes(query) || summary.includes(query);

    return matchesCat && matchesSearch;
  });

  if (sortBy === 'title') {
    filteredData.sort((a, b) => {
      const tA = (a.title_original || a.title || '').toLowerCase();
      const tB = (b.title_original || b.title || '').toLowerCase();
      return tA.localeCompare(tB);
    });
  }

  document.getElementById('current-count').innerText = filteredData.length;
  renderPublicationsFeed(filteredData.slice(0, 60));
}

function renderPublicationsFeed(items) {
  const feed = document.getElementById('publications-feed');
  
  if (items.length === 0) {
    feed.innerHTML = `
      <div class="publication-card" style="text-align: center; padding: 3rem;">
        <p style="color: var(--text-muted); font-family: var(--font-serif);">По вашему запросу не найдено научных публикаций.</p>
      </div>`;
    return;
  }

  feed.innerHTML = items.map((item, index) => {
    const title = item.title_original || item.title || 'Научная публикация без названия';
    const summary = item.summary || item.abstract || 'Аннотация к исследованию отсутствует в базе данных.';
    const category = item.category || item.discipline || 'Олимпизм';

    return `
      <article class="publication-card">
        <div class="card-header-meta">
          <span class="discipline-tag">${category}</span>
          <span class="pub-year">Рецензируемое издание</span>
        </div>
        <h3 class="pub-title" onclick="openModal(${index})">${escapeHtml(title)}</h3>
        <p class="pub-abstract">${escapeHtml(summary)}</p>
        <div class="card-footer">
          <button class="btn-academic btn-academic-gold" onclick="openModal(${index})">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
            Читать аннотацию
          </button>
          <button class="btn-academic" onclick="copyTitle('${escapeHtmlForJs(title)}')">
            Скопировать заглавие
          </button>
        </div>
      </article>
    `;
  }).join('');
}

function openModal(index) {
  const item = filteredData[index];
  if (!item) return;

  const title = item.title_original || item.title || 'Без названия';
  const summary = item.summary || item.abstract || 'Аннотация отсутствует.';
  const category = item.category || item.discipline || 'Олимпизм';

  document.getElementById('modal-title').innerText = title;
  document.getElementById('modal-discipline').innerText = category;
  document.getElementById('modal-abstract').innerText = summary;
  
  document.getElementById('modal-citation').innerText = 
    `${title} // Portalis Olympica: Международный архив олимпийских исследований. — 2026. — URL: https://olympic-hub.ru`;

  document.getElementById('modal-view').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-view').classList.remove('active');
}

function copyTitle(titleText) {
  navigator.clipboard.writeText(titleText);
  alert('Заглавие скопировано!');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeHtmlForJs(str) {
  return String(str)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '&quot;');
}