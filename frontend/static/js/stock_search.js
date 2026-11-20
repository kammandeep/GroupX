(() => {
  const dialog = document.getElementById('stock-search');
  if (!dialog) return;

  const input = document.getElementById('stock-search-input');
  const list = document.getElementById('stock-search-list');
  const empty = document.getElementById('stock-search-empty');
  const emptyDetail = document.getElementById('stock-search-empty-detail');
  const DEBOUNCE_MS = 150;
  let timer;
  let latestRequest = 0;

  function row(stock) {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.className = 'stock-search__row';
    link.href = dialog.dataset.stockUrl.replace('TICKER', encodeURIComponent(stock.ticker));
    item.append(link);

    const label = document.createElement('div');
    const ticker = document.createElement('strong');
    ticker.textContent = stock.ticker;
    const name = document.createElement('span');
    name.className = 'stock-search__name';
    name.textContent = stock.name;
    label.append(ticker, name);

    const price = document.createElement('span');
    price.textContent = stock.price == null ? '-' : `$${stock.price.toFixed(2)}`;

    const change = document.createElement('span');
    if (stock.change_pct == null) {
      change.textContent = '-';
    } else {
      change.className = stock.change_pct >= 0 ? 'up' : 'down';
      change.textContent = `${stock.change_pct >= 0 ? '+' : ''}${stock.change_pct.toFixed(1)}%`;
    }

    link.append(label, price, change);
    return item;
  }

  function show(stocks, query) {
    list.replaceChildren(...stocks.map(row));
    empty.hidden = stocks.length > 0;
    if (!stocks.length) {
      emptyDetail.textContent = query
        ? `“${query}” isn’t in our database.`
        : 'There are no stocks in our database yet.';
    }
  }

  function showError() {
    list.replaceChildren();
    empty.hidden = false;
    document.querySelector('.stock-search__empty-title').textContent = 'Search failed';
    emptyDetail.textContent = 'We couldn’t load stocks. Please try again.';
  }

  async function search(query) {
    const requestId = ++latestRequest;
    try {
      const response = await fetch(`${dialog.dataset.url}?q=${encodeURIComponent(query)}`, {
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`Search returned ${response.status}`);
      const { stocks } = await response.json();
      if (requestId !== latestRequest) return; // a newer search is already running
      document.querySelector('.stock-search__empty-title').textContent = 'Stock not available';
      show(stocks, query);
    } catch (error) {
      if (requestId === latestRequest) showError();
      console.error(error);
    }
  }

  document.querySelectorAll('[data-open-stock-search]').forEach((button) => {
    button.addEventListener('click', () => {
      input.value = '';
      dialog.showModal();
      input.focus();
      search('');
    });
  });

  input.addEventListener('input', () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => search(input.value.trim()), DEBOUNCE_MS);
  });

  dialog.querySelector('[data-close-stock-search]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close(); // click on the dimmed backdrop
  });
})();
