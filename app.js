let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

let donutChartInstance = null;
let lineChartInstance = null;

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
  initCategoryDropdown();
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
      // Переходим к следующему пути
    }
  }

  if (!loaded) {
    console.error(" Ошибка загрузки базы web_data.json");
    document.getElementById('publications-feed').innerHTML = 
      `<div class="pub-card"><p style="color:red;"> Ошибка: Не удалось загрузить базу web_data.json</p></div>`;
  }
}

function initCategoryDropdown() {
  const select = document.getElementById('select-category');
  CATEGORIES.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    select.appendChild(opt);
  });
}

function setupEventListeners() {
  document.getElementById('search-input').addEventListener('input', applyFilters);
  document.getElementById('select-category').addEventListener('change', applyFilters);
  document.getElementById('select-doctype').addEventListener('change', applyFilters);
  document.getElementById('select-country').addEventListener('change', applyFilters);
  document.getElementById('select-language').addEventListener('change', applyFilters);
  document.getElementById('year-from').addEventListener('input', applyFilters);
  document.getElementById('year-to').addEventListener('input', applyFilters);

  // Кнопка сброса
  document.getElementById('btn-reset').addEventListener('click', () => {
    document.getElementById('search-input').value = '';
    document.getElementById('select-category').value = 'ALL';
    document.getElementById('select-doctype').value = 'ALL';
    document.getElementById('select-country').value = 'ALL';
    document.getElementById('select-language').value = 'ALL';
    document.getElementById('year-from').value = '';
    document.getElementById('year-to').value = '';
    showFavOnly = false;
    applyFilters();
  });

  // Кнопка Избранного
  document.getElementById('btn-fav-filter').addEventListener('click', () => {
    showFavOnly = !showFavOnly;
    document.getElementById('btn-fav-filter').style.backgroundColor = showFavOnly ? 'var(--accent-gold)' : 'var(--bg-main)';
    document.getElementById('btn-fav-filter').style.color = showFavOnly ? '#FFFDF9' : 'var(--primary-navy)';
    applyFilters();
  });

  // Экспорт CSV
  document.getElementById('btn-export-csv').addEventListener('click', exportToCSV);

  // Модальное окно
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-view').addEventListener('click', (e) => {
    if (e.target.id === 'modal-view') closeModal();
  });
}

function applyFilters() {
  const searchVal = document.getElementById('search-input').value.toLowerCase().trim();
  const catVal = document.getElementById('select-category').value;
  const docTypeVal = document.getElementById('select-doctype').value;
  const yearFrom = parseInt(document.getElementById('year-from').value, 10);
  const yearTo = parseInt(document.getElementById('year-to').value, 10);

  filteredData = rawData.filter((item, idx) => {
    if (showFavOnly && !favorites.has(idx)) return false;

    const cat = item.category || item.discipline || '';
    if (catVal !== 'ALL' && cat !== catVal) return false;

    const docType = item.type || 'Научная статья';
    if (docTypeVal !== 'ALL' && docType !== docTypeVal) return false;

    const year = parseInt(item.year || 2020, 10);
    if (!isNaN(yearFrom) && year < yearFrom) return false;
    if (!isNaN(yearTo) && year > yearTo) return false;

    const title = (item.title_original || item.title || '').toLowerCase();
    const summary = (item.summary || item.abstract || '').toLowerCase();
    if (searchVal && !title.includes(searchVal) && !summary.includes(searchVal)) return false;

    return true;
  });

  document.getElementById('current-count').innerText = filteredData.length.toLocaleString('ru-RU');
  document.getElementById('header-stat-count').innerText = rawData.length.toLocaleString('ru-RU');
  document.getElementById('metric-total-val').innerText = rawData.length.toLocaleString('ru-RU');

  renderPublicationsGrid(filteredData.slice(0, 60));
  updateCharts(filteredData);
}

function renderPublicationsGrid(items) {
  const feed = document.getElementById('publications-feed');

  if (items.length === 0) {
    feed.innerHTML = `
      <div class="pub-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
        <p style="color: var(--text-muted); font-family: var(--font-serif);">По вашему запросу не найдено исследований.</p>
      </div>`;
    return;
  }

  feed.innerHTML = items.map((item, index) => {
    const title = item.title_original || item.title || 'Научное исследование без названия';
    const summary = item.summary || item.abstract || 'Аннотация к работе отсутствует в базе.';
    const category = item.category || item.discipline || 'Олимпизм';
    const realIndex = rawData.indexOf(item);
    const isFav = favorites.has(realIndex);

    return `
      <article class="pub-card">
        <div class="pub-badge-group">
          <span class="badge-cat">${category}</span>
          <button style="background:none; border:none; cursor:pointer; font-size:1.1rem; color:${isFav ? 'var(--accent-gold)' : '#ccc'};" onclick="toggleFavorite(${realIndex})">
            ★
          </button>
        </div>
        <h3 class="pub-card-title" onclick="openModal(${index})">${escapeHtml(title)}</h3>
        <p class="pub-abstract-text">${escapeHtml(summary)}</p>
        <div class="pub-card-footer">
          <button class="btn-card-action" onclick="openModal(${index})">
            Читать аннотацию
          </button>
          <span class="badge-type">Научная статья</span>
        </div>
      </article>
    `;
  }).join('');
}

function toggleFavorite(index) {
  if (favorites.has(index)) {
    favorites.delete(index);
  } else {
    favorites.add(index);
  }
  document.getElementById('fav-count').innerText = favorites.size;
  applyFilters();
}

/* ОНИМАЦИОННЫЕ ДИАГРАММЫ С ИСПОЛЬЗОВАНИЕМ CHART.JS */
function updateCharts(dataset) {
  if (typeof Chart === 'undefined') return;

  // 1. Подсчет категорий для круговой диаграммы
  const catCounts = {};
  CATEGORIES.forEach(c => catCounts[c] = 0);
  dataset.forEach(item => {
    const c = item.category || item.discipline;
    if (catCounts[c] !== undefined) catCounts[c]++;
  });

  const donutCtx = document.getElementById('donutChart')?.getContext('2d');
  if (donutCtx) {
    if (donutChartInstance) donutChartInstance.destroy();

    donutChartInstance = new Chart(donutCtx, {
      type: 'doughnut',
      data: {
        labels: CATEGORIES.map(c => c.length > 20 ? c.slice(0, 18) + '...' : c),
        datasets: [{
          data: Object.values(catCounts),
          backgroundColor: [
            '#10233F', '#29496B', '#B38A4B', '#2E7D32', '#C62828',
            '#00838F', '#6A1B9A', '#D81B60', '#F57F17', '#4E342E'
          ],
          borderWidth: 2,
          borderColor: '#FFFDF9'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        cutout: '68%'
      }
    });
  }

  // 2. Подсчет годов для линейного графика
  const yearCounts = {};
  dataset.forEach(item => {
    const y = parseInt(item.year || 2020, 10);
    if (y >= 1980 && y <= 2026) {
      yearCounts[y] = (yearCounts[y] || 0) + 1;
    }
  });

  const sortedYears = Object.keys(yearCounts).sort();
  const lineCtx = document.getElementById('lineChart')?.getContext('2d');

  if (lineCtx) {
    if (lineChartInstance) lineChartInstance.destroy();

    lineChartInstance = new Chart(lineCtx, {
      type: 'line',
      data: {
        labels: sortedYears,
        datasets: [{
          label: 'Публикации',
          data: sortedYears.map(y => yearCounts[y]),
          borderColor: '#10233F',
          backgroundColor: 'rgba(41, 73, 107, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: '#E4DED2' } }
        }
      }
    });
  }
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
    `${title} // Olympic Research Hub: Международная система олимпийских исследований. — 2026. — URL: https://olympic-hub.ru`;

  document.getElementById('modal-view').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-view').classList.remove('active');
}

function exportToCSV() {
  let csvContent = "data:text/csv;charset=utf-8,Category,Title,Abstract\n";
  filteredData.forEach(item => {
    const cat = (item.category || item.discipline || '').replace(/"/g, '""');
    const title = (item.title_original || item.title || '').replace(/"/g, '""');
    csvContent += `"${cat}","${title}"\n`;
  });
  
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "olympic_research_data.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}