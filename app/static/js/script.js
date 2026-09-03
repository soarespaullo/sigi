/**
 * SiGI - Sistema Integrado de Gestão de Igreja
 * Frontend Utilities & Interactive Components
 */

/* ==========================================================================
   🌙 SiGI Theme Engine (Light / Dark Mode Architecture)
   ========================================================================== */
window.getTheme = function() {
  return localStorage.getItem('sigi_theme') || 'light';
};

window.setTheme = function(themeName) {
  if (themeName !== 'dark' && themeName !== 'light') {
    themeName = 'light';
  }
  
  // Atualiza atributos raiz do DOM
  document.documentElement.setAttribute('data-theme', themeName);
  document.documentElement.setAttribute('data-bs-theme', themeName);
  localStorage.setItem('sigi_theme', themeName);

  // Atualiza estado visual dos botões seletores se existirem na página
  updateThemeSelectorUI(themeName);

  // Atualiza Chart.js globalmente se presente
  if (window.applyChartTheme) {
    window.applyChartTheme(themeName === 'dark');
  }

  // Dispara evento customizado para componentes desacoplados (FullCalendar, etc)
  window.dispatchEvent(new CustomEvent('sigi-theme-changed', {
    detail: { theme: themeName, isDark: themeName === 'dark' }
  }));
};

function updateThemeSelectorUI(currentTheme) {
  const btnLight = document.getElementById('btnThemeLight');
  const btnDark = document.getElementById('btnThemeDark');
  const badgeLight = document.getElementById('badgeThemeLight');
  const badgeDark = document.getElementById('badgeThemeDark');

  if (btnLight && btnDark) {
    if (currentTheme === 'dark') {
      btnDark.classList.add('active');
      btnLight.classList.remove('active');
      if (badgeDark) badgeDark.classList.remove('d-none');
      if (badgeLight) badgeLight.classList.add('d-none');
    } else {
      btnLight.classList.add('active');
      btnDark.classList.remove('active');
      if (badgeLight) badgeLight.classList.remove('d-none');
      if (badgeDark) badgeDark.classList.add('d-none');
    }
  }
}

// Helper global para adaptar Chart.js ao tema
window.applyChartTheme = function(isDark) {
  if (typeof Chart === 'undefined') return;
  
  const textColor = isDark ? '#cbd5e1' : '#475569';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : '#f1f5f9';
  
  if (Chart.defaults) {
    Chart.defaults.color = textColor;
    Chart.defaults.borderColor = gridColor;
  }
  
  // Se houver instâncias registradas no Chart.instances, atualiza seus eixos e renderiza
  if (Chart.instances) {
    Object.values(Chart.instances).forEach(function(chart) {
      if (!chart || !chart.options) return;
      if (chart.options.scales) {
        Object.values(chart.options.scales).forEach(function(scale) {
          if (scale.grid) scale.grid.color = gridColor;
          if (scale.ticks) scale.ticks.color = textColor;
        });
      }
      if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
        chart.options.plugins.legend.labels.color = textColor;
      }
      chart.update();
    });
  }
};

document.addEventListener("DOMContentLoaded", function() {
  // Sincroniza botões seletores com o tema ativo
  const currentTheme = window.getTheme();
  updateThemeSelectorUI(currentTheme);

  // 1. Mostrar/ocultar campo de cônjuge dinamicamente
  const estadoCivilEl = document.getElementById("estadoCivil");
  const conjugeField = document.getElementById("conjugeField");

  function atualizarCampoConjuge() {
    if (!estadoCivilEl || !conjugeField) return;
    if (estadoCivilEl.value === "Casado") {
      conjugeField.style.display = "block";
    } else {
      conjugeField.style.display = "none";
    }
  }

  if (estadoCivilEl) {
    estadoCivilEl.addEventListener("change", atualizarCampoConjuge);
    atualizarCampoConjuge();
  }

  // 2. Habilitar modo de edição em formulários de visualização
  const btnHabilitar = document.getElementById("habilitarEdicao");
  if (btnHabilitar) {
    btnHabilitar.addEventListener("click", function() {
      document.querySelectorAll("#formEditar input, #formEditar select, #formEditar textarea").forEach(function(el) {
        el.removeAttribute("readonly");
        el.removeAttribute("disabled");
      });
      const salvarBtn = document.getElementById("salvarBtn");
      if (salvarBtn) salvarBtn.classList.remove("d-none");
      this.style.display = "none";
    });
  }

  // 3. Aplicação de máscaras de input (compatível com jQuery Mask se presente)
  if (typeof $ !== "undefined" && typeof $.fn.mask !== "undefined") {
    $('#telefone, input[name="telefone"]').mask('(00) 00000-0000');
    $('#cpf, input[name="cpf"]').mask('000.000.000-00');
    $('#rg, input[name="rg"]').mask('00.000.000-0');
    $('#cep, input[name="cep"]').mask('00000-000');
    $('#cnpj, input[name="cnpj"]').mask('00.000.000/0000-00');
  }

  // 4. Inicializar Tooltips do Bootstrap se disponíveis
  if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }
});
