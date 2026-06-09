(function(){
  const storageKey = 'parametrizacao-n2-theme';
  const getPreferredTheme = () => localStorage.getItem(storageKey) || 'auto';
  const getSystemTheme = () => window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  const setTheme = theme => {
    document.documentElement.setAttribute('data-bs-theme', theme === 'auto' ? getSystemTheme() : theme);
  };
  setTheme(getPreferredTheme());
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-theme-value]');
    if(!btn) return;
    const theme = btn.getAttribute('data-theme-value');
    localStorage.setItem(storageKey, theme);
    setTheme(theme);
  });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if(getPreferredTheme() === 'auto') setTheme('auto');
  });
})();
