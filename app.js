let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

let currentPage = 1;
const itemsPerPage = 60;

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
    const container = document.getElementById('publications-feed');
    if (container) {
      container.innerHTML = `<div class="pub-card" style="grid-column:1/-1;"><p style="color:red;">❌ Ошибка: Не найден файл web_data.json</p></div>`;
    }
  }
}

function normalizeDocType(raw) {
  if (!raw) return 'Научная статья';
  const s = String(raw).toLowerCase();
  if (s.includes('диссертац') || s.includes('dissertation') || s.includes('thesis')) return 'Диссертация';
  if (s.includes('обзор') || s.includes('review')) return 'Обзорная статья';
  if (s.includes('учебн') || s.includes('manual') || s.includes('textbook')) return 'Учебное пособие';
  if (s.includes('book') || s.includes('монограф')) return 'Монография';
  if (s.includes('conf') || s.includes('материал') || s.includes('доклад')) return 'Материалы конференции';
  return 'Научная статья';
}

function normalizeLanguage(raw) {
  if (!raw) return 'Русский';
  const s = String(raw).toLowerCase();
  if (s.includes('ru') || s.includes('rus') || s.includes('рус')) return 'Русский';
  if (s.includes('en') || s.includes('eng') || s.includes('анг')) return 'Английский';
  if (s.includes('de') || s.includes('ger')) return 'Немецкий';
  if (s.includes('fr') || s.includes('fre')) return 'Французский';
  if (s.includes('es') || s.includes('spa')) return 'Испанский';
  return 'Другой язык';
}

function normalizeCountry(raw) {
  if (!raw || raw === 'NR' || raw === 'N/A' || raw === 'null') return 'Другие страны';
  const s = String(raw).trim();
  if (s.toLowerCase().includes('russia') || s.toLowerCase().includes('росси')) return 'Россия';
  if (s.toLowerCase().includes('usa') || s.toLowerCase().includes('сша')) return 'США';
  if (s.toLowerCase().includes('china') || s.toLowerCase().includes('китай')) return 'Китай';
  if (s.toLowerCase().includes('germany') || s.toLowerCase().includes('герман')) return 'Германия';
  if (s.toLowerCase().includes('france') || s.toLowerCase().includes('франц')) return 'Франция';
  if (s.toLowerCase().includes('uk') || s.toLowerCase().includes('england')) return 'Великобритания';
  if (s.toLowerCase().includes('japan') || s.toLowerCase().includes('япони')) return 'Япония';
  return 'Другие страны';
}

function normalizeAuthors(item) {
  let a = item.authors || item.author || item.authors_str || '';
  if (Array.isArray(a)) a = a.join(', ');
  a = String(a).trim();
  if (!a || a.toLowerCase() === 'nr' || a.toLowerCase() === 'n/a') return 'Автор не указан';
  return a;
}

function extractYear(item) {
  let y = item.year || item.publication_year || item.date;
  if (y) {
    let match = String(y).match(/\b(18\d{2}|19\d{2}|20\d{2})\b/);
    if (match) return parseInt(match[1], 10);
  }
  let titleMatch = (item.title_original || item.title || '').match(/\b(18\d{2}|19\d{2}|20\d{2})\b/);
  if (titleMatch) return parseInt(titleMatch[1], 10);
  return 2026;
}

function getOriginalUrl(item) {
  const link = item.url || item.link || item.doi;
  if (link && typeof link === 'string' && link.startsWith('http')) return link;
  const title = item.title_original || item.title || '';
  if (title) return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
  return 'https://scholar.google.com';
}

function generateGostCitation(item) {
    let authors = normalizeAuthors(item);
    let title = item.title_original || item.title || "Без названия";
    let year = extractYear(item);
    let originalUrl = getOriginalUrl(item);
    let citation = `${authors}. ${title} // Научная публикация. – ${year}. – URL: ${originalUrl} (дата обращения: 11.10.2026).`;
    return citation;
}

window.copyGostCitation = function(buttonElement, realIndex) {
    const item = rawData[realIndex];
    if (!item) return;
    const citation = generateGostCitation(item);
    navigator.clipboard.writeText(citation).then(() => {
        let originalText = buttonElement.innerText;
        buttonElement.innerText = "✅ Скопировано!";
        setTimeout(() => { buttonElement.innerText = originalText; }, 2000);
    });
};

function populateDropdownFilters() {
  const selectCat = document.getElementById('select-category');
  if (selectCat) {
    selectCat.innerHTML = `<option value="ALL">Все направления</option>`;
    STANDARD_CATEGORIES.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      selectCat.appendChild(opt);
    });
  }

  const selectDocType = document.getElementById('select-doctype');
  if (selectDocType) {
    selectDocType.innerHTML = `<option value="ALL">Все типы документов</option>`;
    ['Научная статья', 'Обзорная статья', 'Монография', 'Диссертация', 'Учебное пособие', 'Материалы конференции'].forEach(type => {
      const opt = document.createElement('option');
      opt.value = type;
      opt.textContent = type;
      selectDocType.appendChild(opt);
    });
  }

  const selectCountry = document.getElementById('select-country');
  if (selectCountry) {
    selectCountry.innerHTML = `<option value="ALL">Все страны</option>`;
    ['Россия', 'США', 'Китай', 'Германия', 'Франция', 'Великобритания', 'Япония', 'Другие страны'].forEach(c => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      selectCountry.appendChild(opt);
    });
  }

  const selectLang = document.getElementById('select-language');
  if (selectLang) {
    selectLang.innerHTML = `<option value="ALL">Все языки</option>`;
    ['Русский', 'Английский', 'Немецкий', 'Французский', 'Испанский', 'Другой язык'].forEach(l => {
      const opt = document.createElement('option');
      opt.value = l;
      opt.textContent = l;
      selectLang.appendChild(opt);
    });
  }
}

function setupEventListeners() {
  document.getElementById('search-input')?.addEventListener('input', () => { currentPage = 1; applyFilters(); });
  document.getElementById('select-category')?.addEventListener('change', () => { currentPage = 1; applyFilters(); });
  document.getElementById('select-doctype')?.addEventListener('change', () => { currentPage = 1; applyFilters(); });
  document.getElementById('select-country')?.addEventListener('change', () => { currentPage = 1; applyFilters(); });
  document.getElementById('select-language')?.addEventListener('change', () => { currentPage = 1; applyFilters(); });
  document.getElementById('select-sort')?.addEventListener('change', () => { currentPage = 1; applyFilters(); });
  document.getElementById('year-from')?.addEventListener('input', () => { currentPage = 1; applyFilters(); });
  document.getElementById('year-to')?.addEventListener('input', () => { currentPage = 1; applyFilters(); });

  document.getElementById('btn-reset')?.addEventListener('click', () => {
    if (document.getElementById('search-input')) document.getElementById('search-input').value = '';
    if (document.getElementById('select-category')) document.getElementById('select-category').value = 'ALL';
    if (document.getElementById('select-doctype')) document.getElementById('select-doctype').value = 'ALL';
    if (document.getElementById('select-country')) document.getElementById('select-country').value = 'ALL';
    if (document.getElementById('select-language')) document.getElementById('select-language').value = 'ALL';
    if (document.getElementById('select-sort')) document.getElementById('select-sort').value = 'year-desc';
    if (document.getElementById('year-from')) document.getElementById('year-from').value = '';
    if (document.getElementById('year-to')) document.getElementById('year-to').value = '';
    showFavOnly = false;
    const favBtn = document.getElementById('btn-fav-filter');
    if (favBtn) {
      favBtn.style.backgroundColor = '';
      favBtn.style.color = '';
    }
    currentPage = 1;
    applyFilters();
  });

  document.getElementById('btn-fav-filter')?.addEventListener('click', () => {
    showFavOnly = !showFavOnly;
    const favBtn = document.getElementById('btn-fav-filter');
    if (favBtn) {
      favBtn.style.backgroundColor = showFavOnly ? 'var(--primary-navy)' : '';
      favBtn.style.color = showFavOnly ? '#FFFDF9' : '';
    }
    currentPage = 1;
    applyFilters();
  });

  document.getElementById('btn-export-csv')?.addEventListener('click', exportToCSV);

  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  document.getElementById('modal-view')?.addEventListener('click', (e) => {
    if (e.target.id === 'modal-view') closeModal();
  });
}

function applyFilters() {
  const searchVal = document.getElementById('search-input')?.value.toLowerCase().trim() || '';
  const catVal = document.getElementById('select-category')?.value || 'ALL';
  const docTypeVal = document.getElementById('select-doctype')?.value || 'ALL';
  const countryVal = document.getElementById('select-country')?.value || 'ALL';
  const langVal = document.getElementById('select-language')?.value || 'ALL';
  const sortVal = document.getElementById('select-sort')?.value || 'year-desc';
  const yearFrom = parseInt(document.getElementById('year-from')?.value, 10);
  const yearTo = parseInt(document.getElementById('year-to')?.value, 10);

  filteredData = rawData.filter((item, idx) => {
    if (showFavOnly && !favorites.has(idx)) return false;

    const cat = item.category || 'Другое';
    if (catVal !== 'ALL' && cat !== catVal) return false;

    const docType = normalizeDocType(item.type);
    if (docTypeVal !== 'ALL' && docType !== docTypeVal) return false;

    const country = normalizeCountry(item.country);
    if (countryVal !== 'ALL' && country !== countryVal) return false;

    const lang = normalizeLanguage(item.language);
    if (langVal !== 'ALL' && lang !== langVal) return false;

    const year = extractYear(item);
    if (!isNaN(yearFrom) && year < yearFrom) return false;
    if (!isNaN(yearTo) && year > yearTo) return false;

    const title = (item.title_original || item.title || '').toLowerCase();
    const summary = (item.summary_ru || item.summary || item.abstract || '').toLowerCase();
    const authors = normalizeAuthors(item).toLowerCase();

    if (searchVal && !title.includes(searchVal) && !summary.includes(searchVal) && !authors.includes(searchVal)) return false;

    return true;
  });

  // Сортировка данных
  filteredData.sort((a, b) => {
    if (sortVal === 'year-desc') return extractYear(b) - extractYear(a);
    if (sortVal === 'year-asc') return extractYear(a) - extractYear(b);
    if (sortVal === 'title-asc') {
      const tA = (a.title_original || a.title || '').toLowerCase();
      const tB = (b.title_original || b.title || '').toLowerCase();
      return tA.localeCompare(tB);
    }
    return 0;
  });

  const currCountElem = document.getElementById('current-count');
  if (currCountElem) currCountElem.innerText = filteredData.length.toLocaleString('ru-RU');

  const headerStatElem = document.getElementById('header-stat-count');
  if (headerStatElem) headerStatElem.innerText = rawData.length.toLocaleString('ru-RU');

  renderCurrentView();
  updateCharts(filteredData);
}

function renderCurrentView() {
  const container = document.getElementById('publications-feed');
  if (!container) return;

  const totalPages = Math.ceil(filteredData.length / itemsPerPage) || 1;
  if (currentPage > totalPages) currentPage = totalPages;

  const start = (currentPage - 1) * itemsPerPage;
  const end = start + itemsPerPage;
  const items = filteredData.slice(start, end);

  if (items.length === 0) {
    container.innerHTML = `<div class="pub-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;"><p style="color: #666; font-family: serif;">По вашему запросу не найдено исследований.</p></div>`;
    renderPagination(0);
    return;
  }

  container.className = 'cards-grid';
  container.innerHTML = items.map(item => renderGridCardHtml(item)).join('');
  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  const pagContainer = document.getElementById('pagination-container');
  if (!pagContainer) return;

  if (totalPages <= 1) {
    pagContainer.innerHTML = '';
    return;
  }

  let html = `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changePage(${currentPage - 1})">← Назад</button>`;
  
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
      html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="changePage(${i})">${i}</button>`;
    } else if (i === currentPage - 3 || i === currentPage + 3) {
      html += `<span style="padding: 0 4px; color: var(--text-muted);">...</span>`;
    }
  }

  html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changePage(${currentPage + 1})">Вперед →</button>`;
  pagContainer.innerHTML = html;
}

window.changePage = function(page) {
  currentPage = page;
  renderCurrentView();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderGridCardHtml(item) {
  const title = item.title_original || item.title || 'Научное исследование без названия';
  const summary = item.summary_ru || item.summary || item.abstract || 'Аннотация отсутствует.';
  const category = item.category || 'Олимпийское образование и просвещение';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const country = normalizeCountry(item.country);
  const docType = normalizeDocType(item.type);
  const originalUrl = getOriginalUrl(item);

  const realIndex = rawData.indexOf(item);
  const isFav = favorites.has(realIndex);
  const gostCitationText = generateGostCitation(item);

  return `
    <article class="pub-card">
      <div class="pub-badge-group">
        <span class="badge-cat">${escapeHtml(category)}</span>
        <button style="background:none; border:none; cursor:pointer; font-size:1.2rem; color:${isFav ? 'var(--accent-gold)' : '#ccc'};" onclick="toggleFavorite(${realIndex})" title="В избранное">★</button>
      </div>
      
      <span class="badge-type">${escapeHtml(docType)}</span>
      
      <h3 class="pub-card-title" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</h3>
      
      <div class="pub-author-row">${escapeHtml(authors)} (${year})</div>
      <div class="pub-country-row">🌐 ${escapeHtml(country)}</div>

      <div class="ai-summary-box">
        <span style="font-weight: bold; color: var(--primary-navy);">📌 Аннотация:</span> 
        <span id="summary-text-${realIndex}" class="summary-clamped">${escapeHtml(summary)}</span>
        <div style="margin-top: 4px; text-align: right;">
          <button onclick="toggleAbstract(${realIndex}, this)" style="background: none; border: none; color: var(--secondary-navy); cursor: pointer; font-size: 10px; font-weight: 600; padding: 0;">Показать полностью ▼</button>
        </div>
      </div>

      <div class="gost-citation-box">
        <div style="font-weight: bold; margin-bottom: 3px; color: var(--primary-navy);">📋 ГОСТ Р 7.0.100-2018:</div>
        <div style="margin-bottom: 5px; font-style: italic; line-height: 1.3;">${escapeHtml(gostCitationText)}</div>
        <button onclick="copyGostCitation(this, ${realIndex})">
          📋 Копировать цитату
        </button>
      </div>

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

window.toggleAbstract = function(realIndex, btn) {
  const textElem = document.getElementById(`summary-text-${realIndex}`);
  if (!textElem) return;

  if (textElem.classList.contains('summary-clamped')) {
    textElem.classList.remove('summary-clamped');
    btn.innerText = 'Свернуть ▲';
  } else {
    textElem.classList.add('summary-clamped');
    btn.innerText = 'Показать полностью ▼';
  }
};

window.toggleFavorite = function(index) {
  if (favorites.has(index)) favorites.delete(index);
  else favorites.add(index);
  const favCountElem = document.getElementById('fav-count');
  if (favCountElem) favCountElem.innerText = favorites.size;
  applyFilters();
}

window.openModalByItemIndex = function(realIndex) {
  const item = rawData[realIndex];
  if (!item) return;

  document.getElementById('modal-title').innerText = item.title_original || item.title || '';
  document.getElementById('modal-discipline').innerText = item.category || '';
  document.getElementById('modal-authors').innerText = normalizeAuthors(item);
  document.getElementById('modal-year').innerText = extractYear(item);
  document.getElementById('modal-doctype').innerText = normalizeDocType(item.type);
  document.getElementById('modal-country').innerText = normalizeCountry(item.country);
  document.getElementById('modal-abstract').innerText = item.summary_ru || item.summary || item.abstract || '';
  document.getElementById('modal-original-link').href = getOriginalUrl(item);
  document.getElementById('modal-citation').innerText = generateGostCitation(item);

  document.getElementById('modal-view').style.display = 'flex';
}

function closeModal() {
  document.getElementById('modal-view').style.display = 'none';
}

function updateCharts(dataset) {
  if (typeof Chart === 'undefined') return;

  const catCounts = {};
  STANDARD_CATEGORIES.forEach(c => catCounts[c] = 0);
  dataset.forEach(item => {
    const c = item.category || 'Другое';
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
          backgroundColor: ['#10233F', '#29496B', '#B38A4B', '#2E7D32', '#C62828', '#00838F', '#6A1B9A', '#D81B60', '#F57F17', '#4E342E', '#78909C'],
          borderWidth: 2,
          borderColor: '#FFFDF9'
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, cutout: '68%' }
    });
  }

  const yearCounts = {};
  dataset.forEach(item => {
    const y = extractYear(item);
    if (y && y >= 1896 && y <= 2026) yearCounts[y] = (yearCounts[y] || 0) + 1;
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
          tension: 0.3
        }]
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
  }
}

function exportToCSV() {
  let csvContent = "data:text/csv;charset=utf-8,Category,Title,Authors,Year,Country,URL\n";
  filteredData.forEach(item => {
    const cat = (item.category || '').replace(/"/g, '""');
    const title = (item.title_original || item.title || '').replace(/"/g, '""');
    const authors = normalizeAuthors(item).replace(/"/g, '""');
    const year = extractYear(item);
    const country = normalizeCountry(item.country).replace(/"/g, '""');
    const url = getOriginalUrl(item);
    csvContent += `"${cat}","${title}","${authors}","${year}","${country}","${url}"\n`;
  });
  
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", showFavOnly ? "olympic_favorites.csv" : "olympic_research_data.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}