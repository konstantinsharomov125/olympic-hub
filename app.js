let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

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
  "Теория и методология олимпийского движения"
];

document.addEventListener('DOMContentLoaded', async () => {
  await loadDataset();
  populateDropdownFilters();
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
      // Пробуем следующий путь
    }
  }

  if (!loaded) {
    console.error("❌ Не удалось загрузить базу данных web_data.json");
    document.getElementById('publications-feed').innerHTML = 
      `<div class="pub-card" style="grid-column:1/-1;"><p style="color:red;"> Ошибка: Не найден файл web_data.json</p></div>`;
  }
}

// Заполнение выпадающих списков на основе реальных данных из файла
function populateDropdownFilters() {
  const selectCat = document.getElementById('select-category');
  const selectDocType = document.getElementById('select-doctype');
  const selectCountry = document.getElementById('select-country');
  const selectLang = document.getElementById('select-language');

  const categories = new Set(STANDARD_CATEGORIES);
  const docTypes = new Set();
  const countries = new Set();
  const languages = new Set();

  rawData.forEach(item => {
    if (item.category || item.discipline) categories.add(item.category || item.discipline);
    if (item.type || item.document_type || item.doc_type) docTypes.add(item.type || item.document_type || item.doc_type);
    if (item.country || item.country_name) countries.add(item.country || item.country_name);
    if (item.language || item.lang) languages.add(item.language || item.lang);
  });

  // Направление
  categories.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat;
    opt.textContent = cat;
    selectCat.appendChild(opt);
  });

  // Тип документа
  if (docTypes.size === 0) ["Научная статья", "Монография", "Материалы конференции"].forEach(t => docTypes.add(t));
  docTypes.forEach(type => {
    const opt = document.createElement('option');
    opt.value = type;
    opt.textContent = type;
    selectDocType.appendChild(opt);
  });

  // Страна
  if (countries.size === 0) ["Россия", "Международные", "Страна не распознана"].forEach(c => countries.add(c));
  countries.forEach(country => {
    const opt = document.createElement('option');
    opt.value = country;
    opt.textContent = country;
    selectCountry.appendChild(opt);
  });

  // Язык
  if (languages.size === 0) ["Русский", "Английский", "Не указан"].forEach(l => languages.add(l));
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

  // Сброс фильтров
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

  // Переключение фильтра Избранного
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

function getAuthorsStr(item) {
  if (Array.isArray(item.authors)) return item.authors.join(', ');
  if (typeof item.authors === 'string' && item.authors.trim()) return item.authors.trim();
  if (typeof item.author === 'string' && item.author.trim()) return item.author.trim();
  if (item.authors_str) return item.authors_str;
  return 'Автор не указан';
}

function getOriginalUrl(item) {
  const link = item.url || item.link || item.doi || item.source_url || item.pdf_url;
  if (link && typeof link === 'string' && link.startsWith('http')) return link;
  if (link && typeof link === 'string' && link.includes('doi.org')) return link.startsWith('http') ? link : 'https://' + link;
  
  const title = item.title_original || item.title || item.article || '';
  if (title) return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
  return 'https://scholar.google.com';
}

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

    const cat = item.category || item.discipline || '';
    if (catVal !== 'ALL' && cat !== catVal) return false;

    const docType = item.type || item.document_type || item.doc_type || 'Научная статья';
    if (docTypeVal !== 'ALL' && docType !== docTypeVal) return false;

    const country = item.country || item.country_name || 'Страна не распознана';
    if (countryVal !== 'ALL' && country !== countryVal) return false;

    const lang = item.language || item.lang || 'Не указан';
    if (langVal !== 'ALL' && lang !== langVal) return false;

    const year = parseInt(item.year || item.publication_year || 2020, 10);
    if (!isNaN(yearFrom) && year < yearFrom) return false;
    if (!isNaN(yearTo) && year > yearTo) return false;

    const title = (item.title_original || item.title || item.article || '').toLowerCase();
    const summary = (item.summary || item.abstract || item.description || '').toLowerCase();
    const authors = getAuthorsStr(item).toLowerCase();

    if (searchVal && !title.includes(searchVal) && !summary.includes(searchVal) && !authors.includes(searchVal)) return false;

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

  feed.innerHTML = items.map((item) => {
    const title = item.title_original || item.title || item.article || 'Научное исследование без названия';
    const summary = item.summary || item.abstract || item.description || 'Аннотация к работе отсутствует в базе.';
    const category = item.category || item.discipline || 'Олимпизм';
    const authors = getAuthorsStr(item);
    const year = item.year || item.publication_year || '2020';
    const country = item.country || item.country_name || 'Страна не распознана';
    const docType = item.type || item.document_type || 'Научная статья';
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

function openModalByItemIndex(realIndex) {
  const item = rawData[realIndex];
  if (!item) return;

  const title = item.title_original || item.title || item.article || 'Без названия';
  const summary = item.summary || item.abstract || item.description || 'Аннотация отсутствует.';
  const category = item.category || item.discipline || 'Олимпизм';
  const authors = getAuthorsStr(item);
  const year = item.year || item.publication_year || '—';
  const docType = item.type || item.document_type || 'Научная статья';
  const country = item.country || item.country_name || 'Страна не распознана';
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
    `${authors}. ${title} // Olympic Research Hub. — ${year}. — URL: ${originalUrl}`;

  document.getElementById('modal-view').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-view').classList.remove('active');
}

/* ГРАФИКИ CHART.JS */
function updateCharts(dataset) {
  if (typeof Chart === 'undefined') return;

  const catCounts = {};
  STANDARD_CATEGORIES.forEach(c => catCounts[c] = 0);
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
        labels: STANDARD_CATEGORIES.map(c => c.length > 18 ? c.slice(0, 16) + '...' : c),
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
        plugins: { legend: { display: false } },
        cutout: '68%'
      }
    });
  }

  const yearCounts = {};
  dataset.forEach(item => {
    const y = parseInt(item.year || item.publication_year || 2020, 10);
    if (y >= 1896 && y <= 2026) {
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

function exportToCSV() {
  let csvContent = "data:text/csv;charset=utf-8,Category,Title,Authors,Year,Country,URL\n";
  filteredData.forEach(item => {
    const cat = (item.category || item.discipline || '').replace(/"/g, '""');
    const title = (item.title_original || item.title || '').replace(/"/g, '""');
    const authors = getAuthorsStr(item).replace(/"/g, '""');
    const year = item.year || item.publication_year || '';
    const country = (item.country || item.country_name || '').replace(/"/g, '""');
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