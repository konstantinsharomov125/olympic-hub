/* Олимпийский исследовательский портал — логика интерфейса.
   Данные: контракт {metadata, data}, публичный каталог содержит только accepted. */

let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

let currentPage = 1;
const itemsPerPage = 60;
let currentViewMode = 'grid';

let donutChartInstance = null;
let lineChartInstance = null;
let barChartInstance = null;

const FAVORITES_STORAGE_KEY = 'olympic_hub_favorites_v2';
const VIEW_STORAGE_KEY = 'olympic_hub_view_mode';

const CATEGORIES = [
  'Олимпийское образование и просвещение',
  'Пропаганда, философия и культурология',
  'История и наследие олимпизма',
  'Этика, честная игра и антидопинг',
  'Политика, геополитика и глобальные вызовы',
  'Психология олимпийского спорта',
  'Менеджмент, маркетинг и экономика Игр',
  'Спортивная медицина, физиология и биомеханика',
  'Подготовка олимпийского резерва и тренировка',
  'Теория и методология олимпийского движения',
  'Без категории'
];

const DOC_TYPES = [
  'Научная статья', 'Обзорная статья', 'Монография',
  'Диссертация', 'Учебное пособие', 'Материалы конференции'
];

const COUNTRIES = ['Россия', 'США', 'Китай', 'Германия', 'Франция', 'Великобритания', 'Япония', 'Другие страны'];
const LANGUAGES = ['Русский', 'Английский', 'Немецкий', 'Французский', 'Испанский', 'Другой язык'];

/* ---------- Избранное: устойчивые идентификаторы и защита от сбоев ---------- */

function recordKey(item) {
  if (item && item.study_id) return String(item.study_id);
  if (item && item.doi) return 'doi:' + String(item.doi).toLowerCase();
  const title = (item && (item.title_original || item.title)) || '';
  return 'title:' + title.slice(0, 120);
}

function loadFavorites() {
  try {
    const stored = localStorage.getItem(FAVORITES_STORAGE_KEY);
    if (!stored) return new Set();
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((value) => typeof value === 'string'));
  } catch (error) {
    // Повреждённые данные не должны ломать интерфейс.
    console.warn('Не удалось прочитать избранное, список сброшен.');
    try { localStorage.removeItem(FAVORITES_STORAGE_KEY); } catch (e) { /* игнорируем */ }
    return new Set();
  }
}

function saveFavorites() {
  try {
    localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify([...favorites]));
  } catch (error) {
    console.warn('Не удалось сохранить избранное.');
  }
}

/* ---------- Вспомогательные функции ---------- */

function safeUrl(value) {
  if (typeof value !== 'string') return '';
  const trimmed = value.trim();
  if (!/^https?:\/\//i.test(trimmed)) return '';
  try {
    const parsed = new URL(trimmed);
    return (parsed.protocol === 'http:' || parsed.protocol === 'https:') ? parsed.href : '';
  } catch (error) {
    return '';
  }
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function normalizeDocType(raw) {
  const value = String(raw || '').toLowerCase();
  if (!value) return '';
  if (value.includes('диссертац') || value.includes('dissertation') || value.includes('thesis')) return 'Диссертация';
  if (value.includes('обзор') || value.includes('review')) return 'Обзорная статья';
  if (value.includes('учебн') || value.includes('textbook') || value.includes('manual')) return 'Учебное пособие';
  if (value.includes('монограф') || value.includes('monograph') || value.includes('book')) return 'Монография';
  if (value.includes('конференц') || value.includes('conference') || value.includes('proceedings')) return 'Материалы конференции';
  if (value.includes('стать') || value.includes('article') || value.includes('journal')) return 'Научная статья';
  return '';
}

function normalizeLanguage(raw) {
  const value = String(raw || '').toLowerCase();
  if (!value) return '';
  if (value.includes('русс') || value.includes('russian') || value === 'ru') return 'Русский';
  if (value.includes('англ') || value.includes('english') || value === 'en') return 'Английский';
  if (value.includes('нем') || value.includes('german') || value === 'de') return 'Немецкий';
  if (value.includes('франц') || value.includes('french') || value === 'fr') return 'Французский';
  if (value.includes('испан') || value.includes('spanish') || value === 'es') return 'Испанский';
  return 'Другой язык';
}

function normalizeCountry(raw) {
  const value = String(raw || '').trim().toLowerCase();
  if (!value || value === 'nr' || value === 'n/a' || value === 'null') return '';
  if (value.includes('росси') || value.includes('russia')) return 'Россия';
  if (value.includes('сша') || value.includes('usa') || value.includes('united states')) return 'США';
  if (value.includes('китай') || value.includes('china')) return 'Китай';
  if (value.includes('герман') || value.includes('germany')) return 'Германия';
  if (value.includes('франц') || value.includes('france')) return 'Франция';
  if (value.includes('великобрит') || value.includes('united kingdom') || value.includes('england')) return 'Великобритания';
  if (value.includes('япони') || value.includes('japan')) return 'Япония';
  return 'Другие страны';
}

function recordYear(item) {
  const parsed = parseInt(String((item && item.year) || ''), 10);
  if (Number.isFinite(parsed) && parsed >= 1896 && parsed <= new Date().getFullYear()) {
    return parsed;
  }
  return null;
}

function authorList(item) {
  const raw = (item && (item.authors || item.author)) || '';
  return String(raw)
    .split(/[;,]/)
    .map((part) => part.trim().replace(/\.$/, ''))
    .filter((part) => part && !['nr', 'n/a', 'нет'].includes(part.toLowerCase()));
}

function splitName(entry) {
  const text = String(entry || '').trim();
  if (!text) return { surname: '', initials: [] };

  let match = text.match(/^(.+?)\s+((?:[А-ЯЁA-Z]\.\s*){1,3})$/);
  if (match) {
    return {
      surname: match[1].trim(),
      initials: (match[2].match(/[А-ЯЁA-Z]/g) || [])
    };
  }

  match = text.match(/^((?:[А-ЯЁA-Z]\.\s*){1,3})\s*(.+)$/);
  if (match) {
    return {
      surname: match[2].trim(),
      initials: (match[1].match(/[А-ЯЁA-Z]/g) || [])
    };
  }

  const parts = text.split(/\s+/);
  if (parts.length >= 2 && parts.slice(1).every((p) => /^[А-ЯЁA-Z]\.?$/.test(p))) {
    return { surname: parts[0], initials: parts.slice(1).map((p) => p[0]) };
  }
  return { surname: text, initials: [] };
}

function firstAuthorText(entry) {
  const { surname, initials } = splitName(entry);
  if (!surname) return '';
  return (surname + (initials.length ? ' ' + initials.map((i) => i + '.').join('') : '')).replace(/\.$/, '');
}

function otherAuthorText(entry) {
  const { surname, initials } = splitName(entry);
  if (!surname) return '';
  return (initials.length ? initials.map((i) => i + '.').join(' ') + ' ' : '') + surname;
}

function accessDate() {
  const now = new Date();
  const day = String(now.getDate()).padStart(2, '0');
  const month = String(now.getMonth() + 1).padStart(2, '0');
  return `${day}.${month}.${now.getFullYear()}`;
}

function forbiddenContainer(value) {
  const normalized = String(value || '').toLowerCase().trim().replace(/\.$/, '');
  return [
    'научная публикация', 'научная статья', 'научное исследование',
    'unknown journal', 'unknown', 'n/a', 'na', 'none', 'null', '-', '—', 'неизвестно'
  ].includes(normalized);
}

function buildCitation(item) {
  const title = String((item && (item.title_original || item.title)) || '').trim();
  const containerRaw = String((item && (item.container || item.source)) || '').trim();
  const container = forbiddenContainer(containerRaw) ? '' : containerRaw;
  const authors = authorList(item);
  const year = recordYear(item);

  let url = safeUrl(item && item.url);
  if (!url && item && item.doi) {
    const doi = String(item.doi).replace(/^https?:\/\/(dx\.)?doi\.org\//i, '').trim();
    if (doi && !forbiddenContainer(doi)) url = 'https://doi.org/' + doi;
  }

  const parts = [];

  if (authors.length) {
    const first = firstAuthorText(authors[0]);
    const rest = authors.slice(1).map(otherAuthorText).filter(Boolean);
    if (first) {
      let head = title ? `${first}. ${title}` : `${first}.`;
      if (rest.length) head += ' / ' + rest.join(', ');
      parts.push(head);
    } else if (title) {
      parts.push(title);
    }
  } else if (title) {
    parts.push(title);
  }

  if (container) parts.push('// ' + container);
  if (year) parts.push(String(year));
  if (url) parts.push(`URL: ${url} (дата обращения: ${accessDate()})`);

  if (!parts.length) return 'Недостаточно данных для формирования ссылки';

  let result = parts[0];
  for (let i = 1; i < parts.length; i += 1) {
    result += parts[i].startsWith('//') ? ' ' + parts[i] : '. – ' + parts[i];
  }
  return result;
}

/* ---------- Загрузка и инициализация ---------- */

async function loadDataset() {
  // public/web_data.json — единственный корректный публичный каталог.
  // Легаси-массивы (generated/web_data.json, корневой web_data.json) содержат
  // записи без тематической проверки и здесь намеренно не читаются.
  const candidates = ['public/web_data.json'];

  for (const path of candidates) {
    try {
      const response = await fetch(path, { cache: 'no-cache' });
      if (!response.ok) continue;
      const payload = await response.json();

      let records = [];
      if (Array.isArray(payload)) {
        records = payload;
      } else if (payload && Array.isArray(payload.data)) {
        records = payload.data;
      } else {
        continue;
      }

      // Публичный каталог: только подтверждённые записи.
      // Запись без relevance_evidence не могла пройти тематическую проверку —
      // это признак устаревшего файла, а не каталога.
      rawData = records.filter((item) => {
        if (!item) return false;
        const status = item.relevance_status;
        if (status && status !== 'accepted') return false;
        const evidence = item.relevance_evidence;
        return Array.isArray(evidence) ? evidence.length > 0 : Boolean(evidence);
      });

      if (records.length && !rawData.length) {
        console.warn(
          `Каталог ${path} не содержит обоснований включения (relevance_evidence). ` +
          'Похоже, это устаревший файл. Используйте public/web_data.json.'
        );
        continue;
      }

      filteredData = rawData.slice();
      return true;
    } catch (error) {
      console.warn('Не удалось загрузить', path);
    }
  }
  return false;
}

function showLoadError() {
  const container = document.getElementById('publications-feed');
  if (!container) return;
  container.className = 'cards-grid';
  container.innerHTML = `
    <div class="state-box" role="alert">
      <h3>Не удалось загрузить каталог</h3>
      <p>Проверьте подключение к интернету и обновите страницу.</p>
    </div>`;
}

function showEmptyState(message) {
  const container = document.getElementById('publications-feed');
  if (!container) return;
  container.innerHTML = `
    <div class="state-box">
      <h3>Ничего не найдено</h3>
      <p>${escapeHtml(message)}</p>
    </div>`;
}

document.addEventListener('DOMContentLoaded', async () => {
  favorites = loadFavorites();

  try {
    const storedView = localStorage.getItem(VIEW_STORAGE_KEY);
    if (storedView === 'list' || storedView === 'grid') currentViewMode = storedView;
  } catch (error) { /* игнорируем */ }

  const loaded = await loadDataset();
  if (!loaded) {
    showLoadError();
    const counter = document.getElementById('current-count');
    if (counter) counter.textContent = '0';
    return;
  }

  populateDropdownFilters();
  setupEventListeners();
  applyFilters();
});

/* ---------- Заполнение фильтров ---------- */

function fillSelect(id, placeholder, values) {
  const select = document.getElementById(id);
  if (!select) return;
  select.innerHTML = '';
  const base = document.createElement('option');
  base.value = 'ALL';
  base.textContent = placeholder;
  select.appendChild(base);
  values.forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function populateDropdownFilters() {
  fillSelect('select-category', 'Все направления', CATEGORIES);
  fillSelect('select-doctype', 'Все типы документов', DOC_TYPES);
  fillSelect('select-country', 'Все страны', COUNTRIES);
  fillSelect('select-language', 'Все языки', LANGUAGES);
}

/* ---------- Обработчики ---------- */

function debounce(fn, delay) {
  let timer = null;
  return function debounced(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function setViewMode(mode) {
  currentViewMode = mode;
  const gridBtn = document.getElementById('btn-view-grid');
  const listBtn = document.getElementById('btn-view-list');
  if (gridBtn && listBtn) {
    gridBtn.classList.toggle('active', mode === 'grid');
    listBtn.classList.toggle('active', mode === 'list');
    gridBtn.setAttribute('aria-pressed', mode === 'grid' ? 'true' : 'false');
    listBtn.setAttribute('aria-pressed', mode === 'list' ? 'true' : 'false');
  }
  try { localStorage.setItem(VIEW_STORAGE_KEY, mode); } catch (error) { /* игнорируем */ }
  renderCurrentView();
}

function setupEventListeners() {
  const onFilterChange = () => { currentPage = 1; applyFilters(); };

  document.getElementById('search-input')
    ?.addEventListener('input', debounce(onFilterChange, 200));

  ['select-category', 'select-doctype', 'select-country', 'select-language',
   'select-sort', 'year-from', 'year-to'].forEach((id) => {
    document.getElementById(id)?.addEventListener('change', onFilterChange);
  });

  document.getElementById('year-from')?.addEventListener('input', debounce(onFilterChange, 250));
  document.getElementById('year-to')?.addEventListener('input', debounce(onFilterChange, 250));

  document.getElementById('btn-view-grid')?.addEventListener('click', () => setViewMode('grid'));
  document.getElementById('btn-view-list')?.addEventListener('click', () => setViewMode('list'));

  document.getElementById('btn-reset')?.addEventListener('click', () => {
    const search = document.getElementById('search-input');
    if (search) search.value = '';
    ['select-category', 'select-doctype', 'select-country', 'select-language'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = 'ALL';
    });
    const sort = document.getElementById('select-sort');
    if (sort) sort.value = 'year-desc';
    ['year-from', 'year-to'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    showFavOnly = false;
    updateFavButtonState();
    currentPage = 1;
    applyFilters();
  });

  document.getElementById('btn-fav-filter')?.addEventListener('click', () => {
    showFavOnly = !showFavOnly;
    updateFavButtonState();
    currentPage = 1;
    applyFilters();
  });

  document.getElementById('btn-export-csv')?.addEventListener('click', exportToCSV);

  const modal = document.getElementById('modal-view');
  document.getElementById('modal-close')?.addEventListener('click', closeModal);
  modal?.addEventListener('click', (event) => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal && modal.classList.contains('is-open')) {
      closeModal();
    }
  });
}

function updateFavButtonState() {
  const button = document.getElementById('btn-fav-filter');
  if (!button) return;
  button.classList.toggle('is-active', showFavOnly);
  button.setAttribute('aria-pressed', showFavOnly ? 'true' : 'false');
  const counter = document.getElementById('fav-count');
  if (counter) counter.textContent = String(favorites.size);
}

/* ---------- Фильтрация и сортировка ---------- */

function applyFilters() {
  const searchValue = (document.getElementById('search-input')?.value || '').toLowerCase().trim();
  const categoryValue = document.getElementById('select-category')?.value || 'ALL';
  const docTypeValue = document.getElementById('select-doctype')?.value || 'ALL';
  const countryValue = document.getElementById('select-country')?.value || 'ALL';
  const languageValue = document.getElementById('select-language')?.value || 'ALL';
  const sortValue = document.getElementById('select-sort')?.value || 'year-desc';
  const yearFrom = parseInt(document.getElementById('year-from')?.value || '', 10);
  const yearTo = parseInt(document.getElementById('year-to')?.value || '', 10);

  filteredData = rawData.filter((item) => {
    if (showFavOnly && !favorites.has(recordKey(item))) return false;

    if (categoryValue !== 'ALL' && (item.category || 'Без категории') !== categoryValue) return false;

    if (docTypeValue !== 'ALL') {
      const docType = normalizeDocType(item.document_type || item.type);
      if (docType !== docTypeValue) return false;
    }

    if (countryValue !== 'ALL' && normalizeCountry(item.country) !== countryValue) return false;
    if (languageValue !== 'ALL' && normalizeLanguage(item.language) !== languageValue) return false;

    const year = recordYear(item);
    if (!Number.isNaN(yearFrom) && (year === null || year < yearFrom)) return false;
    if (!Number.isNaN(yearTo) && (year === null || year > yearTo)) return false;

    if (searchValue) {
      const haystack = [
        item.title_original, item.title, item.authors,
        item.abstract_ru, item.abstract_original, item.abstract_display
      ].join(' ').toLowerCase();
      if (!haystack.includes(searchValue)) return false;
    }

    return true;
  });

  filteredData.sort((a, b) => {
    if (sortValue === 'year-desc' || sortValue === 'year-asc') {
      const yearA = recordYear(a);
      const yearB = recordYear(b);
      if (yearA === null && yearB === null) return 0;
      if (yearA === null) return 1;   // без года — всегда в конце
      if (yearB === null) return -1;
      return sortValue === 'year-desc' ? yearB - yearA : yearA - yearB;
    }
    if (sortValue === 'title-asc') {
      const titleA = String(a.title_original || a.title || '').toLowerCase();
      const titleB = String(b.title_original || b.title || '').toLowerCase();
      return titleA.localeCompare(titleB, 'ru');
    }
    return 0;
  });

  const currentCount = document.getElementById('current-count');
  if (currentCount) currentCount.textContent = filteredData.length.toLocaleString('ru-RU');

  const headerCount = document.getElementById('header-stat-count');
  if (headerCount) headerCount.textContent = rawData.length.toLocaleString('ru-RU');

  updateFavButtonState();
  renderCurrentView();
  updateCharts(filteredData);
}

/* ---------- Отрисовка ---------- */

function renderCurrentView() {
  const container = document.getElementById('publications-feed');
  if (!container) return;

  const totalPages = Math.max(1, Math.ceil(filteredData.length / itemsPerPage));
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;

  const start = (currentPage - 1) * itemsPerPage;
  const pageItems = filteredData.slice(start, start + itemsPerPage);

  if (!pageItems.length) {
    showEmptyState(
      showFavOnly
        ? 'В избранном пока нет публикаций. Отметьте их звёздочкой.'
        : 'Попробуйте изменить запрос или сбросить фильтры.'
    );
    renderPagination(0);
    return;
  }

  container.className = currentViewMode === 'list' ? 'cards-list' : 'cards-grid';
  container.innerHTML = pageItems.map(renderCard).join('');
  renderPagination(totalPages);
}

function renderCard(item) {
  const key = recordKey(item);
  const isFavorite = favorites.has(key);

  const title = item.title_original || item.title || 'Без названия';
  const authors = item.authors || 'Автор не указан';
  const year = recordYear(item);
  const category = item.category || 'Без категории';
  const docType = normalizeDocType(item.document_type || item.type);
  const country = normalizeCountry(item.country);

  const abstractText = item.abstract_display
    || item.abstract_ru
    || item.abstract_original
    || 'Аннотация не найдена в источнике';

  const url = safeUrl(item.url);
  const citation = buildCitation(item);
  const safeKey = escapeHtml(key);
  const evidence = evidenceSummary(item);

  return `
    <article class="pub-card">
      <div class="pub-badge-group">
        <span class="badge-cat">${escapeHtml(category)}</span>
        <button type="button"
                class="btn-fav-star${isFavorite ? ' is-favorite' : ''}"
                data-key="${safeKey}"
                aria-pressed="${isFavorite ? 'true' : 'false'}"
                aria-label="${isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}"
                title="${isFavorite ? 'Убрать из избранного' : 'В избранное'}">★</button>
      </div>

      ${docType ? `<span class="badge-type">${escapeHtml(docType)}</span>` : ''}

      <h3 class="pub-card-title">
        <button type="button" class="link-like" data-open="${safeKey}">${escapeHtml(title)}</button>
      </h3>

      <div class="pub-author-row">${escapeHtml(authors)}${year ? ` (${year})` : ''}</div>
      ${country ? `<div class="pub-country-row">🌐 ${escapeHtml(country)}</div>` : ''}

      <div class="ai-summary-box">
        <div class="summary-label">📌 Аннотация:</div>
        <div class="summary-clamped">${escapeHtml(abstractText)}</div>
      </div>

      ${evidence ? `<div class="relevance-evidence-line visually-hidden" title="Почему публикация включена в каталог">✓ ${escapeHtml(evidence)}</div>` : ''}

      <div class="gost-citation-box">
        <div class="citation-label">📋 Библиографическая ссылка:</div>
        <div class="citation-text">${escapeHtml(citation)}</div>
        <button type="button" class="btn-copy" data-copy="${safeKey}">Копировать ссылку</button>
      </div>

      <div class="pub-card-footer">
        <button type="button" class="btn-card-action" data-open="${safeKey}">Подробнее</button>
        ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="btn-link-original">Оригинал ↗</a>` : ''}
      </div>
    </article>`;
}

/* Объяснение включения записи: краткая строка для карточки. */
function evidenceSummary(item) {
  const evidence = Array.isArray(item.relevance_evidence) ? item.relevance_evidence : [];
  if (!evidence.length) return '';
  const first = String(evidence[0] || '').replace(/\s+/g, ' ').trim();
  return first.length > 150 ? first.slice(0, 147) + '…' : first;
}

function renderPagination(totalPages) {
  const container = document.getElementById('pagination-container');
  if (!container) return;

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  const parts = [];
  parts.push(`<button type="button" class="page-btn" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>← Назад</button>`);

  for (let page = 1; page <= totalPages; page += 1) {
    if (page === 1 || page === totalPages || Math.abs(page - currentPage) <= 2) {
      const active = page === currentPage;
      parts.push(`<button type="button" class="page-btn${active ? ' active' : ''}" data-page="${page}" ${active ? 'aria-current="page"' : ''}>${page}</button>`);
    } else if (Math.abs(page - currentPage) === 3) {
      parts.push('<span class="page-gap">…</span>');
    }
  }

  parts.push(`<button type="button" class="page-btn" data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''}>Вперёд →</button>`);
  container.innerHTML = parts.join('');
}

/* ---------- Делегирование событий ---------- */

function findByKey(key) {
  return rawData.find((item) => recordKey(item) === key) || null;
}

document.addEventListener('click', (event) => {
  const star = event.target.closest('.btn-fav-star');
  if (star) {
    const key = star.dataset.key;
    if (!key) return;
    if (favorites.has(key)) favorites.delete(key);
    else favorites.add(key);
    saveFavorites();
    applyFilters();
    return;
  }

  const openButton = event.target.closest('[data-open]');
  if (openButton) {
    openModal(findByKey(openButton.dataset.open));
    return;
  }

  const copyButton = event.target.closest('[data-copy]');
  if (copyButton) {
    const item = findByKey(copyButton.dataset.copy);
    if (item) copyText(copyButton, buildCitation(item));
    return;
  }

  const pageButton = event.target.closest('[data-page]');
  if (pageButton && !pageButton.disabled) {
    currentPage = parseInt(pageButton.dataset.page, 10) || 1;
    renderCurrentView();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
});

async function copyText(button, text) {
  const original = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = '✅ Скопировано';
  } catch (error) {
    button.textContent = 'Не удалось скопировать';
  }
  setTimeout(() => { button.textContent = original; }, 2000);
}

/* ---------- Модальное окно ---------- */

let lastFocusedElement = null;

function openModal(item) {
  if (!item) return;
  const modal = document.getElementById('modal-view');
  if (!modal) return;

  lastFocusedElement = document.activeElement;

  const year = recordYear(item);
  const abstractText = item.abstract_display
    || item.abstract_ru
    || item.abstract_original
    || 'Аннотация не найдена в источнике';

  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  };

  setText('modal-title', item.title_original || item.title || 'Без названия');
  setText('modal-authors', item.authors || 'Автор не указан');
  setText('modal-year', year ? String(year) : 'год не указан');
  setText('modal-discipline', item.category || 'Без категории');
  setText('modal-doctype', normalizeDocType(item.document_type || item.type) || 'не указан');
  setText('modal-country', normalizeCountry(item.country) || 'не указана');
  setText('modal-abstract', abstractText);
  setText('modal-citation', buildCitation(item));

  // Почему публикация включена в каталог: полное объяснение.
  const evidenceBox = document.getElementById('modal-evidence');
  const evidenceList = document.getElementById('modal-evidence-list');
  if (evidenceBox && evidenceList) {
    const evidence = Array.isArray(item.relevance_evidence) ? item.relevance_evidence : [];
    evidenceList.innerHTML = '';
    if (evidence.length) {
      evidence.forEach((line) => {
        const li = document.createElement('li');
        li.textContent = String(line || '');
        evidenceList.appendChild(li);
      });
      evidenceBox.style.display = '';
    } else {
      evidenceBox.style.display = 'none';
    }
  }

  const link = document.getElementById('modal-original-link');
  if (link) {
    const url = safeUrl(item.url);
    if (url) {
      link.href = url;
      link.style.display = '';
    } else {
      link.removeAttribute('href');
      link.style.display = 'none';
    }
  }

  modal.classList.add('is-open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');

  const closeButton = document.getElementById('modal-close');
  if (closeButton) closeButton.focus();
}

function closeModal() {
  const modal = document.getElementById('modal-view');
  if (!modal) return;
  modal.classList.remove('is-open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');

  if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
    lastFocusedElement.focus();
  }
}

/* ---------- Графики ---------- */

function updateCharts(dataset) {
  if (typeof Chart === 'undefined') {
    console.warn('Chart.js недоступен: графики не построены.');
    return;
  }

  const categoryCounts = {};
  CATEGORIES.forEach((category) => { categoryCounts[category] = 0; });
  dataset.forEach((item) => {
    const category = item.category || 'Без категории';
    categoryCounts[category] = (categoryCounts[category] || 0) + 1;
  });

  const donutCanvas = document.getElementById('donutChart');
  if (donutCanvas) {
    if (donutChartInstance) donutChartInstance.destroy();
    donutChartInstance = new Chart(donutCanvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: CATEGORIES.map((c) => (c.length > 24 ? c.slice(0, 22) + '…' : c)),
        datasets: [{
          data: CATEGORIES.map((c) => categoryCounts[c] || 0),
          backgroundColor: ['#10233F', '#29496B', '#B38A4B', '#2E7D32', '#C62828',
                            '#00838F', '#6A1B9A', '#D81B60', '#F57F17', '#4E342E', '#78909C'],
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
  dataset.forEach((item) => {
    const year = recordYear(item);
    if (year !== null) yearCounts[year] = (yearCounts[year] || 0) + 1;
  });

  const years = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);
  const lineCanvas = document.getElementById('lineChart');
  if (lineCanvas) {
    if (lineChartInstance) lineChartInstance.destroy();
    lineChartInstance = new Chart(lineCanvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: years,
        datasets: [{
          label: 'Публикации',
          data: years.map((y) => yearCounts[y]),
          borderColor: '#10233F',
          backgroundColor: 'rgba(41, 73, 107, 0.12)',
          borderWidth: 2,
          fill: true,
          tension: 0.3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
      }
    });
  }

  const countryCounts = {};
  dataset.forEach((item) => {
    const country = normalizeCountry(item.country) || 'Страна не указана';
    countryCounts[country] = (countryCounts[country] || 0) + 1;
  });

  const topCountries = Object.entries(countryCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  const barCanvas = document.getElementById('barChart');
  if (barCanvas) {
    if (barChartInstance) barChartInstance.destroy();
    barChartInstance = new Chart(barCanvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels: topCountries.map((entry) => entry[0]),
        datasets: [{
          data: topCountries.map((entry) => entry[1]),
          backgroundColor: '#29496B',
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { display: false } }
        }
      }
    });
  }
}

/* ---------- Экспорт CSV ---------- */

function csvCell(value) {
  const text = String(value == null ? '' : value);
  return '"' + text.replace(/"/g, '""') + '"';
}

function exportToCSV() {
  const headers = ['Направление', 'Название', 'Авторы', 'Год', 'Страна',
                   'Тип документа', 'Язык', 'DOI', 'Ссылка', 'Ссылка (библиография)',
                   'Основание включения'];

  const rows = [headers.map(csvCell).join(';')];

  filteredData.forEach((item) => {
    const year = recordYear(item);
    const evidence = Array.isArray(item.relevance_evidence)
      ? item.relevance_evidence.join(' | ')
      : '';
    rows.push([
      csvCell(item.category || 'Без категории'),
      csvCell(item.title_original || item.title || ''),
      csvCell(item.authors || ''),
      csvCell(year === null ? '' : year),
      csvCell(normalizeCountry(item.country)),
      csvCell(normalizeDocType(item.document_type || item.type)),
      csvCell(normalizeLanguage(item.language)),
      csvCell(item.doi || ''),
      csvCell(safeUrl(item.url)),
      csvCell(buildCitation(item)),
      csvCell(evidence)
    ].join(';'));
  });

  // BOM обязателен, иначе Excel откроет файл в неверной кодировке.
  const content = '\uFEFF' + rows.join('\r\n') + '\r\n';
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });

  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.href = url;
  link.download = showFavOnly ? 'olympic_favorites.csv' : 'olympic_catalog.csv';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}








