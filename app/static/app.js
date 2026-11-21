document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('menu-toggle');
  const update = () => {
    const expanded = window.innerWidth <= 800 ? document.body.classList.contains('sidebar-collapsed') : !document.body.classList.contains('sidebar-collapsed');
    toggle.setAttribute('aria-expanded', String(expanded));
    document.getElementById('sidebar').inert = !expanded;
  };
  window.addEventListener('resize', update);
  toggle.addEventListener('click', () => { document.body.classList.toggle('sidebar-collapsed'); update(); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && window.innerWidth <= 800) { document.body.classList.remove('sidebar-collapsed'); update(); } });
  update();
  document.querySelectorAll('form[method="post"]').forEach(form => {
    form.addEventListener('submit', () => {
      form.setAttribute('aria-busy', 'true');
      form.querySelectorAll('button[type="submit"], button:not([type])').forEach(button => {
        button.disabled = true;
        button.textContent = 'Saving...';
      });
    });
  });
  const element = document.getElementById('chart-data');
  if (!element || typeof Chart === 'undefined') return;
  const data = JSON.parse(element.textContent);
  Chart.defaults.font.family = 'Inter, Segoe UI, sans-serif';
  Chart.defaults.color = '#607568';
  Chart.defaults.font.size = 10;
  const colors = ['#bed8c0', '#69a866', '#006a4d'];
  const options = {responsive:true, maintainAspectRatio:false, animation:!window.matchMedia('(prefers-reduced-motion: reduce)').matches, plugins:{legend:{display:false}}};
  new Chart(document.getElementById('status'), {type:'doughnut', data:{labels:['New','In Progress','Done'],datasets:[{data:['New','In Progress','Done'].map(s=>data.statuses[s]||0),backgroundColor:colors,borderWidth:4,borderColor:'#fff'}]},options:{...options,cutout:'74%'}});
  new Chart(document.getElementById('priority'), {type:'bar',data:{labels:['Low','Medium','High'],datasets:[{data:['Low','Medium','High'].map(p=>data.priorities[p]||0),backgroundColor:['#a8cfac','#52955f','#006a4d'],borderRadius:5,maxBarThickness:28}]},options:{...options,scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false}}}}});
  new Chart(document.getElementById('trend'), {type:'line',data:{labels:data.trend.map(r=>r.day),datasets:[{data:data.trend.map(r=>r.total),borderColor:'#006a4d',backgroundColor:'#006a4d18',fill:true,tension:.3,pointRadius:3,borderWidth:2}]},options:{...options,scales:{y:{beginAtZero:true,ticks:{precision:0}},x:{grid:{display:false},ticks:{maxTicksLimit:5}}}}});
});