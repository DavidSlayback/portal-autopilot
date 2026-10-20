// Fake login and message box for the staged demo portals. Everything here is fictional;
// the credentials are printed on purpose. Login persists in localStorage so the Grok Bot's
// saved browser session behaves like a real "remember me" portal.
function store(op, key, value) {
  try { return op === 'get' ? localStorage.getItem(key) : localStorage.setItem(key, value); }
  catch { return null; }
}

function portal(key, user, pass, recipient = 'Billing Office') {
  // ?reset clears sent messages between demo runs but keeps the saved login.
  if (new URLSearchParams(location.search).has('reset')) {
    try { localStorage.removeItem(key + ':sent'); } catch {}
    history.replaceState(null, '', location.pathname);
  }
  const form = document.getElementById('login');
  const app = document.getElementById('app');
  const show = () => { form.hidden = true; app.hidden = false; };
  if (store('get', key) === 'in') show();
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const ok = form.elements.user.value.trim() === user && form.elements.pass.value === pass;
    document.getElementById('err').hidden = ok;
    if (ok) { store('set', key, 'in'); show(); }
  });
  document.getElementById('logout').addEventListener('click', () => {
    try { localStorage.removeItem(key); } catch {}
    location.reload();
  });
  const compose = document.getElementById('compose');
  if (compose) messages(key + ':sent', compose, recipient);
}

function messages(key, compose, recipient) {
  const list = document.getElementById('sent');
  const render = () => {
    const sent = JSON.parse(store('get', key) || '[]');
    list.replaceChildren(...sent.map((m) => {
      const li = document.createElement('li');
      li.innerHTML = `<b>${m.ref}</b> · ${m.at} · <i></i><pre></pre>`;
      li.querySelector('i').textContent = m.subject;
      li.querySelector('pre').textContent = m.body;
      return li;
    }));
  };
  compose.addEventListener('submit', (e) => {
    e.preventDefault();
    const sent = JSON.parse(store('get', key) || '[]');
    const ref = 'MSG-' + String(Date.now()).slice(-6);
    sent.unshift({ ref, at: new Date().toLocaleString(), subject: compose.elements.subject.value,
                   body: compose.elements.body.value });
    store('set', key, JSON.stringify(sent));
    compose.reset();
    document.getElementById('confirm').textContent =
      `Your message was sent to the ${recipient}. Reference number: ${ref}`;
    render();
  });
  render();
}
