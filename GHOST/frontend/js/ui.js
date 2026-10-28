// Utilitários de interface: criação de elementos, avisos e diálogos.
export function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'class') e.className = v;
    else if (v === true) e.setAttribute(k, '');
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}

export function toast(msg, kind = '') {
  const t = h('div', { class: 'toast ' + kind, role: kind ? 'alert' : 'status' }, msg);
  document.getElementById('toasts').append(t);
  setTimeout(() => t.remove(), kind === 'error' ? 7000 : 3000);
}

export function modal(title, body, { actions = [] } = {}) {
  return new Promise(resolve => {
    const d = h('dialog', { class: 'modal' });
    const close = v => { d.close(); d.remove(); resolve(v); };
    d.append(
      h('header', {}, h('h2', {}, title), h('button', { class: 'icon', type: 'button', title: 'Fechar', onclick: () => close(null) }, '×')),
      h('div', { class: 'body' }, body),
      h('footer', {}, actions.map(a => h('button', {
        type: 'button', class: a.kind || '',
        onclick: async () => {
          let r;
          try { r = await a.run?.(); } catch (e) { toast(e.message, 'error'); return; }
          if (r !== false) close(a.value ?? true);
        },
      }, a.label))),
    );
    d.addEventListener('cancel', e => { e.preventDefault(); close(null); });
    document.body.append(d);
    d.showModal();
  });
}

export async function confirmDialog(message, label = 'Confirmar') {
  const r = await modal('Confirmar ação', h('p', {}, message), {
    actions: [{ label: 'Cancelar', value: false }, { label, kind: 'danger', value: true }],
  });
  return r === true;
}
