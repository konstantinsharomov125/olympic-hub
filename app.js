let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

let currentViewMode = 'grid'; // 'grid', 'list', 'table'

let donutChartInstance = null;
let lineChartInstance = null;

const STANDARD_CATEGORIES = [
  "Олимпийское образование и просвещение",
  "Пропаганда, философия и культурология",
  "История и наследие олимпизма",
  "Этика, честная игра и антидопинг",
  "Политика, геополитика и глобальные вызовы",
  "Психология олимпийского спорта",
  "Менеджмент, маркетинг и экономика Игр",
  "Спортивная медицина, физиология и биомеханика",
  "Подготовка олимпийского резерва и тренировка",
  "Теория и методология олимпийского движения",
  "Другое"
];

document.addEventListener('DOMContentLoaded', async () => {
  await loadDataset();
  populateDropdownFilters();
  setupEventListeners();
  applyFilters();
});

// Загрузка базы данных
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
    console.error("❌ Не удалось загрузить базу данных web_data.json");
    document.getElementById('publications-feed').innerHTML = 
      `<div class="pub-card" style="grid-column:1/-1;"><p style="color:red;">❌ Ошибка: Не найден файл web_data.json</p></div>`;
  }
}

// Нормализация типов документов с расширенными категориями
function normalizeDocType(raw) {
  if (!raw) return 'Научная статья';
  const s = String(raw).toLowerCase();
  if (s.includes('диссертац') || s.includes('dissertation') || s.includes('thesis')) return 'Диссертация';
  if (s.includes('обзор') || s.includes('review')) return 'Обзорная статья';
  if (s.includes('учебн') || s.includes('manual') || s.includes('textbook')) return 'Учебное пособие';
  if (s.includes('book') || s.includes('монограф')) return 'Монография';
  if (s.includes('conf') || s.includes('материал') || s.includes('доклад') || s.includes('proceedings')) return 'Материалы конференции';
  if (s.includes('article') || s.includes('статья') || s.includes('journal')) return 'Научная статья';
  return 'Научная статья';
}

function normalizeLanguage(raw) {
  if (!raw) return 'Русский';
  const s = String(raw).toLowerCase();
  if (s.includes('ru') || s.includes('rus') || s.includes('рус')) return 'Русский';
  if (s.includes('en') || s.includes('eng') || s.includes('анг')) return 'Английский';
  if (s.includes('de') || s.includes('ger') || s.includes('нем')) return 'Немецкий';
  if (s.includes('fr') || s.includes('fre') || s.includes('фра')) return 'Французский';
  if (s.includes('es') || s.includes('spa') || s.includes('исп')) return 'Испанский';
  if (s.includes('zh') || s.includes('chi') || s.includes('кит')) return 'Китайский';
  return 'Другой язык';
}

function normalizeCountry(raw) {
  if (!raw || raw === 'NR' || raw === 'N/A' || raw === 'null' || raw === 'undefined' || raw === 'International' || raw === 'Международные') {
    return 'Другие страны';
  }
  const s = String(raw).trim();
  if (s.toLowerCase().includes('russia') || s.toLowerCase().includes('росси')) return 'Россия';
  if (s.toLowerCase().includes('japan') || s.toLowerCase().includes('япони')) return 'Япония';
  if (s.toLowerCase().includes('usa') || s.toLowerCase().includes('сша') || s.toLowerCase().includes('america')) return 'США';
  if (s.toLowerCase().includes('china') || s.toLowerCase().includes('китай')) return 'Китай';
  if (s.toLowerCase().includes('uk') || s.toLowerCase().includes('england') || s.toLowerCase().includes('великобрит')) return 'Великобритания';
  if (s.toLowerCase().includes('germany') || s.toLowerCase().includes('герман')) return 'Германия';
  if (s.toLowerCase().includes('france') || s.toLowerCase().includes('франц')) return 'Франция';
  return 'Другие страны';
}

function normalizeAuthors(item) {
  let a = item.authors || item.author || item.authors_str || '';
  if (Array.isArray(a)) a = a.join(', ');
  a = String(a).trim();
  if (!a || a.toLowerCase() === 'nr' || a.toLowerCase() === 'n/a' || a.toLowerCase() === 'unknown' || a.toLowerCase() === 'null') {
    return 'Автор не указан';
  }
  return a;
}

// Извлечение чистого года издания
function extractYear(item) {
  let y = item.year || item.publication_year || item.date || item.issued || item.created;
  if (y) {
    let match = String(y).match(/\b(18\d{2}|19\d{2}|20\d{2})\b/);
    if (match) return parseInt(match[1], 10);
  }
  let titleMatch = (item.title_original || item.title || item.article || '').match(/\b(18\d{2}|19\d{2}|20\d{2})\b/);
  if (titleMatch) return parseInt(titleMatch[1], 10);

  return 2020;
}

function getOriginalUrl(item) {
  const link = item.url || item.link || item.doi || item.source_url || item.pdf_url;
  if (link && typeof link === 'string' && link.startsWith('http')) return link;
  if (link && typeof link === 'string' && link.includes('doi.org')) return link.startsWith('http') ? link : 'https://' + link;
  
  const title = item.title_original || item.title || item.article || '';
  if (title) return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
  return 'https://scholar.google.com';
}

// Заполнение обновлённых выпадающих списков
function populateDropdownFilters() {
  const selectCat = document.getElementById('select-category');
  const selectDocType = document.getElementById('select-doctype');
  const selectCountry = document.getElementById('select-country');
  const selectLang = document.getElementById('select-language');

  selectCat.innerHTML = `<option value="ALL">Все направления</option>`;
  STANDARD_CATEGORIES.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    selectCat.appendChild(opt);
  });

  selectDocType.innerHTML = `<option value="ALL">Все типы документов</option>`;
  const docTypes = ['Научная статья', 'Обзорная статья', 'Монография', 'Диссертация', 'Учебное пособие', 'Материалы конференции'];
  docTypes.forEach(type => {
    const opt = document.createElement('option');
    opt.value = type;
    opt.textContent = type;
    selectDocType.appendChild(opt);
  });

  selectCountry.innerHTML = `<option value="ALL">Все страны</option>`;
  const countries = ['Россия', 'США', 'Китай', 'Германия', 'Франция', 'Великобритания', 'Япония', 'Другие страны'];
  countries.forEach(country => {
    const opt = document.createElement('option');
    opt.value = country;
    opt.textContent = country;
    selectCountry.appendChild(opt);
  });

  selectLang.innerHTML = `<option value="ALL">Все языки</option>`;
  const languages = ['Русский', 'Английский', 'Немецкий', 'Французский', 'Испанский', 'Другой язык'];
  languages.forEach(lang => {
    const opt = document.createElement('option');
    opt.value = lang;
    opt.textContent = lang;
    selectLang.appendChild(opt);
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

  document.getElementById('btn-reset').addEventListener('click', () => {
    document.getElementById('search-input').value = '';
    document.getElementById('select-category').value = 'ALL';
    document.getElementById('select-doctype').value = 'ALL';
    document.getElementById('select-country').value = 'ALL';
    document.getElementById('select-language').value = 'ALL';
    document.getElementById('year-from').value = '';
    document.getElementById('year-to').value = '';
    showFavOnly = false;
    document.getElementById('btn-fav-filter').style.backgroundColor = 'var(--bg-main)';
    document.getElementById('btn-fav-filter').style.color = 'var(--primary-navy)';
    applyFilters();
  });

  document.getElementById('btn-fav-filter').addEventListener('click', () => {
    showFavOnly = !showFavOnly;
    document.getElementById('btn-fav-filter').style.backgroundColor = showFavOnly ? 'var(--accent-gold)' : 'var(--bg-main)';
    document.getElementById('btn-fav-filter').style.color = showFavOnly ? '#FFFDF9' : 'var(--primary-navy)';
    applyFilters();
  });

  document.getElementById('btn-export-csv').addEventListener('click', exportToCSV);

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-view').addEventListener('click', (e) => {
    if (e.target.id === 'modal-view') closeModal();
  });
}

// Переключение между вариантами вида: Grid, List, Table
function changeViewMode(mode) {
  currentViewMode = mode;
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`btn-view-${mode}`)?.classList.add('active');
  renderCurrentView();
}

// Применение фильтрации
function applyFilters() {
  const searchVal = document.getElementById('search-input').value.toLowerCase().trim();
  const catVal = document.getElementById('select-category').value;
  const docTypeVal = document.getElementById('select-doctype').value;
  const countryVal = document.getElementById('select-country').value;
  const langVal = document.getElementById('select-language').value;
  const yearFrom = parseInt(document.getElementById('year-from').value, 10);
  const yearTo = parseInt(document.getElementById('year-to').value, 10);

  filteredData = rawData.filter((item, idx) => {
    if (showFavOnly && !favorites.has(idx)) return false;

    const cat = item.category || item.discipline || 'Другое';
    if (catVal !== 'ALL' && cat !== catVal) return false;

    const docType = normalizeDocType(item.type || item.document_type || item.doc_type);
    if (docTypeVal !== 'ALL' && docType !== docTypeVal) return false;

    const country = normalizeCountry(item.country || item.country_name);
    if (countryVal !== 'ALL' && country !== countryVal) return false;

    const lang = normalizeLanguage(item.language || item.lang);
    if (langVal !== 'ALL' && lang !== langVal) return false;

    const year = extractYear(item);
    if (!isNaN(yearFrom) && year < yearFrom) return false;
    if (!isNaN(yearTo) && year > yearTo) return false;

    const title = (item.title_original || item.title || item.article || '').toLowerCase();
    const summary = (item.summary || item.abstract || item.description || '').toLowerCase();
    const authors = normalizeAuthors(item).toLowerCase();

    if (searchVal && !title.includes(searchVal) && !summary.includes(searchVal) && !authors.includes(searchVal)) return false;

    return true;
  });

  document.getElementById('current-count').innerText = filteredData.length.toLocaleString('ru-RU');
  document.getElementById('header-stat-count').innerText = rawData.length.toLocaleString('ru-RU');
  document.getElementById('metric-total-val').innerText = rawData.length.toLocaleString('ru-RU');

  renderCurrentView();
  updateCharts(filteredData);
}

// Отрисовка данных в текущем выбранном виде
function renderCurrentView() {
  const container = document.getElementById('publications-feed');
  const items = filteredData.slice(0, 60);

  if (items.length === 0) {
    container.className = 'cards-grid';
    container.innerHTML = `
      <div class="pub-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
        <p style="color: var(--text-muted); font-family: var(--font-serif);">По вашему запросу не найдено исследований.</p>
      </div>`;
    return;
  }

  if (currentViewMode === 'grid') {
    container.className = 'cards-grid';
    container.innerHTML = items.map(item => renderGridCardHtml(item)).join('');
  } else if (currentViewMode === 'list') {
    container.className = 'cards-list';
    container.innerHTML = items.map(item => renderGridCardHtml(item)).join('');
  } else if (currentViewMode === 'table') {
    container.className = 'table-view-container';
    container.innerHTML = `
      <table class="academic-table">
        <thead>
          <tr>
            <th>Заглавие исследования</th>
            <th>Авторы</th>
            <th>Год</th>
            <th>Направление</th>
            <th>Тип</th>
            <th>Страна</th>
            <th>Ссылка</th>
          </tr>
        </thead>
        <tbody>
          ${items.map(item => renderTableRowHtml(item)).join('')}
        </tbody>
      </table>
    `;
  }
}

function renderGridCardHtml(item) {
  const title = item.title_original || item.title || item.article || 'Научное исследование без названия';
  const summary = item.summary || item.abstract || item.description || 'Аннотация к работе отсутствует в базе.';
  const category = item.category || item.discipline || 'Другое';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const country = normalizeCountry(item.country || item.country_name);
  const docType = normalizeDocType(item.type || item.document_type);
  const originalUrl = getOriginalUrl(item);

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
      
      <span class="badge-type">${docType}</span>
      
      <h3 class="pub-card-title" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</h3>
      
      <div class="pub-author-row">${escapeHtml(authors)} (${year})</div>
      <div class="pub-country-row">🌐 ${escapeHtml(country)}</div>

      <p class="pub-abstract-text">${escapeHtml(summary)}</p>

      <div class="pub-card-footer">
        <button class="btn-card-action" onclick="openModalByItemIndex(${realIndex})">
          Читать аннотацию
        </button>
        <a href="${originalUrl}" target="_blank" class="btn-link-original">
          Оригинал ↗
        </a>
      </div>
    </article>
  `;
}

function renderTableRowHtml(item) {
  const title = item.title_original || item.title || item.article || 'Без названия';
  const category = item.category || item.discipline || 'Другое';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const country = normalizeCountry(item.country || item.country_name);
  const docType = normalizeDocType(item.type || item.document_type);
  const originalUrl = getOriginalUrl(item);
  const realIndex = rawData.indexOf(item);

  return `
    <tr>
      <td><strong style="cursor:pointer; color:var(--primary-navy);" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</strong></td>
      <td>${escapeHtml(authors)}</td>
      <td>${year}</td>
      <td><span class="badge-cat" style="font-size:0.65rem;">${category}</span></td>
      <td>${docType}</td>
      <td>${escapeHtml(country)}</td>
      <td><a href="${originalUrl}" target="_blank" class="btn-link-original">Открыть ↗</a></td>
    </tr>
  `;
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

function openModalByItemIndex(realIndex) {
  const item = rawData[realIndex];
  if (!item) return;

  const title = item.title_original || item.title || item.article || 'Без названия';
  const summary = item.summary || item.abstract || item.description || 'Аннотация отсутствует.';
  const category = item.category || item.discipline || 'Другое';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const docType = normalizeDocType(item.type || item.document_type);
  const country = normalizeCountry(item.country || item.country_name);
  const originalUrl = getOriginalUrl(item);

  document.getElementById('modal-title').innerText = title;
  document.getElementById('modal-discipline').innerText = category;
  document.getElementById('modal-authors').innerText = authors;
  document.getElementById('modal-year').innerText = year;
  document.getElementById('modal-doctype').innerText = docType;
  document.getElementById('modal-country').innerText = country;
  document.getElementById('modal-abstract').innerText = summary;
  
  const linkElem = document.getElementById('modal-original-link');
  linkElem.href = originalUrl;

  document.getElementById('modal-citation').innerText = 
    `${authors}. ${title} // Олимпийский исследовательский портал. — ${year}. — URL: ${originalUrl}`;

  document.getElementById('modal-view').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-view').classList.remove('active');
}

/* ОБНОВЛЕНИЕ ДИАГРАММ С ИСПРАВЛЕННЫМ ГРАФИКОМ ДИНАМИКИ */
function updateCharts(dataset) {
  if (typeof Chart === 'undefined') return;

  // 1. Круговая диаграмма
  const catCounts = {};
  STANDARD_CATEGORIES.forEach(c => catCounts[c] = 0);
  dataset.forEach(item => {
    const c = item.category || item.discipline || 'Другое';
    if (catCounts[c] !== undefined) catCounts[c]++;
    else catCounts['Другое']++;
  });

  const donutCtx = document.getElementById('donutChart')?.getContext('2d');
  if (donutCtx) {
    if (donutChartInstance) donutChartInstance.destroy();

    donutChartInstance = new Chart(donutCtx, {
      type: 'doughnut',
      data: {
        labels: STANDARD_CATEGORIES.map(c => c.length > 18 ? c.slice(0, 16) + '...' : c),
        datasets: [{
          data: Object.values(catCounts),
          backgroundColor: [
            '#10233F', '#29496B', '#B38A4B', '#2E7D32', '#C62828',
            '#00838F', '#6A1B9A', '#D81B60', '#F57F17', '#4E342E', '#78909C'
          ],
          borderWidth: 2,
          borderColor: '#FFFDF9'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        cutout: '68%'
      }
    });
  }

  // 2. Исправленный график динамики по годам
  const yearCounts = {};
  dataset.forEach(item => {
    const y = extractYear(item);
    if (y && y >= 1896 && y <= 2026) {
      yearCounts[y] = (yearCounts[y] || 0) + 1;
    }
  });

  const sortedYears = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);
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
          backgroundColor: 'rgba(41, 73, 107, 0.12)',
          borderWidth: 2,
          fill: true,
          tension: 0.3,
          pointRadius: 2,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { 
            grid: { display: false },
            ticks: { 
              font: { size: 10 }, 
              color: '#697586',
              maxTicksLimit: 8,
              maxRotation: 0
            }
          },
          y: { 
            grid: { color: '#E4DED2' },
            ticks: { font: { size: 10 }, color: '#697586' },
            beginAtZero: true
          }
        }
      }
    });
  }
}

function exportToCSV() {
  let csvContent = "data:text/csv;charset=utf-8,Category,Title,Authors,Year,Country,URL\n";
  filteredData.forEach(item => {
    const cat = (item.category || item.discipline || '').replace(/"/g, '""');
    const title = (item.title_original || item.title || item.article || '').replace(/"/g, '""');
    const authors = normalizeAuthors(item).replace(/"/g, '""');
    const year = extractYear(item);
    const country = normalizeCountry(item.country || item.country_name).replace(/"/g, '""');
    const url = getOriginalUrl(item);
    csvContent += `"${cat}","${title}","${authors}","${year}","${country}","${url}"\n`;
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