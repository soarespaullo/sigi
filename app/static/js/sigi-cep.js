/**
 * 📍 SiGI — Componente Universal de Consulta de CEP (ViaCEP)
 * Integração global, preenchimento automático inteligente, feedback visual e máscara.
 */

(function () {
  'use strict';

  // Cache em memória para evitar consultas duplicadas
  const cepCache = new Map();

  /**
   * Formata uma string de dígitos no formato 00000-000
   * @param {string} val 
   * @returns {string}
   */
  function formatarCep(val) {
    const digits = (val || '').replace(/\D/g, '').slice(0, 8);
    if (digits.length <= 5) {
      return digits;
    }
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  }

  /**
   * Extrai o número ou complemento existente de um campo de endereço caso o usuário já tenha digitado
   * Ex: "Rua das Flores, 123 - Apto 4" -> número "123", complemento "Apto 4"
   */
  function extrairNumeroEComplemento(textoAtual) {
    if (!textoAtual) return { numero: '', complemento: '' };
    const partes = textoAtual.split(',');
    if (partes.length > 1) {
      const resto = partes.slice(1).join(',').trim();
      return { resto };
    }
    return { resto: '' };
  }

  /**
   * Inicializa o componente de CEP em um input específico
   * @param {HTMLInputElement} inputEl 
   */
  function initCepField(inputEl) {
    if (inputEl.dataset.sigiCepInitialized) return;
    inputEl.dataset.sigiCepInitialized = 'true';

    // Cria ou localiza o wrapper visual
    let wrapper = inputEl.closest('.sigi-cep-wrapper');
    let statusIcon = null;
    let feedbackEl = null;

    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'sigi-cep-wrapper position-relative';
      inputEl.parentNode.insertBefore(wrapper, inputEl);
      wrapper.appendChild(inputEl);
    }

    statusIcon = wrapper.querySelector('.sigi-cep-status');
    if (!statusIcon) {
      statusIcon = document.createElement('span');
      statusIcon.className = 'sigi-cep-status position-absolute end-0 top-50 translate-middle-y me-3 text-muted';
      statusIcon.style.pointerEvents = 'none';
      statusIcon.innerHTML = '<i class="bi bi-geo-alt"></i>';
      wrapper.appendChild(statusIcon);
    }

    feedbackEl = wrapper.querySelector('.sigi-cep-feedback');
    if (!feedbackEl) {
      feedbackEl = document.createElement('div');
      feedbackEl.className = 'sigi-cep-feedback small mt-1';
      feedbackEl.style.display = 'none';
      wrapper.parentNode.insertBefore(feedbackEl, wrapper.nextSibling);
    }

    let abortCtrl = null;
    let lastConsultedCep = '';

    // Localizar campos de destino (via data-attributes ou busca no mesmo form)
    function getTargetElement(attrName, fallbackSelectors) {
      const customSelector = inputEl.getAttribute(attrName);
      if (customSelector) {
        const el = document.querySelector(customSelector);
        if (el) return el;
      }
      const form = inputEl.closest('form') || document;
      for (const sel of fallbackSelectors) {
        const el = form.querySelector(sel);
        if (el) return el;
      }
      return null;
    }

    const logradouroEl = getTargetElement('data-target-logradouro', ['#endereco', '[name="endereco"]', '#logradouro', '[name="logradouro"]']);
    const bairroEl = getTargetElement('data-target-bairro', ['#bairro', '[name="bairro"]']);
    const cidadeEl = getTargetElement('data-target-cidade', ['#cidade', '[name="cidade"]', '#naturalidade', '[name="naturalidade"]']);
    const estadoEl = getTargetElement('data-target-estado', ['#estado', '[name="estado"]', '#uf', '[name="uf"]']);
    const numeroEl = getTargetElement('data-target-numero', ['#numero', '[name="numero"]']);
    const complementoEl = getTargetElement('data-target-complemento', ['#complemento', '[name="complemento"]']);

    function setStatus(state, message = '') {
      if (state === 'loading') {
        statusIcon.innerHTML = '<span class="spinner-border spinner-border-sm text-primary" role="status"></span>';
        feedbackEl.style.display = 'none';
        feedbackEl.className = 'sigi-cep-feedback small mt-1 text-primary';
        feedbackEl.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i> Consultando endereço...';
      } else if (state === 'success') {
        statusIcon.innerHTML = '<i class="bi bi-check-circle-fill text-success"></i>';
        feedbackEl.style.display = 'block';
        feedbackEl.className = 'sigi-cep-feedback small mt-1 text-success';
        feedbackEl.innerHTML = `<i class="bi bi-check2 me-1"></i> ${message || 'Endereço localizado com sucesso.'}`;
        setTimeout(() => {
          if (feedbackEl) feedbackEl.style.display = 'none';
        }, 4000);
      } else if (state === 'error') {
        statusIcon.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-warning"></i>';
        feedbackEl.style.display = 'block';
        feedbackEl.className = 'sigi-cep-feedback small mt-1 text-danger';
        feedbackEl.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i> ${message || 'CEP não localizado.'}`;
      } else {
        statusIcon.innerHTML = '<i class="bi bi-geo-alt text-muted"></i>';
        feedbackEl.style.display = 'none';
      }
    }

    function preencherCampos(dados) {
      const hasSeparateFields = !!(bairroEl || cidadeEl || estadoEl);

      // 1. Logradouro / Endereço
      if (logradouroEl) {
        if (!hasSeparateFields) {
          // Caso de campo único (ex: dados da Igreja)
          const partes = [];
          if (dados.logradouro) partes.push(dados.logradouro);
          if (dados.bairro) partes.push(dados.bairro);
          if (dados.cidade && (dados.estado || dados.uf)) partes.push(`${dados.cidade} - ${dados.estado || dados.uf}`);
          if (dados.cep) partes.push(`CEP: ${dados.cep}`);
          logradouroEl.value = partes.join(', ');
        } else if (dados.logradouro) {
          // Caso de campos separados (ex: Membros, Visitantes)
          const atual = logradouroEl.value.trim();
          const extra = extrairNumeroEComplemento(atual);
          if (extra.resto && !logradouroEl.getAttribute('data-single-field')) {
            logradouroEl.value = `${dados.logradouro}, ${extra.resto}`;
          } else {
            logradouroEl.value = dados.logradouro;
          }
        }
        logradouroEl.dispatchEvent(new Event('input', { bubbles: true }));
        logradouroEl.dispatchEvent(new Event('change', { bubbles: true }));
      }

      // 2. Bairro
      if (bairroEl && dados.bairro) {
        bairroEl.value = dados.bairro;
        bairroEl.dispatchEvent(new Event('input', { bubbles: true }));
        bairroEl.dispatchEvent(new Event('change', { bubbles: true }));
      }

      // 3. Cidade
      if (cidadeEl && dados.cidade) {
        // Caso o campo seja "Cidade / Naturalidade" ou aceite "Cidade - UF"
        if (cidadeEl.name === 'naturalidade' || cidadeEl.id === 'naturalidade') {
          cidadeEl.value = `${dados.cidade} - ${dados.estado || dados.uf}`;
        } else {
          cidadeEl.value = dados.cidade;
        }
        cidadeEl.dispatchEvent(new Event('input', { bubbles: true }));
        cidadeEl.dispatchEvent(new Event('change', { bubbles: true }));
      }

      // 4. Estado / UF
      if (estadoEl && (dados.estado || dados.uf)) {
        estadoEl.value = dados.estado || dados.uf;
        estadoEl.dispatchEvent(new Event('input', { bubbles: true }));
        estadoEl.dispatchEvent(new Event('change', { bubbles: true }));
      }

      // Se existir campo de número separado e estiver vazio, foca nele
      if (numeroEl && !numeroEl.value) {
        numeroEl.focus();
      }
    }

    async function consultar(cepNumerico) {
      if (!cepNumerico || cepNumerico.length !== 8) return;

      // Se for o mesmo CEP já carregado com sucesso, não repete
      if (cepNumerico === lastConsultedCep && statusIcon.querySelector('.bi-check-circle-fill')) {
        return;
      }

      // Verifica cache em memória
      if (cepCache.has(cepNumerico)) {
        const dadosCached = cepCache.get(cepNumerico);
        if (dadosCached.success) {
          lastConsultedCep = cepNumerico;
          preencherCampos(dadosCached);
          setStatus('success', `${dadosCached.cidade}/${dadosCached.estado}`);
          return;
        }
      }

      if (abortCtrl) {
        abortCtrl.abort();
      }
      abortCtrl = new AbortController();

      setStatus('loading');

      try {
        let data = null;
        let success = false;

        // 1. Tenta consulta direta no ViaCEP via navegador do cliente
        try {
          const directResp = await fetch(`https://viacep.com.br/ws/${cepNumerico}/json/`, {
            signal: abortCtrl.signal,
            mode: 'cors'
          });

          if (directResp.ok) {
            const viacepData = await directResp.json();
            if (viacepData.erro) {
              data = { success: false, erro: 'CEP não encontrado. Verifique o número digitado.' };
            } else {
              data = {
                success: true,
                cep: viacepData.cep || '',
                logradouro: viacepData.logradouro || '',
                complemento: viacepData.complemento || '',
                bairro: viacepData.bairro || '',
                cidade: viacepData.localidade || '',
                estado: viacepData.uf || '',
                uf: viacepData.uf || ''
              };
              success = true;
            }
          }
        } catch (directErr) {
          if (directErr.name === 'AbortError') return;
        }

        // 2. Se a chamada direta falhar, tenta o endpoint proxy local do backend
        if (!data || !success) {
          try {
            const resp = await fetch(`/api/cep/${cepNumerico}`, {
              signal: abortCtrl.signal,
              headers: { 'Accept': 'application/json' }
            });
            const backendData = await resp.json();
            if (resp.ok && backendData.success) {
              data = backendData;
              success = true;
            } else if (!data) {
              data = backendData;
            }
          } catch (backendErr) {
            if (backendErr.name === 'AbortError') return;
          }
        }

        if (data) {
          cepCache.set(cepNumerico, data);
        }

        if (success && data && data.success) {
          lastConsultedCep = cepNumerico;
          preencherCampos(data);
          setStatus('success', `${data.cidade}/${data.estado}`);
        } else {
          lastConsultedCep = '';
          setStatus('error', (data && data.erro) ? data.erro : 'CEP não encontrado.');
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        lastConsultedCep = '';
        console.warn('[SiGI CEP] Erro:', err);
        setStatus('error', 'Não foi possível consultar o CEP. Preencha o endereço manualmente.');
      }
    }

    function processarInput() {
      const rawValue = inputEl.value;
      const formatted = formatarCep(rawValue);

      if (formatted !== rawValue) {
        inputEl.value = formatted;
      }

      const digitsOnly = formatted.replace(/\D/g, '');
      if (digitsOnly.length === 8) {
        consultar(digitsOnly);
      } else if (digitsOnly.length === 0) {
        lastConsultedCep = '';
        setStatus('default');
      }
    }

    // Eventos de digitação, alteração e colagem
    inputEl.addEventListener('input', processarInput);
    inputEl.addEventListener('change', processarInput);
    inputEl.addEventListener('keyup', function (e) {
      if (e.key === 'Enter') {
        const digitsOnly = inputEl.value.replace(/\D/g, '');
        if (digitsOnly.length === 8) consultar(digitsOnly);
      }
    });

    inputEl.addEventListener('blur', function () {
      const digitsOnly = inputEl.value.replace(/\D/g, '');
      if (digitsOnly.length > 0 && digitsOnly.length < 8) {
        setStatus('error', 'CEP incompleto. Digite os 8 dígitos.');
      }
    });

    // Se o campo já estiver carregado com 8 dígitos e sem endereço, pode consultar ao focar/clicar no ícone
    statusIcon.style.cursor = 'pointer';
    statusIcon.style.pointerEvents = 'auto';
    statusIcon.addEventListener('click', function () {
      const digitsOnly = inputEl.value.replace(/\D/g, '');
      if (digitsOnly.length === 8) {
        lastConsultedCep = ''; // força reconsulta
        consultar(digitsOnly);
      }
    });
  }

  // Inicialização automática para todos os inputs com data-sigi-cep ou id="cep"
  function initAll() {
    const selector = 'input[data-sigi-cep], input#cep, input[name="cep"]';
    document.querySelectorAll(selector).forEach(initCepField);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

  // Expõe inicializador global para modais ou elementos dinâmicos
  window.initSigiCep = initAll;
  window.initSigiCepField = initCepField;

})();
