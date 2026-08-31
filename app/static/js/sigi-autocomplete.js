/**
 * 🔍 SiGI — Componente Universal de Autocomplete & Busca Dinâmica
 * Suporta navegação por teclado (↑, ↓, Enter, Esc), debounce, AbortController,
 * estados de loading/empty/error, busca tolerante a acentos e vinculação de ID oculto.
 */

(function () {
  'use strict';

  class SigiAutocomplete {
    constructor(element, options = {}) {
      this.element = typeof element === 'string' ? document.querySelector(element) : element;
      if (!this.element) return;

      this.options = Object.assign({
        url: this.element.dataset.url || '/api/busca/membros',
        hiddenInput: this.element.dataset.hiddenInput || null,
        minChars: parseInt(this.element.dataset.minChars || 2, 10),
        debounceMs: parseInt(this.element.dataset.debounce || 250, 10),
        placeholder: this.element.getAttribute('placeholder') || 'Buscar...',
        mode: this.element.dataset.mode || 'lookup', // 'lookup' (select ID) ou 'search' (list search)
        onSelect: null,
        renderItem: null
      }, options);

      this.hiddenInputElement = this.options.hiddenInput
        ? (typeof this.options.hiddenInput === 'string'
            ? document.querySelector(this.options.hiddenInput)
            : this.options.hiddenInput)
        : null;

      this.currentFocusIndex = -1;
      this.items = [];
      this.debounceTimer = null;
      this.abortController = null;
      this.isOpen = false;

      this.init();
    }

    init() {
      this.setupDOM();
      this.bindEvents();
    }

    setupDOM() {
      // Wrapper
      if (!this.element.parentElement.classList.contains('sigi-autocomplete-wrapper')) {
        const wrapper = document.createElement('div');
        const inInputGroup = this.element.parentElement.classList.contains('input-group');
        wrapper.className = 'sigi-autocomplete-wrapper position-relative' + (inInputGroup ? ' sigi-in-input-group' : '');
        this.element.parentNode.insertBefore(wrapper, this.element);
        wrapper.appendChild(this.element);
        this.wrapper = wrapper;
      } else {
        this.wrapper = this.element.parentElement;
      }

      this.element.setAttribute('autocomplete', 'off');
      this.element.classList.add('sigi-autocomplete-input');

      // Botão de Limpar Seleção (Modo Lookup)
      if (this.options.mode === 'lookup' && this.hiddenInputElement && this.hiddenInputElement.value) {
        this.createClearButton();
      }

      // Container de Dropdown
      this.dropdown = document.createElement('div');
      this.dropdown.className = 'sigi-autocomplete-dropdown shadow-lg';
      this.dropdown.style.display = 'none';
      this.wrapper.appendChild(this.dropdown);
    }

    createClearButton() {
      if (this.wrapper.querySelector('.sigi-autocomplete-clear')) return;
      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'sigi-autocomplete-clear btn btn-link p-0 text-muted';
      clearBtn.innerHTML = '<i class="bi bi-x-circle-fill"></i>';
      clearBtn.title = 'Limpar seleção';
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        this.clearSelection();
      });
      this.wrapper.appendChild(clearBtn);
      this.wrapper.classList.add('has-selection');
    }

    removeClearButton() {
      const clearBtn = this.wrapper.querySelector('.sigi-autocomplete-clear');
      if (clearBtn) clearBtn.remove();
      this.wrapper.classList.remove('has-selection');
    }

    clearSelection() {
      this.element.value = '';
      if (this.hiddenInputElement) {
        this.hiddenInputElement.value = '';
        // Dispara evento change no input hidden
        this.hiddenInputElement.dispatchEvent(new Event('change', { bubbles: true }));
      }
      this.removeClearButton();
      this.close();
      this.element.focus();
    }

    bindEvents() {
      // Input com debounce
      this.element.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Se o usuário apagar o texto no modo lookup, desvincula o ID
        if (this.options.mode === 'lookup' && this.hiddenInputElement && !query) {
          this.hiddenInputElement.value = '';
          this.removeClearButton();
        }

        clearTimeout(this.debounceTimer);
        if (query.length < this.options.minChars) {
          this.close();
          return;
        }

        this.debounceTimer = setTimeout(() => {
          this.fetchResults(query);
        }, this.options.debounceMs);
      });

      // Foco abre se houver resultados
      this.element.addEventListener('focus', () => {
        const query = this.element.value.trim();
        if (query.length >= this.options.minChars && this.items.length > 0) {
          this.open();
        }
      });

      // Navegação por teclado
      this.element.addEventListener('keydown', (e) => {
        if (!this.isOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
          const query = this.element.value.trim();
          if (query.length >= this.options.minChars) {
            this.fetchResults(query);
          }
          return;
        }

        if (!this.isOpen) return;

        switch (e.key) {
          case 'ArrowDown':
            e.preventDefault();
            this.moveFocus(1);
            break;
          case 'ArrowUp':
            e.preventDefault();
            this.moveFocus(-1);
            break;
          case 'Enter':
            if (this.currentFocusIndex >= 0 && this.items[this.currentFocusIndex]) {
              e.preventDefault();
              this.selectItem(this.items[this.currentFocusIndex]);
            }
            break;
          case 'Escape':
            e.preventDefault();
            this.close();
            break;
          case 'Tab':
            this.close();
            break;
        }
      });

      // Fechar ao clicar fora
      document.addEventListener('click', (e) => {
        if (!this.wrapper.contains(e.target)) {
          this.close();
        }
      });
    }

    async fetchResults(query) {
      if (this.abortController) {
        this.abortController.abort();
      }
      this.abortController = new AbortController();

      this.showLoading();
      this.open();

      try {
        const separator = this.options.url.includes('?') ? '&' : '?';
        const url = `${this.options.url}${separator}q=${encodeURIComponent(query)}`;
        const response = await fetch(url, {
          signal: this.abortController.signal,
          headers: { 'Accept': 'application/json' }
        });

        if (!response.ok) {
          throw new Error('Erro na resposta da API');
        }

        const data = await response.json();
        this.items = Array.isArray(data) ? data : [];
        this.renderList(query);
      } catch (err) {
        if (err.name !== 'AbortError') {
          this.showError('Não foi possível carregar as sugestões.');
        }
      }
    }

    showLoading() {
      this.dropdown.innerHTML = `
        <div class="sigi-autocomplete-state p-3 text-center text-muted small">
          <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
          Buscando sugestões...
        </div>
      `;
    }

    showError(msg) {
      this.dropdown.innerHTML = `
        <div class="sigi-autocomplete-state p-3 text-center text-danger small">
          <i class="bi bi-exclamation-circle me-1"></i> ${msg}
        </div>
      `;
    }

    renderList(query) {
      this.currentFocusIndex = -1;

      if (!this.items || this.items.length === 0) {
        this.dropdown.innerHTML = `
          <div class="sigi-autocomplete-state p-3 text-center text-muted small">
            <i class="bi bi-search me-1"></i> Nenhum resultado encontrado para "<strong>${this.escapeHTML(query)}</strong>"
          </div>
        `;
        return;
      }

      this.dropdown.innerHTML = '';
      const listEl = document.createElement('ul');
      listEl.className = 'sigi-autocomplete-list list-unstyled mb-0';

      this.items.forEach((item, index) => {
        const itemEl = document.createElement('li');
        itemEl.className = 'sigi-autocomplete-item';
        itemEl.dataset.index = index;

        if (this.options.renderItem) {
          itemEl.innerHTML = this.options.renderItem(item);
        } else {
          itemEl.innerHTML = this.defaultItemTemplate(item);
        }

        itemEl.addEventListener('mouseenter', () => {
          this.setFocusIndex(index);
        });

        itemEl.addEventListener('click', (e) => {
          e.preventDefault();
          this.selectItem(item);
        });

        listEl.appendChild(itemEl);
      });

      this.dropdown.appendChild(listEl);
    }

    defaultItemTemplate(item) {
      const inicial = item.inicial || (item.label ? item.label.charAt(0).toUpperCase() : '?');
      
      let avatarHtml = '';
      if (item.foto) {
        avatarHtml = `
          <div class="sigi-avatar-wrapper me-2 flex-shrink-0 position-relative" style="width:34px; height:34px;">
            <img src="${this.escapeHTML(item.foto)}" class="sigi-avatar" alt="${this.escapeHTML(item.label)}"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                 style="width:34px; height:34px;">
            <div class="sigi-avatar bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center fw-bold"
                 style="display:none; width:34px; height:34px; font-size:0.9rem;">
              ${this.escapeHTML(inicial)}
            </div>
          </div>
        `;
      } else {
        avatarHtml = `
          <div class="sigi-avatar bg-primary bg-opacity-10 text-primary d-flex align-items-center justify-content-center fw-bold me-2 flex-shrink-0"
               style="width:34px; height:34px; font-size:0.9rem;">
            ${this.escapeHTML(inicial)}
          </div>
        `;
      }

      const statusBadge = item.status
        ? `<span class="badge ${item.status === 'Ativo' ? 'bg-success bg-opacity-10 text-success border border-success border-opacity-25' : 'bg-secondary bg-opacity-10 text-secondary border'} ms-2 px-2 py-1 small flex-shrink-0">${this.escapeHTML(item.status)}</span>`
        : '';

      return `
        <div class="d-flex align-items-center justify-content-between p-2">
          <div class="d-flex align-items-center flex-grow-1 overflow-hidden me-2">
            ${avatarHtml}
            <div class="overflow-hidden">
              <div class="fw-semibold text-dark text-truncate">${this.escapeHTML(item.label)}</div>
              ${item.subtext ? `<div class="small text-muted text-truncate">${this.escapeHTML(item.subtext)}</div>` : ''}
            </div>
          </div>
          ${statusBadge}
        </div>
      `;
    }

    moveFocus(direction) {
      const itemsCount = this.items.length;
      if (itemsCount === 0) return;

      let newIndex = this.currentFocusIndex + direction;
      if (newIndex >= itemsCount) newIndex = 0;
      if (newIndex < 0) newIndex = itemsCount - 1;

      this.setFocusIndex(newIndex);
    }

    setFocusIndex(index) {
      this.currentFocusIndex = index;
      const itemElements = this.dropdown.querySelectorAll('.sigi-autocomplete-item');
      itemElements.forEach((el, i) => {
        if (i === index) {
          el.classList.add('active');
          el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        } else {
          el.classList.remove('active');
        }
      });
    }

    selectItem(item) {
      this.element.value = item.label;

      if (this.hiddenInputElement) {
        this.hiddenInputElement.value = item.value || item.id;
        this.hiddenInputElement.dispatchEvent(new Event('change', { bubbles: true }));
        this.createClearButton();
      }

      if (typeof this.options.onSelect === 'function') {
        this.options.onSelect(item);
      } else if (this.options.mode === 'search') {
        // Se for modo de busca direta em listagem e o input estiver em um form, pode submeter
        const form = this.element.closest('form');
        if (form) {
          form.submit();
        }
      }

      this.close();
    }

    open() {
      this.dropdown.style.display = 'block';
      this.isOpen = true;
    }

    close() {
      this.dropdown.style.display = 'none';
      this.isOpen = false;
      this.currentFocusIndex = -1;
    }

    escapeHTML(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }
  }

  // Inicializador global exposto
  window.SigiAutocomplete = SigiAutocomplete;
  window.initSigiAutocomplete = function (selectorOrEl, options) {
    return new SigiAutocomplete(selectorOrEl, options);
  };

  // Auto-inicialização de elementos declarativos com [data-sigi-autocomplete]
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-sigi-autocomplete]').forEach((el) => {
      new SigiAutocomplete(el);
    });
  });
})();
