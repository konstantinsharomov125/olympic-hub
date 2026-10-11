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
  setupAdminPanel();
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
    const container = document.getElementById('publications-feed') || document.getElementById('articles-feed');
    if (container) {
      container.innerHTML = `<div class="pub-card" style="grid-column:1/-1;"><p style="color:red;">❌ Ошибка: Не найден файл web_data.json</p></div>`;
    }
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

  return 2026;
}

function getOriginalUrl(item) {
  const link = item.url || item.link || item.doi || item.source_url || item.pdf_url;
  if (link && typeof link === 'string' && link.startsWith('http')) return link;
  if (link && typeof link === 'string' && link.includes('doi.org')) return link.startsWith('http') ? link : 'https://' + link;
  
  const title = item.title_original || item.title || item.article || '';
  if (title) return `https://scholar.google.com/scholar?q=${encodeURIComponent(title)}`;
  return 'https://scholar.google.com';
}

// Формирование библиографической ссылки по ГОСТ Р 7.0.100-2018
function generateGostCitation(item) {
    let authors = normalizeAuthors(item);
    let title = item.title_original || item.title || item.article || "Без названия";
    let year = extractYear(item);
    let originalUrl = getOriginalUrl(item);
    
    let sourceField = item.journal || item.publisher || item.institution || item.university || "";
    
    if (!sourceField || sourceField === "Другое") {
        const docType = normalizeDocType(item.type || item.document_type);
        if (docType === 'Диссертация' || docType === 'Выпускная квалификационная работа') {
            sourceField = "Материалы квалификационной работы";
        } else if (docType === 'Материалы конференции') {
            sourceField = "Сборник материалов научной конференции";
        } else {
            sourceField = "Электронный ресурс / Научная публикация";
        }
    }
    
    let citation = `${authors}. ${title} // ${sourceField}. – ${year}.`;
    
    if (originalUrl) {
        citation += ` – URL: ${originalUrl}`;
    }
    
    let currentDate = new Date().toLocaleDateString('ru-RU');
    citation += ` (дата обращения: ${currentDate}).`;
    
    return citation;
}

// Копирование цитаты в буфер обмена
window.copyGostCitation = function(buttonElement, realIndex) {
    const item = rawData[realIndex];
    if (!item) return;
    
    const citation = generateGostCitation(item);
    navigator.clipboard.writeText(citation).then(() => {
        let originalText = buttonElement.innerText;
        buttonElement.innerText = "✅ Скопировано!";
        buttonElement.style.background = "#d4edda";
        setTimeout(() => {
            buttonElement.innerText = originalText;
            buttonElement.style.background = "";
        }, 2000);
    }).catch(err => {
        console.error("Ошибка копирования: ", err);
        alert("Не удалось скопировать в буфер обмена.");
    });
};

// Заполнение выпадающих списков
function populateDropdownFilters() {
  const selectCat = document.getElementById('select-category');
  const selectDocType = document.getElementById('select-doctype');
  const selectCountry = document.getElementById('select-country');
  const selectLang = document.getElementById('select-language');

  if (selectCat) {
    selectCat.innerHTML = `<option value="ALL">Все направления</option>`;
    STANDARD_CATEGORIES.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      selectCat.appendChild(opt);
    });
  }

  if (selectDocType) {
    selectDocType.innerHTML = `<option value="ALL">Все типы документов</option>`;
    const docTypes = ['Научная статья', 'Обзорная статья', 'Монография', 'Диссертация', 'Учебное пособие', 'Материалы конференции'];
    docTypes.forEach(type => {
      const opt = document.createElement('option');
      opt.value = type;
      opt.textContent = type;
      selectDocType.appendChild(opt);
    });
  }

  if (selectCountry) {
    selectCountry.innerHTML = `<option value="ALL">Все страны</option>`;
    const countries = ['Россия', 'США', 'Китай', 'Германия', 'Франция', 'Великобритания', 'Япония', 'Другие страны'];
    countries.forEach(country => {
      const opt = document.createElement('option');
      opt.value = country;
      opt.textContent = country;
      selectCountry.appendChild(opt);
    });
  }

  if (selectLang) {
    selectLang.innerHTML = `<option value="ALL">Все языки</option>`;
    const languages = ['Русский', 'Английский', 'Немецкий', 'Французский', 'Испанский', 'Другой язык'];
    languages.forEach(lang => {
      const opt = document.createElement('option');
      opt.value = lang;
      opt.textContent = lang;
      selectLang.appendChild(opt);
    });
  }
}

function setupEventListeners() {
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.addEventListener('input', applyFilters);

  const selectCat = document.getElementById('select-category');
  if (selectCat) selectCat.addEventListener('change', applyFilters);

  const selectDocType = document.getElementById('select-doctype');
  if (selectDocType) selectDocType.addEventListener('change', applyFilters);

  const selectCountry = document.getElementById('select-country');
  if (selectCountry) selectCountry.addEventListener('change', applyFilters);

  const selectLang = document.getElementById('select-language');
  if (selectLang) selectLang.addEventListener('change', applyFilters);

  const yearFrom = document.getElementById('year-from');
  if (yearFrom) yearFrom.addEventListener('input', applyFilters);

  const yearTo = document.getElementById('year-to');
  if (yearTo) yearTo.addEventListener('input', applyFilters);

  const btnReset = document.getElementById('btn-reset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      if (document.getElementById('search-input')) document.getElementById('search-input').value = '';
      if (document.getElementById('select-category')) document.getElementById('select-category').value = 'ALL';
      if (document.getElementById('select-doctype')) document.getElementById('select-doctype').value = 'ALL';
      if (document.getElementById('select-country')) document.getElementById('select-country').value = 'ALL';
      if (document.getElementById('select-language')) document.getElementById('select-language').value = 'ALL';
      if (document.getElementById('year-from')) document.getElementById('year-from').value = '';
      if (document.getElementById('year-to')) document.getElementById('year-to').value = '';
      showFavOnly = false;
      const favBtn = document.getElementById('btn-fav-filter');
      if (favBtn) {
        favBtn.style.backgroundColor = 'var(--bg-main)';
        favBtn.style.color = 'var(--primary-navy)';
      }
      applyFilters();
    });
  }

  const btnFavFilter = document.getElementById('btn-fav-filter');
  if (btnFavFilter) {
    btnFavFilter.addEventListener('click', () => {
      showFavOnly = !showFavOnly;
      btnFavFilter.style.backgroundColor = showFavOnly ? 'var(--accent-gold)' : 'var(--bg-main)';
      btnFavFilter.style.color = showFavOnly ? '#FFFDF9' : 'var(--primary-navy)';
      applyFilters();
    });
  }

  const exportCsvBtn = document.getElementById('btn-export-csv');
  if (exportCsvBtn) exportCsvBtn.addEventListener('click', exportToCSV);

  const modalClose = document.getElementById('modal-close');
  if (modalClose) modalClose.addEventListener('click', closeModal);

  const modalView = document.getElementById('modal-view');
  if (modalView) {
    modalView.addEventListener('click', (e) => {
      if (e.target.id === 'modal-view') closeModal();
    });
  }
}

window.changeViewMode = function(mode) {
  currentViewMode = mode;
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`btn-view-${mode}`)?.classList.add('active');
  renderCurrentView();
}

function applyFilters() {
  const searchVal = document.getElementById('search-input') ? document.getElementById('search-input').value.toLowerCase().trim() : '';
  const catVal = document.getElementById('select-category') ? document.getElementById('select-category').value : 'ALL';
  const docTypeVal = document.getElementById('select-doctype') ? document.getElementById('select-doctype').value : 'ALL';
  const countryVal = document.getElementById('select-country') ? document.getElementById('select-country').value : 'ALL';
  const langVal = document.getElementById('select-language') ? document.getElementById('select-language').value : 'ALL';
  const yearFrom = parseInt(document.getElementById('year-from')?.value, 10);
  const yearTo = parseInt(document.getElementById('year-to')?.value, 10);

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
    const summary = (item.summary_ru || item.summary || item.abstract || item.description || '').toLowerCase();
    const authors = normalizeAuthors(item).toLowerCase();

    if (searchVal && !title.includes(searchVal) && !summary.includes(searchVal) && !authors.includes(searchVal)) return false;

    return true;
  });

  const currCountElem = document.getElementById('current-count');
  if (currCountElem) currCountElem.innerText = filteredData.length.toLocaleString('ru-RU');

  const headerStatElem = document.getElementById('header-stat-count') || document.querySelector('#db-counter span');
  if (headerStatElem) headerStatElem.innerText = rawData.length.toLocaleString('ru-RU');

  const metricTotal = document.getElementById('metric-total-val');
  if (metricTotal) metricTotal.innerText = rawData.length.toLocaleString('ru-RU');

  renderCurrentView();
  updateCharts(filteredData);
}

function renderCurrentView() {
  const container = document.getElementById('publications-feed') || document.getElementById('articles-feed');
  if (!container) return;

  const items = filteredData.slice(0, 60);

  if (items.length === 0) {
    container.className = 'cards-grid';
    container.innerHTML = `
      <div class="pub-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
        <p style="color: var(--text-muted); font-family: var(--font-serif);">По вашему запросу не найдено исследований.</p>
      </div>`;
    return;
  }

  if (currentViewMode === 'grid' || currentViewMode === 'list') {
    container.className = currentViewMode === 'grid' ? 'cards-grid' : 'cards-list';
    container.innerHTML = items.map(item => renderGridCardHtml(item)).join('');
  } else if (currentViewMode === 'table') {
    container.className = 'table-view-container';
    container.innerHTML = `
      <table class="academic-table" style="width: 100%; border-collapse: collapse; background: #fff; font-size: 12px;">
        <thead>
          <tr style="background: #10233F; color: #fff; text-align: left;">
            <th style="padding: 10px;">Заглавие исследования</th>
            <th style="padding: 10px;">Авторы</th>
            <th style="padding: 10px;">Год</th>
            <th style="padding: 10px;">Направление</th>
            <th style="padding: 10px;">Тип</th>
            <th style="padding: 10px;">Страна</th>
            <th style="padding: 10px;">Ссылка</th>
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
  const summary = item.summary_ru || item.summary || item.abstract || item.description || 'Аннотация к работе отсутствует в базе.';
  const category = item.category || item.discipline || 'Другое';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const country = normalizeCountry(item.country || item.country_name);
  const docType = normalizeDocType(item.type || item.document_type);
  const originalUrl = getOriginalUrl(item);

  const realIndex = rawData.indexOf(item);
  const isFav = favorites.has(realIndex);
  const gostCitationText = generateGostCitation(item);

  return `
    <article class="pub-card" style="background: #FFFDF9; border: 1px solid #E4DED2; border-radius: 6px; padding: 18px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
      <div class="pub-badge-group" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span class="badge-cat" style="font-size: 10px; background: #10233F; color: #FFFDF9; padding: 3px 8px; border-radius: 3px; font-weight: 600; text-transform: uppercase;">${escapeHtml(category)}</span>
        <button style="background:none; border:none; cursor:pointer; font-size:1.2rem; color:${isFav ? 'var(--accent-gold)' : '#ccc'};" onclick="toggleFavorite(${realIndex})" title="В избранное">
          ★
        </button>
      </div>
      
      <span class="badge-type" style="font-size: 11px; color: #697586; display: block; margin-bottom: 6px;">${escapeHtml(docType)}</span>
      
      <h3 class="pub-card-title" style="font-size: 15px; font-family: var(--font-serif); color: #10233F; margin-bottom: 8px; cursor: pointer;" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</h3>
      
      <div class="pub-author-row" style="font-size: 12px; color: #333; margin-bottom: 4px;">${escapeHtml(authors)} (${year})</div>
      <div class="pub-country-row" style="font-size: 12px; color: #697586; margin-bottom: 8px;">🌐 ${escapeHtml(country)}</div>

      <div class="ai-summary-box" style="margin-top: 8px; margin-bottom: 8px; padding: 8px 10px; background: #f0f4f8; border-left: 3px solid #10233F; border-radius: 4px; font-size: 11px; color: #1a202c;">
        <span style="font-weight: bold; color: #10233F;">📌 Аннотация:</span> ${escapeHtml(summary)}
      </div>

      <div class="gost-citation-box" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 6px; border: 1px solid #e9ecef; font-size: 11px; color: #333;">
        <div style="font-weight: bold; margin-bottom: 3px; color: #555;">📋 ГОСТ Р 7.0.100-2018:</div>
        <div style="margin-bottom: 6px; font-style: italic; line-height: 1.3;" id="gost-${realIndex}">${escapeHtml(gostCitationText)}</div>
        <button onclick="copyGostCitation(this, ${realIndex})" style="background: #007bff; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 500;">
          📋 Копировать цитату
        </button>
      </div>

      <div class="pub-card-footer" style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
        <button class="btn-card-action" onclick="openModalByItemIndex(${realIndex})" style="background: #10233F; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">
          Читать аннотацию
        </button>
        <a href="${originalUrl}" target="_blank" class="btn-link-original" style="font-size: 11px; color: #10233F; text-decoration: none; font-weight: 600;">
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
    <tr style="border-bottom: 1px solid #E4DED2;">
      <td style="padding: 8px;"><strong style="cursor:pointer; color:#10233F;" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</strong></td>
      <td style="padding: 8px;">${escapeHtml(authors)}</td>
      <td style="padding: 8px;">${year}</td>
      <td style="padding: 8px;"><span style="font-size:10px; background:#10233F; color:#fff; padding:2px 6px; border-radius:3px;">${escapeHtml(category)}</span></td>
      <td style="padding: 8px;">${docType}</td>
      <td style="padding: 8px;">${escapeHtml(country)}</td>
      <td style="padding: 8px;"><a href="${originalUrl}" target="_blank" style="color:#007bff; text-decoration:none;">Открыть ↗</a></td>
    </tr>
  `;
}

window.toggleFavorite = function(index) {
  if (favorites.has(index)) {
    favorites.delete(index);
  } else {
    favorites.add(index);
  }
  const favCountElem = document.getElementById('fav-count');
  if (favCountElem) favCountElem.innerText = favorites.size;
  applyFilters();
}

window.openModalByItemIndex = function(realIndex) {
  const item = rawData[realIndex];
  if (!item) return;

  const title = item.title_original || item.title || item.article || 'Без названия';
  const summary = item.summary_ru || item.summary || item.abstract || item.description || 'Аннотация отсутствует.';
  const category = item.category || item.discipline || 'Другое';
  const authors = normalizeAuthors(item);
  const year = extractYear(item);
  const docType = normalizeDocType(item.type || item.document_type);
  const country = normalizeCountry(item.country || item.country_name);
  const originalUrl = getOriginalUrl(item);

  if (document.getElementById('modal-title')) document.getElementById('modal-title').innerText = title;
  if (document.getElementById('modal-discipline')) document.getElementById('modal-discipline').innerText = category;
  if (document.getElementById('modal-authors')) document.getElementById('modal-authors').innerText = authors;
  if (document.getElementById('modal-year')) document.getElementById('modal-year').innerText = year;
  if (document.getElementById('modal-doctype')) document.getElementById('modal-doctype').innerText = docType;
  if (document.getElementById('modal-country')) document.getElementById('modal-country').innerText = country;
  if (document.getElementById('modal-abstract')) document.getElementById('modal-abstract').innerText = summary;
  
  const linkElem = document.getElementById('modal-original-link');
  if (linkElem) linkElem.href = originalUrl;

  const citationElem = document.getElementById('modal-citation');
  if (citationElem) citationElem.innerText = generateGostCitation(item);

  const modalView = document.getElementById('modal-view');
  if (modalView) modalView.classList.add('active');
}

function closeModal() {
  const modalView = document.getElementById('modal-view');
  if (modalView) modalView.classList.remove('active');
}

function updateCharts(dataset) {
  if (typeof Chart === 'undefined') return;

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

// ВСТРОЕННАЯ ПАНЕЛЬ АДМИНИСТРАТОРА
function setupAdminPanel() {
  const adminModal = document.getElementById('admin-modal');
  const btnOpen = document.getElementById('btn-admin-open');
  const btnCloseAuth = document.getElementById('admin-close-auth');
  const btnClosePanel = document.getElementById('admin-panel-close');
  const loginBtn = document.getElementById('admin-login-btn');
  const passwordInput = document.getElementById('admin-password-input');
  
  const authSection = document.getElementById('admin-auth-section');
  const panelSection = document.getElementById('admin-panel-section');
  const addForm = document.getElementById('add-article-form');
  const downloadBtn = document.getElementById('admin-download-json');

  const ADMIN_PASS = "olympic2026";

  if (btnOpen) {
    btnOpen.addEventListener('click', () => {
      adminModal.style.display = 'flex';
      authSection.style.display = 'block';
      panelSection.style.display = 'none';
      passwordInput.value = '';
    });
  }

  const closeAdmin = () => {
    if (adminModal) adminModal.style.display = 'none';
  };

  if (btnCloseAuth) btnCloseAuth.addEventListener('click', closeAdmin);
  if (btnClosePanel) btnClosePanel.addEventListener('click', closeAdmin);

  if (loginBtn) {
    loginBtn.addEventListener('click', () => {
      if (passwordInput.value === ADMIN_PASS) {
        authSection.style.display = 'none';
        panelSection.style.display = 'block';
      } else {
        alert("❌ Неверный пароль администратора!");
      }
    });
  }

  if (addForm) {
    addForm.addEventListener('submit', (e) => {
      e.preventDefault();

      const newItem = {
        title: document.getElementById('new-title').value.trim(),
        title_original: document.getElementById('new-title').value.trim(),
        authors: document.getElementById('new-authors').value.trim(),
        year: parseInt(document.getElementById('new-year').value, 10) || 2026,
        category: document.getElementById('new-category').value,
        country: document.getElementById('new-country').value.trim(),
        url: document.getElementById('new-url').value.trim() || "https://scholar.google.com",
        summary_ru: document.getElementById('new-abstract').value.trim() || "Аннотация добавлена вручную через панель администратора.",
        ai_processed: true,
        type: "Научная статья"
      };

      rawData.unshift(newItem);
      applyFilters();

      alert("✅ Исследование успешно добавлено в базу данных!");
      addForm.reset();
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener('click', () => {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(rawData, null, 2));
      const downloadAnchor = document.createElement('a');
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", "web_data.json");
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}