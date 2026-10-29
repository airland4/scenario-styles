"""Собирает страницу «12 стилей сценариев» из паспортов стилей.

    python3 build.py      (откуда угодно)

Один файл на четыре случая — VARIANT:
  show    — страница для просмотра (12-styles.html), без форм
  site    — сайт для всех: у стиля кнопка «Скопировать промпт» с полным паспортом — вставить в любой чат
  project — папка-проект для Claude Code и Codex: паспорта в styles/, сценарии в scripts/, страница index.html с «Моими сценариями»
  module  — раздел портала: без своего дизайна, берёт цвета и шрифты портала (theme.css — подстройка);
            если в ../portal.html стоят метки scenario-styles:css и scenario-styles:page — заполняет их
Правишь паспорт или сценарий — запусти снова.
"""
from pathlib import Path
import html as H
import json
import re

VARIANT = 'module'

HERE = Path(__file__).resolve().parent
STYLES_DIR = HERE / 'styles' if (HERE / 'styles').is_dir() else HERE
SCRIPTS_DIR = HERE / 'scripts'
PORTAL = HERE.parent / 'portal.html'
GROUPS = ['История', 'Объяснить', 'Мнение', 'Продать']

HOW_TO_WRITE = """1. Сначала проверь, хватает ли фактов: что нужно от человека для этого стиля — в поле «что-нужно». Не хватает — задай вопросы одним коротким списком и жди ответа. Никогда не придумывай цифры, имена, результаты, отзывы и факты. Просят «придумай сам» — ставь пропуск [вписать: …] и скажи, что туда нужно.
2. Пиши по паспорту: порядок шагов, хронометраж из «Арки», «Правила» стиля. Один ролик — один стиль, не смешивай.
3. Пиши так, как человек говорит вслух: короткие фразы, живые слова, без канцелярита. Без «Привет, я…» и «В этом видео я расскажу». Первая фраза — середина истории или сразу польза.
4. Ответ: сверху стиль и длина; дальше таблица «Время | Говорю | В кадре», строка на шаг; снизу число слов (около 3 слов в секунду) и проверка по «Правилам» стиля — «чисто» или что нарушено и почему."""


def inline(s):
    s = H.escape(s.strip())
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    return re.sub(r'`(.+?)`', r'<code>\1</code>', s)


def cells(line):
    return [c.strip() for c in line.strip().strip('|').split('|')]


def split_md(path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        return {}, text
    _, fm, body = text.split('---', 2)
    meta = {}
    for line in fm.strip().splitlines():
        k, _, v = line.partition(':')
        meta[k.strip()] = v.strip()
    return meta, body


def sections(body):
    title, secs, cur = '', {}, None
    for line in body.splitlines():
        if line.startswith('# '):
            title = line[2:].strip()
        elif line.startswith('## '):
            cur = secs.setdefault(line[3:].strip(), {'para': [], 'items': [], 'rows': []})
        elif cur is None or not line.strip():
            continue
        elif line.startswith('|'):
            if not re.match(r'^\|[\s|:-]+\|$', line.strip()):
                cur['rows'].append(cells(line))
        elif line.startswith('- '):
            cur['items'].append(line[2:])
        else:
            cur['para'].append(line)
    return title, secs


def parse(path):
    meta, body = split_md(path)
    title, secs = sections(body)
    return {'slug': re.sub(r'^\d+-', '', path.stem), 'n': int(path.stem[:2]), 'file': path.name,
            'meta': meta, 'title': title, 'secs': secs, 'body': body.strip()}


def load_styles(folder=STYLES_DIR):
    return [parse(p) for p in sorted(folder.glob('[0-9][0-9]-*.md')) if p.name[:2] != '00']   # 00-overview.md — карта, не стиль


def load_scenarios():
    """Готовые сценарии из scripts/: шапка name / стиль / дата / длина, таблица «Время | Говорю | В кадре»."""
    out = []
    for p in sorted(SCRIPTS_DIR.glob('*.md'), reverse=True) if SCRIPTS_DIR.is_dir() else []:
        meta, body = split_md(p)
        rows = [cells(l) for l in body.splitlines() if l.startswith('|') and not re.match(r'^\|[\s|:-]+\|$', l.strip())]
        rest = [l for l in body.splitlines() if l.strip() and not l.startswith(('|', '#'))]
        out.append({'file': p.name, 'meta': meta, 'title': meta.get('name') or p.stem, 'rows': rows[1:], 'rest': rest})
    return out


def arc_svg(rows, length, compact=False):
    """Арка (Секунды | Накал | Шаг | Что сказать) → кривая накала с подписью каждого шага.
    compact — для телефона: узкая, на точках номера шагов, сами шаги — списком под графиком."""
    pts = [(float(r[0]), float(r[1]), r[2], r[3] if len(r) > 3 else '') for r in rows[1:]]
    W, Hh, L, R, T, B = (340, 230, 14, 14, 34, 52) if compact else (760, 300, 30, 24, 52, 74)
    nums = re.findall(r'\d+', length)
    end = max(pts[-1][0] + 6, float(nums[-1]) if nums else 0)
    x = lambda s: L + s / end * (W - L - R)
    y = lambda v: T + (100 - v) / 60 * (Hh - T - B)    # шкала накала 40–100 на всю высоту
    xy = [(x(s), y(v)) for s, v, *_ in pts] + [(x(end), y(pts[-1][1] - 6))]
    d = f'M{xy[0][0]:.1f},{xy[0][1]:.1f}'
    for (x0, y0), (x1, y1) in zip(xy, xy[1:]):
        m = (x0 + x1) / 2
        d += f' C{m:.1f},{y0:.1f} {m:.1f},{y1:.1f} {x1:.1f},{y1:.1f}'
    base = Hh - B + 8
    out = [f'<svg class="arc" viewBox="0 0 {W} {Hh - B + 34}" role="img" aria-label="Арка накала по секундам">',
           f'<path d="{d} L{x(end):.1f},{base:.1f} L{x(0):.1f},{base:.1f}Z" class="arc-fill"/><path d="{d}" class="arc-line"/>',
           f'<line x1="{L}" y1="{base:.1f}" x2="{W - R}" y2="{base:.1f}" class="arc-axis"/>']
    step = (10 if end <= 30 else 20 if end <= 60 else 30) if compact else (5 if end <= 30 else 10 if end <= 60 else 15)
    for s in range(0, int(end) + 1, step):
        out.append(f'<text x="{x(s):.1f}" y="{base + 20:.1f}" class="arc-tick" text-anchor="middle">{s} с</text>')
    placed = []                                        # занятые подписями прямоугольники (x0, x1, y0, y1)
    for i, (s, v, name, what) in enumerate(pts):
        prev = pts[i - 1][1] if i else v - 1
        nxt = pts[i + 1][1] if i + 1 < len(pts) else v - 1
        up = v >= (prev + nxt) / 2                     # вершина — подпись сверху, впадина — снизу
        peak = v >= 90
        label = str(i + 1) if compact else name
        anchor = 'middle' if compact else 'start' if i == 0 else 'end' if i == len(pts) - 1 else 'middle'
        w = len(label) * 8 + (6 if compact else 10)    # ширина подписи на глаз
        x0 = x(s) if anchor == 'start' else x(s) - w if anchor == 'end' else x(s) - w / 2
        free = lambda ty: all(x0 + w <= a or b <= x0 or ty + 4 <= c or d <= ty - 13 for a, b, c, d in placed)
        ty = next((t for t in (y(v) - 14 - k * 17 if up else y(v) + 24 + k * 17 for k in range(5)) if free(t)), y(v) - 14)
        placed.append((x0, x0 + w, ty - 13, ty + 4))
        out.append(f'<g><title>{H.escape(name)} — {H.escape(what)}</title>'
                   f'<circle cx="{x(s):.1f}" cy="{y(v):.1f}" r="{6 if peak else 4.5}" class="{"arc-pk" if peak else "arc-dot"}"/>'
                   f'<text x="{x(s):.1f}" y="{ty:.1f}" class="arc-lbl{" pk" if peak else ""}{" num" if compact else ""}" text-anchor="{anchor}">{H.escape(label)}</text></g>')
    out.append('</svg>')
    if compact:
        out.append('<ol class="arc-legend">' + ''.join(
            f'<li{" class=pk" if v >= 90 else ""}><b>{i + 1}</b><span>{s:g} с</span>{H.escape(name)}</li>'
            for i, (s, v, name, _) in enumerate(pts)) + '</ol>')
    return ''.join(out)


def ex_rows(rows):
    return ''.join(f'<div class="ex-row"><span class="ex-t">{H.escape(t)}{"" if t.endswith("с") else " с"}</span>'
                   f'<p class="ex-say">{inline(say)}</p><p class="ex-shot">{inline(shot)}</p></div>'
                   for t, say, shot, *_ in rows)


def ask_html(s, variant):
    """Блок «Сделать сценарий»: на сайте — полный промпт для любого чата, в проекте и портале — просьба агенту."""
    m = s['meta']
    need = f'<p class="ask-need"><b>Что нужно от тебя:</b> {inline(m.get("что-нужно", ""))}</p>'
    if variant == 'site':
        btn, ok = 'Скопировать промпт', 'Скопировано — вставь в ChatGPT, Claude или Gemini'
    else:
        btn, ok = 'Скопировать просьбу агенту', 'Скопировано — вставь в чат с агентом'
    path = f'styles/{s["file"]}' if variant == 'project' else f'{HERE.name}/{s["file"]}'
    return f'''
  <div class="ask"><div class="h">Сделать сценарий в этом стиле</div>{need}
    <textarea rows="4" placeholder="Тема и что было на самом деле — своими словами, можно коротко"></textarea>
    <button class="ask-btn" type="button" data-slug="{s["slug"]}" data-style="{H.escape(s["title"])}" data-file="{path}">{btn}</button>
    <span class="ask-ok">{ok}</span></div>'''


def style_html(s, variant):
    m, sec = s['meta'], s['secs']
    scheme = ''.join(f'<span>{inline(p)}</span>' for p in m['схема'].split('→'))
    what = ''.join(f'<p>{inline(p)}</p>' for p in sec['Что это']['para'])
    when = ''.join(f'<li>{inline(i)}</li>' for i in sec['Когда брать']['items'])
    steps = []
    for n, step, say, tpl in sec['Шаги']['rows'][1:]:
        btn = '' if tpl in ('—', '') else f'<button class="tpl" type="button" data-copy="{H.escape(tpl)}" title="Скопировать заготовку">{inline(tpl)}</button>'
        steps.append(f'<li><span class="sn">{H.escape(n)}</span><div><b>{inline(step)}</b><p>{inline(say)}</p>{btn}</div></li>')
    ex = sec['Пример']
    words = sum(len(r[1].split()) for r in ex['rows'][1:])
    rules = ''.join(f'<li>{inline(i)}</li>' for i in sec['Правила']['items'])
    ask = '' if variant == 'show' else ask_html(s, variant)
    return f'''<section class="st" data-id="{s["slug"]}" data-group="{H.escape(m["группа"])}">
  <header class="st-head"><div class="st-n">{s["n"]:02d}</div><div><h2>{H.escape(s["title"])}</h2>
    <div class="chips"><span>{H.escape(m["группа"])}</span><span>{H.escape(m["длина"])}</span></div></div></header>
  <div class="scheme">{scheme}</div>{ask}
  <div class="two">
    <div><div class="h">Что это за стиль</div>{what}</div>
    <div><div class="h">Когда брать</div><ul class="dots">{when}</ul></div>
  </div>
  <div class="h">Арка сценария</div>
  <div class="arc-box"><div class="arc-wide">{arc_svg(sec["Арка"]["rows"], m["длина"])}</div>
    <div class="arc-narrow">{arc_svg(sec["Арка"]["rows"], m["длина"], compact=True)}</div>
    <p class="arc-cap">По горизонтали — секунды ролика, по вертикали — накал: насколько зрителя держит. Яркие точки — пики, ради них досматривают.</p></div>
  <details class="fold" open><summary class="h">Шаги <small>заготовку можно скопировать нажатием</small></summary>
  <ol class="steps">{"".join(steps)}</ol></details>
  <details class="fold" open><summary class="h">Пример сценария</summary>
  <p class="ex-lead">{inline(" ".join(ex["para"]))}</p>
  <div class="ex"><div class="ex-row ex-hd"><span>Время</span><p>Говорю</p><p>В кадре</p></div>{ex_rows(ex["rows"][1:])}</div>
  <p class="ex-count">{words} слов</p></details>
  <details class="fold" open><summary class="h">Правила стиля</summary>
  <ul class="dots rules">{rules}</ul></details>
  <button class="top" type="button">↑ Ко всем стилям</button>
</section>'''


def card_html(s):
    m = s['meta']
    return (f'<button class="card" type="button" data-go="{s["slug"]}" data-group="{H.escape(m["группа"])}"><span class="c-n">{s["n"]:02d}</span>'
            f'<b>{H.escape(s["title"])}</b><span class="c-meta">{H.escape(m["группа"])} · {H.escape(m["длина"])}</span>'
            f'<span class="c-sch">{inline(m["схема"])}</span></button>')


def scenarios_html(items):
    if not items:
        return ('<div class="mine"><div class="h">Мои сценарии</div><p class="mine-empty">Пока пусто. Напиши агенту: '
                '«сделай сценарий рилс в стиле … про …» — готовый сценарий появится здесь.</p></div>')
    out = []
    for sc in items:
        m = sc['meta']
        chips = ''.join(f'<span>{H.escape(v)}</span>' for v in (m.get('стиль'), m.get('длина'), m.get('дата')) if v)
        rest = ''.join(f'<p class="sc-rest">{inline(l.lstrip("- "))}</p>' for l in sc['rest'])
        out.append(f'<details class="sc"><summary><b>{H.escape(sc["title"])}</b><span class="chips">{chips}</span></summary>'
                   f'<div class="ex">{ex_rows(sc["rows"])}</div>{rest}<p class="sc-file">scripts/{H.escape(sc["file"])}</p></details>')
    return f'<div class="mine"><div class="h">Мои сценарии <small>{len(items)}</small></div>{"".join(out)}</div>'


def prompts_json(styles):
    """Сайт: полный промпт стиля — правила + паспорт; {{ABOUT}} и {{TOPIC}} подставляет страница."""
    data = {}
    for s in styles:
        data[s['slug']] = (f'Ты — сценарист коротких видео (Reels, Shorts, TikTok). Напиши сценарий в стиле «{s["title"]}» строго по паспорту стиля ниже.\n\n'
                           f'Как работать:\n{HOW_TO_WRITE}\n\n'
                           f'Обо мне: {{{{ABOUT}}}}\n'
                           f'Тема и что было на самом деле: {{{{TOPIC}}}}\n'
                           f'Что нужно от меня для этого стиля: {s["meta"].get("что-нужно", "")}\n\n'
                           f'=== ПАСПОРТ СТИЛЯ «{s["title"]}» ===\n'
                           f'Длина: {s["meta"]["длина"]}\nСхема: {s["meta"]["схема"]}\n\n{s["body"]}')
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


TOKENS_BRAND = """
.scs{--scs-accent:#D84773;--scs-on-accent:#fff;--scs-bg:#F9F6EF;--scs-text:#2B2B2B;--scs-mut:rgba(43,43,43,.68);--scs-line:#E6D9C9;
  --scs-card:#fff;--scs-soft:#F3ECE2;--scs-fill:rgba(216,71,115,.12);--scs-input:#F9F6EF;
  --scs-font:'Manrope',-apple-system,sans-serif;--scs-font-head:'Playfair Display',Georgia,serif;--scs-r:18px}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .scs{--scs-bg:#232123;--scs-text:#F9F6EF;--scs-mut:rgba(249,246,239,.62);
  --scs-line:#3B3739;--scs-card:#2C292B;--scs-soft:#332F31;--scs-fill:rgba(216,71,115,.2);--scs-input:#232123}}
:root[data-theme="dark"] .scs{--scs-bg:#232123;--scs-text:#F9F6EF;--scs-mut:rgba(249,246,239,.62);--scs-line:#3B3739;--scs-card:#2C292B;--scs-soft:#332F31;--scs-fill:rgba(216,71,115,.2);--scs-input:#232123}
"""

# Раздел портала: своих цветов нет — акцент из --accent портала (если есть), остальное от цвета текста. Подстройка — theme.css
TOKENS_PORTAL = """
.scs{--scs-accent:var(--accent,#4F46E5);--scs-on-accent:#fff;--scs-bg:transparent;--scs-text:currentColor;
  --scs-mut:color-mix(in srgb,currentColor 64%,transparent);--scs-line:color-mix(in srgb,currentColor 14%,transparent);
  --scs-card:color-mix(in srgb,currentColor 3%,transparent);--scs-soft:color-mix(in srgb,currentColor 7%,transparent);
  --scs-fill:color-mix(in srgb,var(--scs-accent) 13%,transparent);--scs-input:transparent;
  --scs-font:inherit;--scs-font-head:inherit;--scs-r:14px}
"""

CSS = """
.scs{font-family:var(--scs-font);color:var(--scs-text);font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased}
.scs *{margin:0;padding:0;box-sizing:border-box}
.scs code{font-family:ui-monospace,monospace;font-size:.9em}
.scs .wrap{max-width:960px;margin:0 auto;padding:48px 16px 96px}
.scs .eyebrow{display:flex;align-items:center;gap:10px;font-weight:700;font-size:12px;letter-spacing:.24em;text-transform:uppercase;margin-bottom:18px}
.scs .eyebrow::before{content:'';width:10px;height:10px;background:var(--scs-accent)}
.scs h1{font-family:var(--scs-font-head);font-weight:900;font-size:clamp(38px,7vw,64px);line-height:.98;text-transform:uppercase;margin-bottom:18px}
.scs .lead{font-size:18px;color:var(--scs-mut);max-width:680px}
.scs .how{margin:28px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.scs .how div{background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);padding:14px 16px;font-size:14px;color:var(--scs-mut)}
.scs .how b{display:block;color:var(--scs-text);font-size:15px;margin-bottom:2px}
.scs .filter{display:flex;flex-wrap:wrap;gap:8px;margin:40px 0 16px}
.scs .filter button{font:inherit;font-weight:700;font-size:14px;min-height:40px;padding:8px 16px;border-radius:999px;border:1px solid var(--scs-line);background:var(--scs-card);color:var(--scs-text);cursor:pointer}
.scs .filter button.on{background:var(--scs-accent);border-color:var(--scs-accent);color:var(--scs-on-accent)}
.scs .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.scs .card{display:flex;flex-direction:column;gap:4px;padding:16px;border-radius:var(--scs-r);border:1px solid var(--scs-line);background:var(--scs-card);color:inherit;font:inherit;text-align:left;cursor:pointer;transition:border-color .15s,transform .15s}
.scs .card:hover{border-color:var(--scs-accent);transform:translateY(-2px)}
.scs .c-n{font-family:var(--scs-font-head);font-weight:900;font-size:26px;color:var(--scs-accent);line-height:1}
.scs .card b{font-size:18px;line-height:1.2}
.scs .c-meta{font-size:13px;color:var(--scs-mut);font-weight:600}
.scs .c-sch{font-size:13px;color:var(--scs-mut);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;margin-top:4px}
.scs .st{margin-top:72px;padding-top:40px;border-top:2px solid var(--scs-line);scroll-margin-top:12px}
.scs .st-head{display:flex;gap:16px;align-items:flex-start}
.scs .st-n{font-family:var(--scs-font-head);font-weight:900;font-size:clamp(48px,9vw,72px);line-height:.9;color:var(--scs-accent)}
.scs .st h2{font-family:var(--scs-font-head);font-weight:800;font-size:clamp(28px,5vw,42px);line-height:1.05}
.scs .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.scs .chips span{font-size:13px;font-weight:700;padding:4px 12px;border-radius:999px;background:var(--scs-soft)}
.scs .scheme{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:22px 0 4px}
.scs .scheme span{font-size:14px;font-weight:600;padding:6px 12px;border-radius:10px;background:var(--scs-card);border:1px solid var(--scs-line)}
.scs .scheme span+span::before{content:'→';color:var(--scs-accent);margin-right:8px;font-weight:800}
.scs .two{display:grid;grid-template-columns:1.4fr 1fr;gap:28px}
@media (max-width:700px){.scs .two{grid-template-columns:1fr;gap:0}}
.scs .two p{margin-bottom:10px;font-size:16.5px}
.scs .h{font-weight:800;font-size:13px;letter-spacing:.16em;text-transform:uppercase;margin:32px 0 12px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.scs .h small{font-weight:600;letter-spacing:0;text-transform:none;color:var(--scs-mut);font-size:13px}
.scs .dots{list-style:none;display:grid;gap:8px}
.scs .dots li{padding-left:18px;position:relative}
.scs .dots li::before{content:'';position:absolute;left:0;top:.6em;width:7px;height:7px;background:var(--scs-accent)}
.scs .arc-box{background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);padding:16px 16px 12px}
.scs .arc{display:block;width:100%;height:auto}
.scs .arc-narrow{display:none}
.scs .arc-lbl.num{font-size:13px;font-weight:800}
.scs .arc-legend{list-style:none;display:grid;gap:4px;margin-top:10px;font-size:14px}
.scs .arc-legend li{display:flex;gap:8px;align-items:baseline}
.scs .arc-legend b{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:12px;border:2px solid var(--scs-accent);color:var(--scs-accent)}
.scs .arc-legend li.pk b{background:var(--scs-accent);color:var(--scs-on-accent)}
.scs .arc-legend span{flex:none;width:40px;color:var(--scs-mut);font-size:13px}
.scs .fold>summary{cursor:pointer;list-style:none}
.scs .fold>summary::-webkit-details-marker{display:none}
.scs .fold>summary::after{content:'';width:8px;height:8px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg);margin-left:auto;align-self:center;transition:transform .15s}
.scs .fold[open]>summary::after{transform:rotate(-135deg)}
.scs .to-dl{display:inline-block;margin-top:14px;font-size:15px;font-weight:700;color:var(--scs-accent);background:none;border:0;padding:0;font-family:inherit;cursor:pointer;text-align:left}
@media (max-width:600px){
  .scs .wrap{padding-top:32px}
  .scs .arc-wide{display:none}.scs .arc-narrow{display:block}
  .scs .arc-box{padding:12px 12px 10px}
  .scs .filter{flex-wrap:nowrap;overflow-x:auto;margin:32px -16px 14px;padding:0 16px 4px;scrollbar-width:none}
  .scs .filter::-webkit-scrollbar{display:none}
  .scs .filter button{flex:none}
  .scs .cards{gap:8px}
  .scs .card{display:grid;grid-template-columns:auto 1fr;column-gap:12px;align-items:center;padding:12px 14px}
  .scs .c-n{grid-row:span 2;font-size:24px}
  .scs .card b{font-size:16px}
  .scs .c-sch{display:none}
  .scs .st{margin-top:48px;padding-top:28px}
  .scs .st-head{gap:12px}
  .scs .scheme span{font-size:13px;padding:4px 9px}
  .scs .scheme span+span::before{margin-right:5px}
  .scs .ask{padding:2px 14px 14px}
  .scs .ask-ok{display:none;margin:8px 0 0}
  .scs .ask-ok.on{display:block}
  .scs .ask-btn{width:100%}
  .scs .how div{padding:12px;font-size:13px}
  .scs .fold>summary.h{margin:24px 0 10px;padding:12px 14px;border:1px solid var(--scs-line);border-radius:var(--scs-r);background:var(--scs-card)}
  .scs .fold[open]>summary.h{margin-bottom:12px}
  .scs .fold+.fold>summary.h{margin-top:10px}
  .scs .fold>summary.h small{display:none}
  .scs .steps li{padding:12px}
}
.scs .arc-fill{fill:var(--scs-fill)}
.scs .arc-line{fill:none;stroke:var(--scs-accent);stroke-width:3;stroke-linecap:round}
.scs .arc-axis{stroke:var(--scs-line);stroke-width:1.5}
.scs .arc-tick{font-size:12px;fill:var(--scs-mut);font-family:inherit}
.scs .arc-dot{fill:var(--scs-card);stroke:var(--scs-accent);stroke-width:2.5}
.scs .arc-pk{fill:var(--scs-accent);stroke:var(--scs-card);stroke-width:2}
.scs .arc-lbl{font-size:13px;font-weight:700;fill:var(--scs-text);font-family:inherit}
.scs .arc-lbl.pk{fill:var(--scs-accent)}
.scs .arc-cap{font-size:13px;color:var(--scs-mut);margin-top:8px}
.scs .steps{list-style:none;display:grid;gap:10px}
.scs .steps li{display:flex;gap:14px;background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);padding:14px 16px}
.scs .sn{flex:none;width:30px;height:30px;border-radius:50%;background:var(--scs-accent);color:var(--scs-on-accent);font-weight:800;font-size:14px;display:grid;place-items:center}
.scs .steps b{font-size:16px}
.scs .steps p{color:var(--scs-mut);font-size:15px}
.scs .tpl{margin-top:8px;font:inherit;font-size:15px;text-align:left;padding:8px 12px;border-radius:10px;border:1px dashed var(--scs-accent);background:var(--scs-fill);color:var(--scs-text);cursor:pointer;width:100%}
.scs .tpl:hover{border-style:solid}
.scs .tpl.done{border-style:solid;background:var(--scs-accent);color:var(--scs-on-accent)}
.scs .ex-lead{font-size:14px;color:var(--scs-mut);margin-bottom:10px}
.scs .ex{border:1px solid var(--scs-line);border-radius:var(--scs-r);overflow:hidden;background:var(--scs-card)}
.scs .ex-row{display:grid;grid-template-columns:72px 1.5fr 1fr;gap:14px;padding:12px 16px;border-top:1px solid var(--scs-line)}
.scs .ex-row:first-child{border-top:0}
.scs .ex-hd{background:var(--scs-soft);font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.scs .ex-t{font-weight:800;color:var(--scs-accent);font-size:14px;white-space:nowrap}
.scs .ex-say{font-size:16px}
.scs .ex-shot{font-size:14px;color:var(--scs-mut)}
@media (max-width:640px){.scs .ex-hd{display:none}.scs .ex-row{grid-template-columns:1fr;gap:4px}.scs .ex-shot::before{content:'В кадре: ';font-weight:700}}
.scs .ex-count{font-size:13px;color:var(--scs-mut);margin-top:8px}
.scs .top{display:inline-block;margin-top:28px;font:inherit;font-size:14px;font-weight:700;color:var(--scs-accent);background:none;border:0;cursor:pointer}
.scs .hidden{display:none!important}
.scs .ask{margin-top:24px;background:var(--scs-card);border:2px solid var(--scs-accent);border-radius:var(--scs-r);padding:4px 18px 18px}
.scs .ask .h{margin-top:16px}
.scs .ask-need{font-size:14px;color:var(--scs-mut);margin-bottom:10px}
.scs .ask-need b{color:var(--scs-text)}
.scs textarea{display:block;width:100%;font:inherit;font-size:15px;padding:12px 14px;border-radius:12px;border:1px solid var(--scs-line);background:var(--scs-input);color:var(--scs-text);resize:vertical}
.scs .ask-btn,.scs .dl a{display:inline-block;margin-top:10px;font:inherit;font-weight:800;font-size:15px;min-height:44px;padding:10px 20px;border:0;border-radius:999px;background:var(--scs-accent);color:var(--scs-on-accent);cursor:pointer;text-decoration:none}
.scs .ask-ok{display:none;margin-left:12px;font-size:14px;font-weight:700;color:var(--scs-accent)}
.scs .ask-ok.on{display:inline}
.scs .about{margin-top:28px;background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);padding:4px 18px 18px}
.scs .about p{font-size:14px;color:var(--scs-mut);margin-bottom:10px}
.scs .about-ok{font-size:13px;font-weight:700;color:var(--scs-accent);margin-top:6px;min-height:1.2em}
.scs .mine{margin-top:28px}
.scs .mine-empty{color:var(--scs-mut);background:var(--scs-card);border:1px dashed var(--scs-line);border-radius:var(--scs-r);padding:16px}
.scs .sc{background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);margin-bottom:10px}
.scs .sc summary{cursor:pointer;padding:14px 16px;list-style:none}
.scs .sc summary b{font-size:17px}
.scs .sc[open] summary{border-bottom:1px solid var(--scs-line)}
.scs .sc .ex{border:0;border-radius:0}
.scs .sc-rest{font-size:14px;color:var(--scs-mut);padding:8px 16px 0}
.scs .sc-file{font-size:12px;color:var(--scs-mut);padding:8px 16px 14px}
.scs .dl{margin-top:72px;padding-top:40px;border-top:2px solid var(--scs-line)}
.scs .dl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.scs .dl-grid > div{background:var(--scs-card);border:1px solid var(--scs-line);border-radius:var(--scs-r);padding:18px}
.scs .dl-grid b{font-size:18px;display:block;margin-bottom:6px}
.scs .dl-grid p,.scs .dl-grid li{font-size:14px;color:var(--scs-mut)}
.scs .dl-grid ol{padding-left:18px;margin-top:8px;display:grid;gap:4px}
"""

SCRIPT = """<script>
(() => {
const root = document.currentScript.closest('.scs') || document;
function copy(text, done) {               // буфер обмена; в iframe без разрешения — запасной путь через textarea
  const old = () => { const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); done(); } catch (e) {} t.remove(); };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done).catch(old); else old();
}
const store = { get: k => { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
const about = root.querySelector('.about textarea');
if (about) {
  about.value = store.get('scs-about');
  about.addEventListener('input', () => { store.set('scs-about', about.value);
    root.querySelector('.about-ok').textContent = 'Сохранено в этом браузере — попадёт в каждый промпт'; });
}
const prompts = JSON.parse((root.querySelector('script[type="application/json"]') || {}).textContent || '{}');
root.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () =>
  copy(b.dataset.copy, () => { b.classList.add('done'); setTimeout(() => b.classList.remove('done'), 1200); })));
root.querySelectorAll('.ask-btn').forEach(b => b.addEventListener('click', () => {
  const box = b.closest('.ask'), ok = box.querySelector('.ask-ok'), topic = box.querySelector('textarea').value.trim();
  let text;
  if (prompts[b.dataset.slug]) {
    const me = about ? about.value.trim() : '';
    text = prompts[b.dataset.slug].replace('{{ABOUT}}', () => me || '— спроси меня: ниша, для кого ролики, как я говорю')
                                  .replace('{{TOPIC}}', () => topic || '— спроси меня');
  } else {
    text = `Сделай сценарий рилс в стиле «${b.dataset.style}» (${b.dataset.file}).\\n`
      + (topic ? `Тема и что было на самом деле: ${topic}` : 'Тему и факты спроси у меня.');
  }
  copy(text, () => { ok.classList.add('on'); setTimeout(() => ok.classList.remove('on'), 2500); });
}));
if (matchMedia('(max-width:600px)').matches) root.querySelectorAll('.fold').forEach(d => d.open = false);   // на телефоне шаги, пример и правила свёрнуты
const go = el => el && el.scrollIntoView({ behavior: 'smooth', block: 'start' });
root.querySelectorAll('.to-dl').forEach(b => b.addEventListener('click', () => go(root.querySelector('.dl'))));
root.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => go(root.querySelector(`.st[data-id="${b.dataset.go}"]`))));
root.querySelectorAll('.top').forEach(b => b.addEventListener('click', () => go(root.querySelector('.filter'))));
root.querySelectorAll('.filter button').forEach(b => b.addEventListener('click', () => {
  root.querySelectorAll('.filter button').forEach(x => x.classList.toggle('on', x === b));
  const g = b.dataset.g;
  root.querySelectorAll('.card,.st').forEach(el => el.classList.toggle('hidden', !!g && el.dataset.group !== g));
}));
})();
</script>"""

EYEBROW = {'show': 'Мастер-класс · сценарии Reels', 'site': 'Сценарии Reels',
           'project': 'Стили сценариев · проект', 'module': 'Стили сценариев'}

DOWNLOADS = """
<div class="dl"><div class="h">Хочешь, чтобы нейросеть помнила стили сама?</div>
<div class="dl-grid">
  <div><b>Проект для Claude и Codex</b><p>Папка, которую открываешь в Codex или Claude Code. Дальше просто пишешь «сделай сценарий в стиле …», а готовые сценарии собираются на странице проекта.</p>
    <ol><li>Скачай и распакуй архив</li><li>Открой папку <code>scenario-styles</code> в Codex или Claude Code</li><li>Напиши: «Сделай сценарий рилс в стиле Урок про …»</li></ol>
    <a href="scenario-styles-project.zip" download>Скачать проект</a></div>
  <div><b>Раздел для своего портала</b><p>Если у тебя есть свой портал с агентом — новый раздел меню «Стили сценариев» в его стиле, со своими цветами и шрифтами.</p>
    <ol><li>Скачай архив, папку <code>scenario-styles</code> положи в корень своей среды</li><li>Открой <code>scenario-styles/INSTALL.md</code></li><li>Вставь текст оттуда в чат с агентом</li></ol>
    <a href="scenario-styles-module.zip" download>Скачать раздел</a></div>
</div></div>"""


def body_html(styles, variant, scenarios=()):
    groups = [g for g in GROUPS if any(s['meta']['группа'] == g for s in styles)]
    filt = '<button class="on" data-g="">Все</button>' + ''.join(f'<button data-g="{g}">{g}</button>' for g in groups)
    lead = ('Стиль сценария — это порядок, в котором говорить, чтобы ролик досматривали. '
            + {'site': 'Выбери стиль под задачу ролика, впиши тему — и забери готовый промпт для ChatGPT, Claude или Gemini.',
               'project': 'Выбери стиль, впиши тему, скопируй просьбу агенту — или просто напиши ему «сделай сценарий в стиле …».',
               'module': 'Выбери стиль, впиши тему и отдай просьбу агенту.'}.get(variant, 'Выбери стиль под задачу ролика, пройди его шаги — и получишь сценарий, который держит внимание до конца.'))
    about = '' if variant != 'site' else '''
<div class="about"><div class="h">О себе <small>один раз — попадёт в каждый промпт</small></div>
  <p>Ниша, для кого твои ролики, как ты говоришь: на «ты» или на «вы», пара твоих любимых фраз.</p>
  <textarea rows="3" placeholder="Например: психолог, ролики для мам в декрете, говорю на «ты», люблю «давай честно»"></textarea>
  <div class="about-ok"></div></div>'''
    mine = scenarios_html(scenarios) if variant in ('project', 'module') else ''
    data = f'<script type="application/json">{prompts_json(styles)}</script>' if variant == 'site' else ''
    return f'''<div class="wrap">
<div class="eyebrow">{EYEBROW[variant]}</div>
<h1>12 стилей сценариев</h1>
<p class="lead">{lead}</p>{'<button class="to-dl" type="button">↓ Проект для Claude и Codex, раздел для портала</button>' if variant == 'site' else ''}
<div class="how">
  <div><b>Что это за стиль</b>Суть и когда его брать</div>
  <div><b>Арка</b>Где в ролике пики и спады внимания — по секундам</div>
  <div><b>Шаги</b>Что говорить на каждом шаге, заготовки фраз</div>
  <div><b>Пример</b>Готовый сценарий: что говорю и что в кадре</div>
</div>{about}{mine}
<nav class="filter">{filt}</nav>
<div class="cards">{"".join(card_html(s) for s in styles)}</div>
{chr(10).join(style_html(s, variant) for s in styles)}
{DOWNLOADS if variant == 'site' else ''}
</div>{data}'''


def css_for(variant):
    theme = (HERE / 'theme.css').read_text(encoding='utf-8') if variant == 'module' and (HERE / 'theme.css').exists() else ''
    return (TOKENS_PORTAL if variant == 'module' else TOKENS_BRAND) + CSS + theme


def page_html(styles, variant, scenarios=()):
    fonts = '' if variant == 'module' else ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
             '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Playfair+Display:wght@700;800;900&display=swap" rel="stylesheet">')
    page_bg = ('body{margin:0;background:#fff;color:#1f1f1f;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}'
               '@media (prefers-color-scheme:dark){body{background:#1c1c1e;color:#f2f2f2}}') if variant == 'module' else \
              'body{margin:0;background:var(--scs-bg)}html{scroll-behavior:smooth}'
    if variant != 'module':                            # фон страницы — из токенов бренда: объявляем их и на body
        page_bg = page_bg.replace('body{', 'body.scs{', 1)
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>12 стилей сценариев</title>
{fonts}
<style>{css_for(variant)}
{page_bg}</style></head>
<body{' class="scs"' if variant != 'module' else ''}><div class="scs">{body_html(styles, variant, scenarios)}
{SCRIPT}</div>
</body></html>
'''


def fill_portal(styles, scenarios):
    """Раздел портала: метки ставит агент при установке (INSTALL.md), дальше этот файл только меняет то, что между ними."""
    if not PORTAL.exists():
        return
    html = PORTAL.read_text(encoding='utf-8')
    marks = {'css': ('/* scenario-styles:css:start */', '/* scenario-styles:css:end */', css_for('module')),
             'page': ('<!-- scenario-styles:page:start -->', '<!-- scenario-styles:page:end -->',
                      f'<div class="scs">{body_html(styles, "module", scenarios)}\n{SCRIPT}</div>')}
    done = []
    for name, (a, b, content) in marks.items():
        if a in html and b in html:
            i, j = html.index(a) + len(a), html.index(b)
            html = html[:i] + '\n' + content + '\n' + html[j:]
            done.append(name)
    if done:
        PORTAL.write_text(html, encoding='utf-8')
        print('Портал обновлён:', ', '.join(done))
    else:
        print('В portal.html нет меток scenario-styles — раздел не встроен (см. INSTALL.md)')


def main():
    styles = load_styles()
    scenarios = load_scenarios() if VARIANT in ('project', 'module') else []
    out = HERE / ('12-styles.html' if VARIANT == 'show' else 'index.html')
    out.write_text(page_html(styles, VARIANT, scenarios), encoding='utf-8')
    print(f'Готово: {out} — {len(styles)} стилей' + (f', сценариев: {len(scenarios)}' if VARIANT in ('project', 'module') else ''))
    if VARIANT == 'module':
        fill_portal(styles, scenarios)


if __name__ == '__main__':
    main()
