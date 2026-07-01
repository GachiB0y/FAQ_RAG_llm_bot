#!/usr/bin/env python3
"""One-off: генерирует графики отчёта в /tmp/report_images/."""
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

OUT = Path('/tmp/report_images')
OUT.mkdir(parents=True, exist_ok=True)

data = {
    'metric':      ['Faithfulness', 'Answer\nRelevancy', 'Context\nPrecision', 'Context\nRecall'],
    'exp1_dense':  [0.826, 0.700, 0.606, 0.736],
    'exp1_hybrid': [1.000, 0.816, 0.917, 1.000],
    'exp2_dense':  [0.909, 0.762, 0.666, 0.950],
    'exp2_hybrid': [0.895, 0.722, 0.675, 0.929],
}
df = pd.DataFrame(data)

# ─── FIG 1: все 4 прогона ─────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 6))
x = np.arange(len(df)); w = 0.2
ax.bar(x - 1.5*w, df['exp1_dense'],  w, label='Эксп.1 · Dense',  color='#d62728', alpha=0.7)
ax.bar(x - 0.5*w, df['exp1_hybrid'], w, label='Эксп.1 · Hybrid', color='#2ca02c', alpha=0.7)
ax.bar(x + 0.5*w, df['exp2_dense'],  w, label='Эксп.2 · Dense',  color='#1f77b4')
ax.bar(x + 1.5*w, df['exp2_hybrid'], w, label='Эксп.2 · Hybrid', color='#ff7f0e')
ax.set_xticks(x); ax.set_xticklabels(df['metric'], fontsize=11)
ax.set_ylabel('Mean score'); ax.set_ylim(0, 1.15)
ax.set_title('Все 4 прогона Ragas в MLflow', fontsize=13, pad=12)
ax.legend(loc='upper right', fontsize=9, ncols=2)
ax.grid(axis='y', linestyle=':', alpha=0.4)
for c in ax.containers:
    for b in c:
        h = b.get_height()
        ax.text(b.get_x()+b.get_width()/2, h+0.01, f'{h:.2f}', ha='center', va='bottom', fontsize=8)
plt.tight_layout()
plt.savefig(OUT/'01_all_runs_bar.png', dpi=140, bbox_inches='tight')
plt.close()
print('saved 01_all_runs_bar.png')

# ─── FIG 2: чистый эксп — dense vs hybrid ─────────────────
fig, ax = plt.subplots(figsize=(9, 5.5))
x = np.arange(len(df)); w = 0.35
ax.bar(x - w/2, df['exp2_dense'],  w, label='Dense',  color='#1f77b4')
ax.bar(x + w/2, df['exp2_hybrid'], w, label='Hybrid', color='#ff7f0e')
ax.set_xticks(x); ax.set_xticklabels(df['metric'], fontsize=11)
ax.set_ylabel('Mean score'); ax.set_ylim(0.5, 1.05)
ax.set_title('Чистый эксперимент — Dense vs Hybrid\n'
             'судья gpt-oss-120b · 15 вопросов · 3 документа',
             fontsize=12, pad=10)
ax.legend(fontsize=11)
ax.grid(axis='y', linestyle=':', alpha=0.4)
for c in ax.containers:
    for b in c:
        h = b.get_height()
        ax.text(b.get_x()+b.get_width()/2, h+0.005, f'{h:.3f}',
                ha='center', va='bottom', fontsize=10)
for i in range(len(df)):
    delta = df['exp2_hybrid'][i] - df['exp2_dense'][i]
    color = '#2ca02c' if delta > 0 else '#d62728'
    ax.text(i, 0.55, f'Δ = {delta:+.3f}', ha='center', color=color,
            fontsize=10, fontweight='bold')
plt.tight_layout()
plt.savefig(OUT/'02_clean_dense_vs_hybrid.png', dpi=140, bbox_inches='tight')
plt.close()
print('saved 02_clean_dense_vs_hybrid.png')

# ─── FIG 3: parallel coords ──────────────────────────────
fig, ax = plt.subplots(figsize=(11, 6))
axes_labels = ['retrieval_mode'] + [m.replace('\n', ' ') for m in df['metric']]
d = df['exp2_dense'].values
h = df['exp2_hybrid'].values
mins = np.minimum(d, h)
maxs = np.maximum(d, h)

def normed(vals):
    return [
        0.5 if maxs[i] == mins[i] else (v - mins[i]) / (maxs[i] - mins[i])
        for i, v in enumerate(vals)
    ]

positions = list(range(len(axes_labels)))
dense_pts = [0.0] + normed(d)
hybrid_pts = [1.0] + normed(h)
ax.plot(positions, dense_pts, 'o-', color='#1f77b4', lw=2.5, ms=12, label='Dense')
ax.plot(positions, hybrid_pts, 's-', color='#ff7f0e', lw=2.5, ms=12, label='Hybrid')
for i, pos in enumerate(positions):
    ax.axvline(pos, color='gray', alpha=0.3, lw=0.8)
    if i == 0:
        ax.text(pos, 1.06, 'hybrid', ha='center', fontsize=9, color='gray')
        ax.text(pos, -0.06, 'dense', ha='center', fontsize=9, color='gray')
    else:
        ax.text(pos, 1.06, f'{maxs[i-1]:.3f}', ha='center', fontsize=9, color='gray')
        ax.text(pos, -0.06, f'{mins[i-1]:.3f}', ha='center', fontsize=9, color='gray')
ax.set_xticks(positions)
ax.set_xticklabels(axes_labels, fontsize=10)
ax.set_yticks([])
ax.set_ylim(-0.15, 1.15)
ax.set_title('Parallel Coordinates — эксп.2\n'
             'Dense выше на 3 метриках, Hybrid только на Precision',
             fontsize=12, pad=10)
ax.legend(fontsize=11, loc='upper left')
plt.tight_layout()
plt.savefig(OUT/'03_parallel_coords.png', dpi=140, bbox_inches='tight')
plt.close()
print('saved 03_parallel_coords.png')

# ─── FIG 4: dense baseline «улучшение» ────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
x = np.arange(len(df)); w = 0.35
d1 = df['exp1_dense'].values
d2 = df['exp2_dense'].values
ax.bar(x - w/2, d1, w, label='Эксп.1 (грязный судья · шумный индекс)', color='#a0aec0')
ax.bar(x + w/2, d2, w, label='Эксп.2 (независимый судья · OCR)', color='#1f77b4')
ax.set_xticks(x); ax.set_xticklabels(df['metric'], fontsize=11)
ax.set_ylabel('Mean score'); ax.set_ylim(0.5, 1.0)
ax.set_title('Один и тот же Dense RAG — два разных eval-сетапа\n'
             '«Улучшение» — не апгрейд, а честное измерение',
             fontsize=12, pad=10)
ax.legend(fontsize=10)
ax.grid(axis='y', linestyle=':', alpha=0.4)
for i in range(len(df)):
    delta = d2[i] - d1[i]
    ax.annotate('', xy=(i+w/2, d2[i]), xytext=(i-w/2, d1[i]),
                arrowprops=dict(arrowstyle='->', color='#2ca02c', lw=1.5))
    ax.text(i, 0.53, f'+{delta*100:.0f}pp', ha='center', color='#2ca02c',
            fontsize=10, fontweight='bold')
plt.tight_layout()
plt.savefig(OUT/'04_dense_baseline_growth.png', dpi=140, bbox_inches='tight')
plt.close()
print('saved 04_dense_baseline_growth.png')

print('\n=== Все графики готовы:', OUT, '===')
for p in sorted(OUT.iterdir()):
    print(f'  {p.name}  ({p.stat().st_size/1024:.1f} KB)')
