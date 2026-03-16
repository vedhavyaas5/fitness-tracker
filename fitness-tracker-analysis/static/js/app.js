document.addEventListener('DOMContentLoaded', () => {
  const q = (sel) => document.querySelector(sel);

  // Body form
  const bodyForm = q('#body-form');
  if (bodyForm) {
    bodyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(bodyForm).entries());
      try {
        const res = await fetch('/body', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const json = await res.json();
        q('#body-msg').textContent = json.ok ? `Saved. BMI: ${json.bmi ?? 'n/a'}` : 'Save failed';
        // Optionally append to table without refresh
        if (json.ok) {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${data.date || new Date().toISOString().slice(0,10)}</td><td>${data.weight_kg || ''}</td><td>${data.height_cm || ''}</td><td>${data.bodyfat_pct || ''}</td><td>${data.water_l || ''}</td><td>${data.notes || ''}</td>`;
          const tbody = q('#body-table tbody');
          if (tbody) tbody.prepend(tr);
          bodyForm.reset();
        }
      } catch (_) {
        q('#body-msg').textContent = 'Save failed';
      }
    });
  }

  // Workout form
  const workoutForm = q('#workout-form');
  if (workoutForm) {
    workoutForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(workoutForm).entries());
      try {
        const res = await fetch('/workout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const json = await res.json();
        q('#workout-msg').textContent = json.ok ? 'Saved.' : 'Save failed';
        if (json.ok) {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${data.date || new Date().toISOString().slice(0,10)}</td><td>${data.workout_type || 'other'}</td><td>${data.duration_min || 0}</td><td>${data.calories_burned || (Number(data.duration_min||0)*6)}</td><td>${data.notes || ''}</td>`;
          const tbody = q('#workout-table tbody');
          if (tbody) tbody.prepend(tr);
          workoutForm.reset();
        }
      } catch (_) {
        q('#workout-msg').textContent = 'Save failed';
      }
    });
  }

  // Suggestions
  const suggestionsList = q('#suggestions-list');
  if (suggestionsList) {
    fetch('/suggestions').then(r => r.json()).then(data => {
      suggestionsList.innerHTML = '';
      (data.suggestions || []).forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        suggestionsList.appendChild(li);
      });
    }).catch(() => {});
  }
});
