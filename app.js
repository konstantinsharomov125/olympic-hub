let rawData = [];
let filteredData = [];
let favorites = new Set();
let showFavOnly = false;

let currentViewMode = 'grid';
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
      // Пробуем следующий путь
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

function normalizeCountry(raw) {
  if (!raw || raw === 'NR' || raw === 'N/A' || raw === 'null') return 'Другие страны';
  const s = String(raw).trim();
  if (s.toLowerCase().includes('russia') || s.toLowerCase().includes('росси')) return 'Россия';
  if (s.toLowerCase().includes('usa') || s.toLowerCase().includes('сша')) return 'США';
  if (s.toLowerCase().includes('china') || s.toLowerCase().includes('китай')) return 'Китай';
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

function setupEventListeners() {
  const modalClose = document.getElementById('modal-close');
  if (modalClose) modalClose.addEventListener('click', closeModal);

  const modalView = document.getElementById('modal-view');
  if (modalView) {
    modalView.addEventListener('click', (e) => {
      if (e.target.id === 'modal-view') closeModal();
    });
  }
}

function applyFilters() {
  filteredData = [...rawData];

  const headerStatElem = document.getElementById('header-stat-count');
  if (headerStatElem) headerStatElem.innerText = rawData.length.toLocaleString('ru-RU');

  renderCurrentView();
  updateCharts(filteredData);
}

function renderCurrentView() {
  const container = document.getElementById('publications-feed');
  if (!container) return;

  const items = filteredData.slice(0, 60);

  if (items.length === 0) {
    container.innerHTML = `<div class="pub-card" style="text-align: center; padding: 3rem;"><p>Исследования не найдены или загружаются...</p></div>`;
    return;
  }

  container.className = 'cards-grid';
  container.innerHTML = items.map(item => renderGridCardHtml(item)).join('');
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
    <article class="pub-card" style="background: #FFFDF9; border: 1px solid #E4DED2; border-radius: 6px; padding: 18px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.03);">
      <div class="pub-badge-group" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span class="badge-cat" style="font-size: 10px; background: #10233F; color: #FFFDF9; padding: 3px 8px; border-radius: 3px; font-weight: 600;">${escapeHtml(category)}</span>
        <button style="background:none; border:none; cursor:pointer; font-size:1.2rem; color:${isFav ? '#d4af37' : '#ccc'};" onclick="toggleFavorite(${realIndex})">★</button>
      </div>
      
      <span class="badge-type" style="font-size: 11px; color: #697586; display: block; margin-bottom: 6px;">${escapeHtml(docType)}</span>
      
      <h3 class="pub-card-title" style="font-size: 15px; color: #10233F; margin-bottom: 8px; cursor: pointer;" onclick="openModalByItemIndex(${realIndex})">${escapeHtml(title)}</h3>
      
      <div class="pub-author-row" style="font-size: 12px; color: #333; margin-bottom: 4px;">${escapeHtml(authors)} (${year})</div>
      <div class="pub-country-row" style="font-size: 12px; color: #697586; margin-bottom: 8px;">🌐 ${escapeHtml(country)}</div>

      <div class="ai-summary-box" style="margin-top: 8px; margin-bottom: 8px; padding: 8px 10px; background: #f0f4f8; border-left: 3px solid #10233F; border-radius: 4px; font-size: 11px; color: #1a202c;">
        <span style="font-weight: bold; color: #10233F;">📌 Аннотация:</span> ${escapeHtml(summary)}
      </div>

      <div class="gost-citation-box" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 6px; border: 1px solid #e9ecef; font-size: 11px; color: #333;">
        <div style="font-weight: bold; margin-bottom: 3px; color: #555;">📋 ГОСТ Р 7.0.100-2018:</div>
        <div style="margin-bottom: 6px; font-style: italic; line-height: 1.3;">${escapeHtml(gostCitationText)}</div>
        <button onclick="copyGostCitation(this, ${realIndex})" style="background: #007bff; color: white; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 11px;">
          📋 Копировать цитату
        </button>
      </div>

      <div class="pub-card-footer" style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
        <button class="btn-card-action" onclick="openModalByItemIndex(${realIndex})" style="background: #10233F; color: #fff; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;">
          Читать аннотацию
        </button>
        <a href="${originalUrl}" target="_blank" style="font-size: 11px; color: #10233F; text-decoration: none; font-weight: 600;">
          Оригинал ↗
        </a>
      </div>
    </article>
  `;
}

window.toggleFavorite = function(index) {
  if (favorites.has(index)) favorites.delete(index);
  else favorites.add(index);
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

  document.getElementById('modal-view').classList.add('active');
}

function closeModal() {
  document.getElementById('modal-view').classList.remove('active');
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

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}