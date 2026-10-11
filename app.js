let rawData = [];
let categoryChartInstance = null;
let dynamicsChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setupModal();
  setupAdminPanel();
});

// Загрузка данных из web_data.json
async function loadData() {
  try {
    const response = await fetch('web_data.json');
    if (!response.ok) {
      throw new Error('Ошибка загрузки данных');
    }
    rawData = await response.json();
    
    // Обновляем счетчик в шапке
    const counterEl = document.querySelector('#db-counter span');
    if (counterEl) {
      counterEl.textContent = rawData.length.toLocaleString('ru-RU');
    }

    renderFeed(rawData);
    renderAnalytics(rawData);
  } catch (error) {
    console.error('Не удалось загрузить данные:', error);
    const feed = document.getElementById('articles-feed');
    if (feed) {
      feed.innerHTML = '<p style="padding: 20px; color: #d9534f;">Ошибка загрузки базы данных исследований.</p>';
    }
  }
}

// Отрисовка ленты исследований
function renderFeed(items) {
  const feed = document.getElementById('articles-feed');
  if (!feed) return;

  feed.innerHTML = '';

  if (items.length === 0) {
    feed.innerHTML = '<p style="padding: 20px; color: #666;">Исследования не найдены.</p>';
    return;
  }

  items.forEach((item, index) => {
    const card = document.createElement('div');
    card.className = 'article-card';
    
    const category = item.category || 'Теория и методология олимпийского движения';
    const type = item.type || 'Научная статья';
    const title = item.title || 'Без названия';
    const authors = item.authors || 'Автор не указан';
    const year = item.year || 2026;
    const country = item.country || 'Другие страны';
    const url = item.url || '#';
    
    // Приоритет русскому переводу аннотации, иначе оригинал
    const summary = item.summary_ru || item.summary || item.abstract || 'Аннотация отсутствует.';

    // Генерация ГОСТ Р 7.0.100–2018 (защита от попадания категории/издателя в авторы)
    const gostCitation = generateGostCitation(authors, title, year, url);

    card.innerHTML = `
      <div class="article-header">
        <span class="article-category">${escapeHtml(category)}</span>
      </div>
      <div class="article-type">${escapeHtml(type)}</div>
      <h2 class="article-title">${escapeHtml(title)}</h2>
      <div class="article-meta-info">
        <span class="authors">${escapeHtml(authors)} (${year})</span>
        <span class="country-tag">🌐 ${escapeHtml(country)}</span>
      </div>
      <div class="article-abstract">
        <strong>📌 Аннотация:</strong> ${escapeHtml(summary)}
      </div>
      <div class="gost-block">
        <div class="gost-title">ГОСТ Р 7.0.100–2018:</div>
        <div class="gost-text" id="gost-${index}">${escapeHtml(gostCitation)}</div>
        <button class="btn-copy" onclick="copyGost('gost-${index}', this)">Копировать цитату</button>
      </div>
      <div class="card-footer">
        <button class="btn-read-more" onclick='openModal(${JSON.stringify(item).replace(/'/g, "&apos;")})'>Читать аннотацию</button>
        <a href="${escapeHtml(url)}" target="_blank" class="btn-original">Оригинал ↗</a>
      </div>
    `;

    feed.appendChild(card);
  });
}

// Генерация ГОСТ цитаты
function generateGostCitation(authors, title, year, url) {
  let cleanAuthors = authors;
  if (authors.includes("Теория") || authors.includes("Подготовка") || authors.includes("История")) {
    cleanAuthors = "Авторский коллектив";
  }
  return `${cleanAuthors}. ${title} // Электронный ресурс / Научная публикация. — ${year}. — URL: ${url} (дата обращения: 10.10.2026).`;
}

// Копирование ГОСТ цитаты в буфер обмена
window.copyGost = function(elementId, btn) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    const originalText = btn.textContent;
    btn.textContent = 'Скопировано ✓';
    btn.style.background = '#2E7D32';
    btn.style.color = '#fff';
    setTimeout(() => {
      btn.textContent = originalText;
      btn.style.background = '';
      btn.style.color = '';
    }, 2000);
  });
};

// Модальное окно просмотра аннотации
function setupModal() {
  const modal = document.getElementById('modal-overlay');
  const closeBtn = document.getElementById('modal-close');

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      modal.style.display = 'none';
    });
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.style.display = 'none';
      }
    });
  }
}

window.openModal = function(item) {
  const modal = document.getElementById('modal-overlay');
  document.getElementById('modal-title').textContent = item.title || 'Без названия';
  document.getElementById('modal-meta').textContent = `${item.authors || 'Автор не указан'} (${item.year || 2026})`;
  document.getElementById('modal-abstract').textContent = item.summary_ru || item.summary || item.abstract || 'Аннотация отсутствует.';
  document.getElementById('modal-link').href = item.url || '#';
  modal.style.display = 'flex';
};

// Рендеринг графиков аналитики
function renderAnalytics(items) {
  const categoriesCount = {};
  const yearsCount = {};

  items.forEach(item => {
    const cat = item.category || 'Другое';
    categoriesCount[cat] = (categoriesCount[cat] || 0) + 1;

    const yr = item.year || 2026;
    yearsCount[yr] = (yearsCount[yr] || 0) + 1;
  });

  const catCtx = document.getElementById('categoryChart');
  if (catCtx) {
    if (categoryChartInstance) categoryChartInstance.destroy();
    
    categoryChartInstance = new Chart(catCtx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(categoriesCount),
        datasets: [{
          data: Object.values(categoriesCount),
          backgroundColor: ['#1a365d', '#2E7D32', '#d97706', '#7c3aed', '#0284c7', '#64748b']
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 10 } } }
        }
      }
    });
  }

  const sortedYears = Object.keys(yearsCount).sort();
  const sortedData = sortedYears.map(yr => yearsCount[yr]);

  const dynCtx = document.getElementById('dynamicsChart');
  if (dynCtx) {
    if (dynamicsChartInstance) dynamicsChartInstance.destroy();

    dynamicsChartInstance = new Chart(dynCtx, {
      type: 'line',
      data: {
        labels: sortedYears,
        datasets: [{
          label: 'Публикации',
          data: sortedData,
          borderColor: '#1a365d',
          backgroundColor: 'rgba(26, 54, 93, 0.1)',
          fill: true,
          tension: 0.2
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } }
      }
    });
  }
}

// Экранирование HTML для безопасности
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Логика Панели администратора
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

  const ADMIN_PASS = "olympic2026"; // Пароль администратора

  if (btnOpen) {
    btnOpen.addEventListener('click', () => {
      adminModal.style.display = 'flex';
      authSection.style.display = 'block';
      panelSection.style.display = 'none';
      passwordInput.value = '';
    });
  }

  const closeAdmin = () => {
    adminModal.style.display = 'none';
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
      renderFeed(rawData);
      renderAnalytics(rawData);

      const counterEl = document.querySelector('#db-counter span');
      if (counterEl) {
        counterEl.textContent = rawData.length.toLocaleString('ru-RU');
      }

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