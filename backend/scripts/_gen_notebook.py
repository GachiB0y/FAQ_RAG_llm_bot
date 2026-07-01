"""Генератор Jupyter notebook: 01_experiment_analysis.ipynb"""
import json
from pathlib import Path

nb = {
    "cells": [],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def _to_lines(text):
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines else [])


def md(text):
    nb["cells"].append(
        {"cell_type": "markdown", "metadata": {}, "source": _to_lines(text.strip())}
    )


def code(text):
    nb["cells"].append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": _to_lines(text.strip()),
        }
    )


md(
    """# Анализ эксперимента Ragas + MLflow: Dense vs Hybrid

**Цель:** интерактивный разбор результатов двух экспериментов (28.06 и 30.06 2026) — те же графики что в отчёте, но с живым кодом и возможностью копнуть глубже.

Данные читаются напрямую из MLflow-артефактов на диске (`backend/mlruns/`) — без запуска MLflow-сервиса."""
)

md("## 1. Setup — импорты и пути")

code(
    """from pathlib import Path
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

mpl.rcParams['font.family'] = 'DejaVu Sans'
mpl.rcParams['figure.dpi'] = 100

# Путь к репо — работает если notebook лежит в notebooks/
REPO = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
MLRUNS = REPO / 'backend' / 'mlruns' / '1'
EVAL_DIR = REPO / 'backend' / 'tests' / 'eval'

print(f'REPO:   {REPO}')
print(f'MLruns: {MLRUNS} (exists={MLRUNS.exists()})')
print(f'Eval:   {EVAL_DIR} (exists={EVAL_DIR.exists()})')"""
)

md("""## 2. Загрузка данных четырёх прогонов

В MLflow у нас 4 завершённых run-а. У каждого есть CSV-артефакт с поваршивочными оценками.""")

code(
    """RUNS = {
    'exp1_dense':  '4ca165905e5047369f3dd40ba380af6e',   # gemma judge, битый корпус
    'exp1_hybrid': '92b32508b90d41b3bc257812d673a280',
    'exp2_dense':  'aa16b0bcd42a4898978182720547d06d',   # gpt-oss judge, OCR corpus
    'exp2_hybrid': '8c6fc9bbca3241549f52ea3bf916498e',
}

dfs = {}
for name, rid in RUNS.items():
    csv = MLRUNS / rid / 'artifacts' / 'eval_results_json.csv'
    dfs[name] = pd.read_csv(csv)
    print(f'{name:14s}  rows={len(dfs[name])}  path={csv.relative_to(REPO)}')"""
)

md("""## 3. Сводные метрики — таблица

Собираем среднее по 4 метрикам для каждого прогона.""")

code(
    """METRICS = ['faithfulness', 'answer_relevancy', 'llm_context_precision_with_reference', 'context_recall']
short_names = {'faithfulness': 'Faith', 'answer_relevancy': 'Relev',
               'llm_context_precision_with_reference': 'Prec', 'context_recall': 'Recall'}

summary = pd.DataFrame({
    name: [dfs[name][m].dropna().mean() for m in METRICS]
    for name in RUNS
}, index=[short_names[m] for m in METRICS]).T

summary.round(3)"""
)

md("""## 4. Bar chart — все 4 прогона рядом

Видно, как эксп.1 hybrid (green) уходит в потолок, а честный эксп.2 (blue/orange) стоит на реалистичных отметках.""")

code(
    """fig, ax = plt.subplots(figsize=(11, 5.5))
x = np.arange(len(METRICS)); w = 0.2
colors = {'exp1_dense': '#d62728', 'exp1_hybrid': '#2ca02c',
          'exp2_dense': '#1f77b4', 'exp2_hybrid': '#ff7f0e'}
labels = {'exp1_dense': 'Эксп.1 · Dense', 'exp1_hybrid': 'Эксп.1 · Hybrid',
          'exp2_dense': 'Эксп.2 · Dense', 'exp2_hybrid': 'Эксп.2 · Hybrid'}

for i, name in enumerate(RUNS):
    vals = [dfs[name][m].dropna().mean() for m in METRICS]
    ax.bar(x + (i - 1.5) * w, vals, w, label=labels[name], color=colors[name],
           alpha=0.75 if 'exp1' in name else 1.0)

ax.set_xticks(x)
ax.set_xticklabels([short_names[m] for m in METRICS], fontsize=11)
ax.set_ylabel('Mean score'); ax.set_ylim(0, 1.1)
ax.set_title('Ragas — 4 прогона в MLflow'); ax.legend(ncols=2)
ax.grid(axis='y', linestyle=':', alpha=0.4)
plt.show()"""
)

md("""## 5. Чистый эксперимент — фокус

Смотрим только на эксп.2 (независимый судья + OCR), где методология корректная.""")

code(
    """d = summary.loc['exp2_dense']
h = summary.loc['exp2_hybrid']
delta = h - d

comparison = pd.DataFrame({
    'Dense':  d.round(3),
    'Hybrid': h.round(3),
    'Δ':      delta.round(3),
    'Winner': ['Dense' if x < 0 else ('Hybrid' if x > 0 else '=') for x in delta]
})
comparison"""
)

md("""**Наблюдение:** Dense выигрывает 3 из 4 метрик, Hybrid — только Precision (+0.009). Все дельты в пределах шума — статистически незначимы.

## 6. Поваршивочный разбор — где что расходится

Смотрим на каждый из 15 вопросов эксп.2 отдельно.""")

code(
    """d = dfs['exp2_dense'].copy()
h = dfs['exp2_hybrid'].copy()

per_q = pd.DataFrame({
    '#': range(1, len(d) + 1),
    'synth': d.get('synthesizer', pd.Series(['?'] * len(d))).astype(str).str.replace('_query_synthesizer', '').str[:15],
    'question': d['user_input'].str[:70] + '…',
})
for m in METRICS:
    per_q[f'{short_names[m]}_D'] = d[m].round(2)
    per_q[f'{short_names[m]}_H'] = h[m].round(2)
    per_q[f'{short_names[m]}_Δ'] = (h[m] - d[m]).round(2)

per_q"""
)

md("## 7. Топ-5 вопросов где Hybrid выиграл сильнее всего")

code(
    """per_q_valid = per_q.dropna(subset=['Faith_Δ'])
top_hybrid = per_q_valid.nlargest(5, 'Faith_Δ')[['#', 'synth', 'question', 'Faith_D', 'Faith_H', 'Faith_Δ']]
top_hybrid"""
)

md("## 8. Топ-5 вопросов где Hybrid проиграл")

code(
    """top_dense = per_q_valid.nsmallest(5, 'Faith_Δ')[['#', 'synth', 'question', 'Faith_D', 'Faith_H', 'Faith_Δ']]
top_dense"""
)

md("""## 9. Разбор конкретной аномалии — вопрос №5

Q: «Кто там по 115-ФЗ про легализаци и отмывание денег?»

Hybrid faith=1.00, но Relev=0.00. Смотрим ответы обоих.""")

code(
    """i = 4  # вопрос #5 (индекс с 0)
print('QUESTION:')
print(f'  {d.iloc[i][\"user_input\"]}\\n')
print('REFERENCE:')
print(f'  {d.iloc[i][\"reference\"][:300]}\\n')
print('DENSE ANSWER (faith=0.50, relev=0.67):')
print(f'  {d.iloc[i][\"response\"][:300]}\\n')
print('HYBRID ANSWER (faith=1.00, relev=0.00):')
print(f'  {h.iloc[i][\"response\"][:300]}')"""
)

md("""**Вывод:** Hybrid дословно скопировал текст закона → судья дал faith=1.00 (все утверждения = закон). Но `answer_relevancy=0` — судья решил что ответ не отвечает на вопрос «Кто там?» (говорит о категории лиц, не о конкретном лице).

**Это ошибка судьи, а не hybrid'а.** LLM-судья слишком буквально понял «Кто» в разговорной формулировке.

## 10. Разбор Knowledge Graph""")

code(
    """with open(EVAL_DIR / 'kg.json') as f:
    kg = json.load(f)

from collections import Counter

# Топ entities
all_entities = []
for node in kg['nodes']:
    ents = node['properties'].get('entities') or []
    all_entities.extend(ents)

top_ents = Counter(all_entities).most_common(15)
print(f'Узлов: {len(kg[\"nodes\"])}')
print(f'Рёбер: {len(kg[\"relationships\"])}')
print(f'Уникальных entities: {len(set(all_entities))}')
print()
print('Топ-15 entities:')
for ent, c in top_ents:
    print(f'  {c:3d} × {ent}')"""
)

md("## 11. Testset — распределение вопросов")

code(
    """with open(EVAL_DIR / 'testset_auto.json') as f:
    testset = json.load(f)

synths = Counter(r['synthesizer_name'].replace('_query_synthesizer', '') for r in testset)
print(f'Всего вопросов: {len(testset)}')
print('Distribution:')
for s, c in synths.most_common():
    print(f'  {c} × {s}')"""
)

md(
    """## 12. Финальный вывод

**На нашем корпусе (bge-m3 + документы ФПСР)** hybrid retrieval **не даёт значимого преимущества**. Первый эксперимент показал ложную +51% фору из-за:

1. Bias самосуда (gemma-4-31b в 3-х ролях)
2. Мусора в индексе (битый картинка-PDF)
3. Узкого testset (1 doc из 3)

**Урок:** методология eval **критичнее** самой оптимизации RAG. Хороший judge + чистый корпус + разнообразный testset → честные цифры. Плохие условия → цифры, которым нельзя доверять.

---

📄 Полный отчёт: [`docs/plans/2026-06-30-clean-experiment-report.md`](../docs/plans/2026-06-30-clean-experiment-report.md)"""
)

out = Path("/tmp/01_experiment_analysis.ipynb")
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print(f"saved: {out}  ({out.stat().st_size} bytes, {len(nb['cells'])} cells)")
